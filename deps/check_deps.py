"""
GOATS Dependency Resolver

Analyzes version compatibility between GOATS, TOMToolkit, DRAGONS and JDAViz,
checks conda availability, and reports conflicts.

Usage:
    python3 check_deps.py                    # latest GOATS, direct deps
    python3 check_deps.py -v 26.4.3          # specific version
    python3 check_deps.py -d 2               # include 2 levels of transitive deps
    python3 check_deps.py --json > deps.json # export JSON for the viewer
    python3 check_deps.py --open             # open the interactive viewer in a browser
    python3 check_deps.py --fail-on-conflict # exit 2 if conflicts found (CI gating)

Environment:
    GITHUB_TOKEN   used (if set) to raise the GitHub API rate limit
    NO_COLOR       disables colored output

Exit codes:
    0  success
    1  fatal error (could not resolve versions / fetch metadata)
    2  conflicts found, with --fail-on-conflict
"""

from __future__ import annotations

import argparse
import functools
import gzip
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

# ---------------------------------------------------------------------------
# Logging — always stderr so --json output stays clean
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr
)
logger = logging.getLogger("dep")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOATS_REPO = ("gemini-hlsw", "goats")
TOMTOOLKIT_REPO = ("TOMToolkit", "tom_base")
DRAGONS_REPO = ("GeminiDRSoftware", "DRAGONS")
JDAVIZ_REPO = ("spacetelescope", "jdaviz")

SOURCE_IDS = frozenset({"goats", "tomtoolkit", "dragons", "jdaviz"})
CONFLICT_STATUSES = frozenset({"conflict", "invalid_range", "conda_conflict"})

RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/refs/tags/{ref}/{path}"
PYPI_URL = "https://pypi.org/pypi/{package}/{version}/json"
PYPI_URL_LATEST = "https://pypi.org/pypi/{package}/json"
ANACONDA_URL = "https://api.anaconda.org/package/{channel}/{package}"
GITHUB_LATEST_RELEASE = "https://api.github.com/repos/{owner}/{repo}/releases/latest"

PRIMARY_CHANNEL = "conda-forge"
CONDA_CHANNELS = [PRIMARY_CHANNEL, "astroconda", "defaults"]
# Gemini channels are plain static repodata; they must be pointed at a
# <base>/<subdir>/repodata.json, not at the channel root (which is an HTML
# redirect and used to blow up JSON parsing).
GEMINI_CHANNEL_ROOTS = [
    "https://gemini-hlsw.github.io/goats-infra/conda-test",
    "https://gemini-hlsw.github.io/goats-infra/conda",
    "http://astroconda.gemini.edu/public",
]
CONDA_SUBDIRS = ["noarch", "linux-64", "osx-64"]
GEMINI_REPODATA_URLS = [
    f"{root}/{subdir}/repodata.json"
    for root in GEMINI_CHANNEL_ROOTS
    for subdir in CONDA_SUBDIRS
]

# PyPI name -> conda name, for packages whose conda name differs.
PACKAGE_NAME_MAP: dict[str, str] = {
    "channels-redis": "channels_redis",
    "channels_redis": "channels_redis",
    "redis": "redis-server",
    "msgpack": "msgpack-python",
}

USER_AGENT = "goats-dependency-resolver/2.0 (+https://github.com/gemini-hlsw/goats)"

DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_TIMEOUT = 15
DEFAULT_WORKERS = 16
HTTP_RETRIES = 2

# Mutated by main() via configure_python(); read by parse_requirements().
PYTHON_VERSION = DEFAULT_PYTHON_VERSION
PYTHON_ENVIRONMENT: dict[str, str] = {}

_TIMEOUT = object()  # sentinel: the request timed out / host unreachable


def configure_python(version: str) -> None:
    """Set the Python version used to evaluate environment markers."""
    global PYTHON_VERSION
    PYTHON_VERSION = version
    full = version if version.count(".") >= 2 else f"{version}.0"
    PYTHON_ENVIRONMENT.clear()
    PYTHON_ENVIRONMENT.update(
        {
            "python_version": ".".join(version.split(".")[:2]),
            "python_full_version": full,
            "sys_platform": "linux",
            "platform_machine": "x86_64",
            "platform_system": "Linux",
            "os_name": "posix",
            "implementation_name": "cpython",
            "extra": "",
        }
    )


configure_python(DEFAULT_PYTHON_VERSION)

# ---------------------------------------------------------------------------
# Terminal colors
# ---------------------------------------------------------------------------


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


_COLOR_ENABLED = True


def configure_color(force: bool | None = None) -> None:
    """Enable colors only when they will actually render."""
    global _COLOR_ENABLED
    if force is not None:
        _COLOR_ENABLED = force
        return
    _COLOR_ENABLED = (
        not os.environ.get("NO_COLOR")
        and os.environ.get("TERM") != "dumb"
        and sys.stdout.isatty()
    )


configure_color()


def colored(text: str, color: str, bold: bool = False) -> str:
    if not _COLOR_ENABLED:
        return text
    prefix = Color.BOLD if bold else ""
    return f"{prefix}{color}{text}{Color.RESET}"


def die(message: str) -> NoReturn:
    """Print a red error to stderr and exit non-zero."""
    print(colored(f"ERROR: {message}", Color.RED, bold=True), file=sys.stderr)
    sys.exit(1)


SOURCE_COLOR: dict[str, str] = {
    "goats": Color.BLUE,
    "tomtoolkit": Color.CYAN,
    "dragons": Color.YELLOW,
    "jdaviz": Color.GREEN,
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

# (operator, version_str, source_id, marker_or_None)
Bound = tuple[str, str, str, str | None]
# (spec_str, source_id, marker_or_None)
SpecSource = tuple[str, str, str | None]


@dataclass
class PackageInfo:
    spec_sources: list[SpecSource]
    lower_bound: Bound | None = None
    upper_bound: Bound | None = None
    pinned: list[tuple[str, str, str | None]] = field(default_factory=list)
    excluded: list[tuple[str, str, str | None]] = field(default_factory=list)
    has_conflict: bool = False
    conflict_reason: str | None = None
    combined_spec: str = ""


@dataclass
class CondaResult:
    """Outcome of looking a package up in the configured conda channels."""

    version: str | None
    message: str
    found: bool = False  # the package exists in at least one channel
    satisfied: bool = False  # some available version matches the constraints
    checked: bool = True  # False when the lookup never ran

    @property
    def missing(self) -> bool:
        return self.checked and not self.found


# ---------------------------------------------------------------------------
# HTTP layer: cached, retried, gzip-aware
# ---------------------------------------------------------------------------

_http_cache: dict[str, Any] = {}
_http_cache_lock = threading.Lock()
_url_locks: dict[str, threading.Lock] = {}


def _lock_for(url: str) -> threading.Lock:
    with _http_cache_lock:
        return _url_locks.setdefault(url, threading.Lock())


def _build_request(url: str) -> urllib.request.Request:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept-Encoding", "gzip")
    host = urllib.parse.urlsplit(url).hostname or ""
    token = os.environ.get("GITHUB_TOKEN")
    if token and (host == "github.com" or host.endswith((".github.com", ".githubusercontent.com"))):
        req.add_header("Authorization", f"Bearer {token}")
    return req


def _read_body(response: Any) -> bytes:
    body = response.read()
    if response.headers.get("Content-Encoding") == "gzip":
        try:
            return gzip.decompress(body)
        except OSError:
            return body
    return body


def _http_fetch(url: str, timeout: int) -> bytes | object | None:
    """One attempt chain. Returns bytes, None (absent/error), or _TIMEOUT."""
    delay = 0.5
    for attempt in range(HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(_build_request(url), timeout=timeout) as r:
                return _read_body(r)
        except urllib.error.HTTPError as e:
            # Must come before URLError: HTTPError is a subclass of it.
            if e.code in (429, 500, 502, 503, 504) and attempt < HTTP_RETRIES:
                logger.debug("HTTP %s, retrying: %s", e.code, url)
                time.sleep(delay)
                delay *= 2
                continue
            if e.code != 404:
                logger.debug("HTTP %s: %s", e.code, url)
            return None
        except (socket.timeout, TimeoutError, urllib.error.URLError) as e:
            if attempt < HTTP_RETRIES:
                logger.debug("Timeout/URL error, retrying: %s (%s)", url, e)
                time.sleep(delay)
                delay *= 2
                continue
            logger.debug("Unreachable after %d attempts: %s", attempt + 1, url)
            return _TIMEOUT
        except Exception as e:  # noqa: BLE001 - never let one URL kill the run
            logger.debug("Request failed: %s — %s", url, e)
            return None
    return None


def _http_get(
    url: str, timeout: int | None = None, cache: bool = True
) -> bytes | object | None:
    """GET with a process-wide cache so each URL is fetched at most once.

    Timeouts are cached too: an unreachable channel should cost one timeout,
    not one per package. Callers that only need a small digest of a large
    response (repodata, PyPI metadata) pass cache=False and memoize that digest
    instead, which keeps peak memory flat.
    """
    if not cache:
        return _http_fetch(url, timeout if timeout is not None else DEFAULT_TIMEOUT)

    with _http_cache_lock:
        if url in _http_cache:
            return _http_cache[url]

    with _lock_for(url):  # collapse concurrent requests for the same URL
        with _http_cache_lock:
            if url in _http_cache:
                return _http_cache[url]
        result = _http_fetch(url, timeout if timeout is not None else DEFAULT_TIMEOUT)
        with _http_cache_lock:
            _http_cache[url] = result
        return result


def _http_json(
    url: str, timeout: int | None = None, cache: bool = True
) -> Any | object | None:
    data = _http_get(url, timeout, cache)
    if data is _TIMEOUT or not data:
        return data if data is _TIMEOUT else None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug("Invalid JSON from %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Source fetchers
# ---------------------------------------------------------------------------


def fetch_local_file(path: Path | str) -> str | None:
    try:
        return Path(path).read_text()
    except OSError as e:
        logger.error("FAILED local read -> %s (%s)", path, e)
        return None


def fetch_github_raw(owner: str, repo: str, ref: str, path: str) -> str | None:
    url = RAW_URL.format(owner=owner, repo=repo, ref=ref, path=path)
    logger.info("FETCH -> %s", url)
    data = _http_get(url)
    if data is _TIMEOUT or not data:
        logger.error("FAILED -> %s", url)
        return None
    return data.decode("utf-8", errors="replace")


def latest_goats_release() -> str | None:
    logger.info("Resolving latest GOATS release...")
    payload = _http_json(GITHUB_LATEST_RELEASE.format(owner=GOATS_REPO[0], repo=GOATS_REPO[1]))
    if payload is _TIMEOUT or not isinstance(payload, dict):
        return None
    return payload.get("tag_name")


_pypi_cache: dict[tuple[str, str | None], list[str]] = {}
_pypi_cache_lock = threading.Lock()


def fetch_pypi_requires(package: str, version: str | None = None) -> list[str]:
    """Return the `requires_dist` list for a package (empty when unavailable).

    Only the requirement list is kept; PyPI metadata documents are large and
    holding them all would dominate memory on a deep run.
    """
    key = (package.lower(), version)
    with _pypi_cache_lock:
        if key in _pypi_cache:
            return _pypi_cache[key]

    url = (
        PYPI_URL.format(package=package, version=version)
        if version
        else PYPI_URL_LATEST.format(package=package)
    )
    payload = _http_json(url, cache=False)
    if payload is _TIMEOUT or not isinstance(payload, dict):
        # A pinned version may not exist on PyPI (e.g. conda-only builds);
        # fall back to the latest release rather than losing the subtree.
        if version:
            logger.debug("PyPI has no %s==%s, falling back to latest", package, version)
            requires = fetch_pypi_requires(package)
        else:
            requires = []
    else:
        requires = payload.get("info", {}).get("requires_dist") or []

    with _pypi_cache_lock:
        _pypi_cache[key] = requires
    return requires


# ---------------------------------------------------------------------------
# Conda channel lookups
# ---------------------------------------------------------------------------


def _fetch_anaconda_versions(package: str, channel: str) -> list[str] | object:
    # cache=False: the response lists every file of every build, and
    # fetch_conda_versions() already memoizes the version list we distill here.
    payload = _http_json(ANACONDA_URL.format(channel=channel, package=package), cache=False)
    if payload is _TIMEOUT:
        return _TIMEOUT
    if not isinstance(payload, dict):
        return []
    return payload.get("versions", [])


@functools.lru_cache(maxsize=None)
def _repodata_index(repodata_url: str) -> Any:
    """Parse a repodata.json once into {package_name: {versions}}.

    The previous implementation re-downloaded and re-scanned the whole file for
    every package and name variant, which dominated the runtime.
    """
    payload = _http_json(repodata_url, cache=False)
    if payload is _TIMEOUT:
        return _TIMEOUT
    if not isinstance(payload, dict):
        return {}
    index: dict[str, set[str]] = {}
    for section in ("packages", "packages.conda"):
        for info in payload.get(section, {}).values():
            name = str(info.get("name", "")).lower()
            version = info.get("version")
            if name and version:
                index.setdefault(name, set()).add(str(version))
    return index


def _fetch_gemini_versions(package: str, repodata_url: str) -> set[str] | object:
    index = _repodata_index(repodata_url)
    if index is _TIMEOUT:
        return _TIMEOUT
    return set(index.get(package.lower(), set()))


def _conda_name_variants(package: str) -> list[str]:
    """Candidate conda names, most likely first."""
    name = PACKAGE_NAME_MAP.get(package.lower(), package.lower())
    variants = [name]
    swapped = name.replace("-", "_") if "-" in name else name.replace("_", "-")
    if swapped != name:
        variants.append(swapped)
    return variants


ChannelTask = tuple[Callable[[str, str], Any], str]


def _fetch_channel_group(
    name: str, tasks: list[ChannelTask], pool: ThreadPoolExecutor
) -> tuple[set[str], bool]:
    """Run a group of channel lookups. Returns (versions, had_timeout)."""
    versions: set[str] = set()
    had_timeout = False
    if not tasks:
        return versions, had_timeout
    futures = [pool.submit(fn, name, arg) for fn, arg in tasks]
    for future in as_completed(futures):
        try:
            result = future.result()
        except Exception as e:  # noqa: BLE001
            logger.debug("Channel lookup failed for '%s': %s", name, e)
            continue
        if result is _TIMEOUT:
            had_timeout = True
        elif result:
            versions.update(result)
    return versions, had_timeout


def _parse_versions(package: str, raw: Iterable[str]) -> list[str]:
    """Keep only PEP 440-parseable versions, newest first.

    Conda channels occasionally expose odd version strings; dropping those is
    better than failing the whole package.
    """
    parsed: list[Version] = []
    for v in raw:
        try:
            parsed.append(Version(v))
        except InvalidVersion:
            logger.debug("Skipping unparseable conda version for '%s': %s", package, v)
    return [str(v) for v in sorted(parsed, reverse=True)]


_conda_versions_cache: dict[str, list[str]] = {}
_conda_versions_lock = threading.Lock()


def fetch_conda_versions(package: str, pool: ThreadPoolExecutor | None = None) -> list[str]:
    """Fetch available conda versions with channel priority.

      1. conda-forge (fastest, most packages)
      2. fallback channels (astroconda, defaults, Gemini) — only if needed

    Results are cached per package for the lifetime of the process.
    """
    key = package.lower()
    with _conda_versions_lock:
        if key in _conda_versions_cache:
            return _conda_versions_cache[key]

    owns_pool = pool is None
    pool = pool or ThreadPoolExecutor(max_workers=8)
    try:
        all_versions: set[str] = set()
        had_timeout = False

        for name in _conda_name_variants(package):
            primary, primary_timeout = _fetch_channel_group(
                name, [(_fetch_anaconda_versions, PRIMARY_CHANNEL)], pool
            )
            had_timeout = had_timeout or primary_timeout
            if primary:
                all_versions.update(primary)
                logger.debug("'%s' found in %s, skipping fallbacks", name, PRIMARY_CHANNEL)
                continue

            logger.debug("'%s' not in %s, trying fallback channels", name, PRIMARY_CHANNEL)
            fallback_tasks: list[ChannelTask] = [
                (_fetch_anaconda_versions, ch)
                for ch in CONDA_CHANNELS
                if ch != PRIMARY_CHANNEL
            ] + [(_fetch_gemini_versions, url) for url in GEMINI_REPODATA_URLS]
            fallback, fallback_timeout = _fetch_channel_group(name, fallback_tasks, pool)
            had_timeout = had_timeout or fallback_timeout
            all_versions.update(fallback)
    finally:
        if owns_pool:
            pool.shutdown(wait=True)

    if not all_versions and had_timeout:
        logger.warning(
            "All conda channels timed out for '%s' — result may be incomplete", package
        )

    versions = _parse_versions(package, all_versions)
    with _conda_versions_lock:
        _conda_versions_cache[key] = versions
    return versions


def _safe_specifier(spec: str) -> SpecifierSet | None:
    try:
        return SpecifierSet(spec)
    except InvalidSpecifier:
        logger.debug("Invalid specifier, ignoring: %s", spec)
        return None


def best_conda_match(
    package: str, spec: str, pool: ThreadPoolExecutor | None = None
) -> CondaResult:
    """Pick the newest conda version satisfying `spec`."""
    versions = fetch_conda_versions(package, pool)
    if not versions:
        return CondaResult(None, "not found in any conda channel", found=False)

    if not spec:
        return CondaResult(
            versions[0], f"no constraints -> latest {versions[0]}", found=True, satisfied=True
        )

    specifier = _safe_specifier(spec)
    if specifier is None:
        return CondaResult(
            versions[0],
            f"unparseable constraint '{spec}' -> latest {versions[0]}",
            found=True,
            satisfied=True,
        )

    matching = list(specifier.filter(versions))
    prerelease_only = False
    if not matching:
        matching = list(specifier.filter(versions, prereleases=True))
        prerelease_only = bool(matching)

    if not matching:
        return CondaResult(
            None,
            f"no conda version satisfies {spec} "
            f"(available: {versions[-1]} ... {versions[0]})",
            found=True,
            satisfied=False,
        )

    best = matching[0]
    if prerelease_only:
        message = f"would install prerelease {best} (only match for {spec})"
    elif best != versions[0]:
        message = f"would install {best} (latest is {versions[0]}, constrained by {spec})"
    else:
        message = f"would install {best} (latest, satisfies {spec})"
    return CondaResult(best, message, found=True, satisfied=True)


# ---------------------------------------------------------------------------
# Dependency parsing
# ---------------------------------------------------------------------------


def _load_toml(text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        logger.error("Invalid pyproject.toml: %s", e)
        return {}


def parse_pyproject(text: str) -> list[str]:
    return _load_toml(text).get("project", {}).get("dependencies", []) or []


def parse_uv_git_pins(text: str) -> dict[str, str]:
    """Versions implied by `[tool.uv.sources]` git tags.

    GOATS declares DRAGONS as a bare dependency and pins the actual version via
    a git tag, so the tag is the only version information in pyproject.toml.
    """
    sources = _load_toml(text).get("tool", {}).get("uv", {}).get("sources", {})
    pins: dict[str, str] = {}
    for name, spec in sources.items():
        if isinstance(spec, dict) and isinstance(spec.get("tag"), str):
            pins[name.lower()] = spec["tag"].lstrip("vV")
    return pins


_PEP440_OPS = ("===", "==", "!=", "~=", ">=", "<=", ">", "<")
_CONDA_ENTRY_RE = re.compile(r"^(?P<name>[A-Za-z0-9._+-]+)\s*(?P<rest>.*)$")


def conda_spec_to_pep440(entry: str) -> str | None:
    """Convert a conda dependency line into a PEP 440 requirement string.

    conda uses a single `=` for pinning and may append a build string, so
    `numpy=1.26=py312h1234` must become `numpy==1.26`. Naively rewriting the
    first `=` corrupts `numpy>=1.20` into `numpy>==1.20`.
    """
    entry = entry.split("#", 1)[0].strip()
    if not entry:
        return None
    if "::" in entry:  # channel::package
        entry = entry.split("::", 1)[-1].strip()

    match = _CONDA_ENTRY_RE.match(entry)
    if not match:
        return None
    name, rest = match.group("name"), match.group("rest").strip()
    if not rest:
        return name
    if rest.startswith(_PEP440_OPS):
        return f"{name}{rest}"
    if rest.startswith("="):
        version = rest.lstrip("=").split("=", 1)[0].strip()
        return f"{name}=={version}" if version else name
    if rest[0].isdigit():  # "numpy 1.26.*"
        return f"{name}=={rest.split()[0]}"
    return name


def parse_ci_environment(text: str) -> list[str]:
    """Extract requirement strings from a conda environment YAML."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        logger.error("Invalid environment YAML: %s", e)
        return []
    if not isinstance(data, dict):
        return []

    out: list[str] = []
    for entry in data.get("dependencies") or []:
        if isinstance(entry, str):
            converted = conda_spec_to_pep440(entry)
            if converted:
                out.append(converted)
        elif isinstance(entry, dict):
            for pip_dep in entry.get("pip") or []:
                if isinstance(pip_dep, str) and not pip_dep.startswith("-"):
                    out.append(pip_dep)
    return out


def parse_requirements(deps: Iterable[str]) -> list[SpecSource]:
    """Parse requirement strings, dropping those excluded by their markers."""
    result: list[SpecSource] = []
    for dep in deps:
        try:
            req = Requirement(dep)
        except InvalidRequirement:
            logger.debug("Could not parse requirement: %s", dep)
            continue
        if req.marker is not None:
            try:
                if not req.marker.evaluate(PYTHON_ENVIRONMENT):
                    continue
            except Exception as e:  # noqa: BLE001 - undefined markers, extras...
                logger.debug("Could not evaluate marker for '%s': %s", dep, e)
        result.append(
            (req.name.lower(), str(req.specifier), str(req.marker) if req.marker else None)
        )
    return result


def build_source_dict(parsed: list[SpecSource], source: str) -> dict[str, list[SpecSource]]:
    result: dict[str, list[SpecSource]] = {}
    for name, spec, marker in parsed:
        result.setdefault(name, []).append((spec, source, marker))
    return result


def get_pinned_version(
    d: dict[str, list[SpecSource]], pkg: str
) -> tuple[str | None, str | None, str | None]:
    """Return the first `==` pin for a package, if any."""
    for spec, source, marker in d.get(pkg, []):
        specifier = _safe_specifier(spec)
        if specifier is None:
            continue
        for s in specifier:
            if s.operator in ("==", "===") and "*" not in s.version:
                return s.version, source, marker
    return None, None, None


# ---------------------------------------------------------------------------
# Transitive resolution (breadth-first, parallel, shared cache)
# ---------------------------------------------------------------------------


def resolve_transitive(
    roots: list[tuple[str, str | None]],
    max_depth: int,
    workers: int = DEFAULT_WORKERS,
) -> list[tuple[str, str]]:
    """Expand the dependency tree breadth-first via PyPI.

    Returns (parent_package, requirement_string) pairs so the caller can build
    edges between the real parent and child rather than attributing every
    transitive dependency to the top-level package.

    Breadth-first with one shared `seen` set means each package is fetched once
    and is always reached at its shallowest depth; the previous depth-first walk
    re-fetched packages and pruned subtrees depending on traversal order.
    """
    if max_depth <= 0:
        return []

    edges: list[tuple[str, str]] = []
    seen: set[str] = set()
    frontier = [(name.lower(), version) for name, version in roots]
    seen.update(name for name, _ in frontier)

    for depth in range(max_depth):
        if not frontier:
            break
        logger.info("[depth %d] Resolving %d package(s)...", depth, len(frontier))

        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(frontier)))) as pool:
            futures = {
                pool.submit(fetch_pypi_requires, name, version): name
                for name, version in frontier
            }
            results: dict[str, list[str]] = {}
            for future in as_completed(futures):
                parent = futures[future]
                try:
                    results[parent] = future.result()
                except Exception as e:  # noqa: BLE001
                    logger.debug("PyPI lookup failed for %s: %s", parent, e)
                    results[parent] = []

        next_frontier: list[tuple[str, str | None]] = []
        for parent, deps in results.items():
            # Markers are evaluated here so we never spend a request resolving a
            # dependency that does not apply to the target environment.
            for name, spec, _marker in parse_requirements(deps):
                edges.append((parent, f"{name}{spec}"))
                if name in seen:
                    continue
                seen.add(name)
                specifier = _safe_specifier(spec)
                pinned = next(
                    (s.version for s in specifier or () if s.operator == "=="), None
                )
                next_frontier.append((name, pinned))
        frontier = next_frontier

    return edges


# ---------------------------------------------------------------------------
# Intersection analysis
# ---------------------------------------------------------------------------


def _bump(version: str, index: int) -> str:
    """Increment release segment `index`, zeroing the ones after it."""
    parts = list(Version(version).release)
    while len(parts) <= index:
        parts.append(0)
    parts = parts[: index + 1]
    parts[index] += 1
    return ".".join(str(p) for p in parts)


def normalize_specifier(operator: str, version: str) -> list[tuple[str, str]]:
    """Expand a specifier into plain (operator, version) bounds.

    `~=` and `==X.Y.*` were previously dropped on the floor, so compatible-release
    pins contributed no bounds at all.
    """
    if operator == "===":
        return [("==", version)]
    if operator == "~=":
        try:
            release = Version(version).release
            if len(release) < 2:
                return [(">=", version)]
            return [(">=", version), ("<", _bump(version, len(release) - 2))]
        except InvalidVersion:
            return [(">=", version)]
    if operator in ("==", "!=") and version.endswith(".*"):
        base = version[:-2]
        try:
            if operator == "==":
                return [(">=", base), ("<", _bump(base, len(Version(base).release) - 1))]
        except InvalidVersion:
            return []
        return []  # `!=X.Y.*` constrains nothing we model
    return [(operator, version)]


def find_intersections(
    global_dict: dict[str, list[SpecSource]],
) -> dict[str, PackageInfo]:
    intersections: dict[str, PackageInfo] = {}

    for pkg, spec_sources in global_dict.items():
        if not spec_sources:
            continue

        # Deduplicate by (spec, source)
        seen_keys: set[tuple[str, str]] = set()
        deduped = [
            item
            for item in spec_sources
            if (key := (item[0], item[1])) not in seen_keys and not seen_keys.add(key)
        ]

        lower_bounds: list[Bound] = []
        upper_bounds: list[Bound] = []
        pinned: list[tuple[str, str, str | None]] = []
        excluded: list[tuple[str, str, str | None]] = []
        spec_parts: list[str] = []

        for spec, source, marker in deduped:
            specifier = _safe_specifier(spec)
            if specifier is None:
                continue
            spec_parts.extend(str(s) for s in specifier)
            for s in specifier:
                for op, version in normalize_specifier(s.operator, s.version):
                    if op == "==":
                        pinned.append((version, source, marker))
                    elif op == "!=":
                        excluded.append((version, source, marker))
                    elif op in (">=", ">"):
                        lower_bounds.append((op, version, source, marker))
                    elif op in ("<=", "<"):
                        upper_bounds.append((op, version, source, marker))

        lower_bound = _tightest(lower_bounds, max)
        upper_bound = _tightest(upper_bounds, min)

        info = PackageInfo(
            spec_sources=deduped,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            pinned=pinned,
            excluded=excluded,
            combined_spec=",".join(sorted(set(spec_parts))),
        )
        info.has_conflict, info.conflict_reason = _detect_conflict(info)
        intersections[pkg] = info

    return intersections


def _tightest(bounds: list[Bound], pick: Callable[..., Bound]) -> Bound | None:
    if not bounds:
        return None
    try:
        return pick(bounds, key=lambda b: Version(b[1]))
    except InvalidVersion:
        return bounds[0]


def _detect_conflict(info: PackageInfo) -> tuple[bool, str | None]:
    """Contradictory pins, or a pin that falls outside the declared bounds."""
    distinct = {v for v, _, _ in info.pinned}
    if len(distinct) > 1:
        return True, "Pinned to multiple versions: " + ", ".join(
            f"{v} (from {s})" for v, s, _ in info.pinned
        )

    if distinct:
        pin = next(iter(distinct))
        for bound in (info.lower_bound, info.upper_bound):
            if not bound:
                continue
            try:
                if not SpecifierSet(f"{bound[0]}{bound[1]}").contains(pin, prereleases=True):
                    return True, (
                        f"Pin =={pin} (from {info.pinned[0][1]}) violates "
                        f"{bound[0]}{bound[1]} (from {bound[2]})"
                    )
            except (InvalidSpecifier, InvalidVersion):
                continue
        if any(v == pin for v, _, _ in info.excluded):
            return True, f"Pin =={pin} is explicitly excluded by a != constraint"

    return False, None


def is_range_valid(lower: Bound | None, upper: Bound | None) -> bool:
    """True when some version can satisfy both bounds."""
    if not lower or not upper:
        return True
    try:
        lv, uv = Version(lower[1]), Version(upper[1])
    except InvalidVersion:
        return True
    if lv < uv:
        return True
    if lv > uv:
        return False
    # Equal versions: only `>=x,<=x` leaves a satisfiable point.
    return lower[0] == ">=" and upper[0] == "<="


# ---------------------------------------------------------------------------
# Conda availability for the whole set
# ---------------------------------------------------------------------------


def build_conda_results(
    intersections: dict[str, PackageInfo], workers: int = DEFAULT_WORKERS
) -> dict[str, CondaResult]:
    """Look every package up in conda, in parallel.

    Two independent pools: package lookups never wait on a slot held by the
    channel requests they spawn, so nested submissions cannot deadlock.
    """
    results: dict[str, CondaResult] = {}
    if not intersections:
        return results

    channel_pool = ThreadPoolExecutor(max_workers=max(8, workers * 2))
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(intersections)))) as pool:
            futures = {
                pool.submit(best_conda_match, pkg, info.combined_spec, channel_pool): pkg
                for pkg, info in intersections.items()
            }
            for future in as_completed(futures):
                pkg = futures[future]
                try:
                    results[pkg] = future.result()
                except Exception as e:  # noqa: BLE001
                    logger.debug("conda lookup failed for %s: %s", pkg, e)
                    results[pkg] = CondaResult(None, f"error: {e}")
    finally:
        channel_pool.shutdown(wait=True)
    return results


NOT_CHECKED = CondaResult(None, "not checked", checked=False)


def classify_status(info: PackageInfo, conda: CondaResult) -> tuple[str, str | None]:
    """Return (status, issue) for a package."""
    if info.has_conflict:
        return "conflict", info.conflict_reason

    if not is_range_valid(info.lower_bound, info.upper_bound):
        lb, ub = info.lower_bound, info.upper_bound
        issue = f"Impossible range: {lb[0]}{lb[1]} AND {ub[0]}{ub[1]}" if lb and ub else None
        return "invalid_range", issue

    has_bounds = bool(info.lower_bound or info.upper_bound or info.pinned)
    if has_bounds and conda.checked and not conda.satisfied:
        return "conda_conflict", conda.message

    return "ok", None


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------


def _fmt_marker(marker: str | None) -> str:
    return colored(f" [{marker}]", Color.DIM) if marker else ""


def _print_package(pkg: str, info: PackageInfo, status: str, conda: CondaResult) -> None:
    scol = Color.RED if status in CONFLICT_STATUSES else Color.GREEN
    print(
        f"{colored(f'[{status.upper()}]', scol, bold=True)} "
        f"{colored(pkg, Color.CYAN, bold=True)}"
    )

    print("  Requirements:")
    for spec, source, marker in info.spec_sources:
        c = SOURCE_COLOR.get(source, Color.YELLOW)
        shown = spec or "(any)"
        print(f"    · {colored(shown, c)} (from {colored(source.upper(), c)}){_fmt_marker(marker)}")

    if info.pinned:
        if info.has_conflict:
            print("  Pinned versions (CONFLICT):")
            for v, s, m in info.pinned:
                c = SOURCE_COLOR.get(s, Color.YELLOW)
                print(
                    f"    · {colored(v, Color.RED, bold=True)} "
                    f"(from {colored(s.upper(), c)}){_fmt_marker(m)}"
                )
        else:
            v, s, m = info.pinned[0]
            c = SOURCE_COLOR.get(s, Color.YELLOW)
            print(
                f"  Pinned: {colored(v, c, bold=True)} "
                f"(from {colored(s.upper(), c)}){_fmt_marker(m)}"
            )

    if info.lower_bound or info.upper_bound:
        print("  Version bounds:")
        for label, b in (("Lower", info.lower_bound), ("Upper", info.upper_bound)):
            if b:
                c = SOURCE_COLOR.get(b[2], Color.YELLOW)
                print(f"    {label}: {colored(b[0] + b[1], c)} (from {colored(b[2].upper(), c)})")
        if info.lower_bound and info.upper_bound:
            valid_rng = is_range_valid(info.lower_bound, info.upper_bound)
            rng = f"{info.lower_bound[1]} -> {info.upper_bound[1]}"
            print(
                f"  Range: "
                f"{colored(rng, Color.GREEN if valid_rng else Color.RED, bold=not valid_rng)}"
            )

    print(f"  Conda: {colored(conda.message, Color.GREEN if conda.version else Color.RED)}")
    print()


def print_analysis(
    intersections: dict[str, PackageInfo],
    goats_ref: str,
    max_depth: int,
    workers: int = DEFAULT_WORKERS,
) -> int:
    """Print the analysis and return the number of conflicting packages."""
    title = "DEPENDENCY RESOLUTION ANALYSIS"
    if max_depth:
        title += f" (transitive depth: {max_depth})"

    print(colored("Fetching conda availability...", Color.DIM), end="\r", file=sys.stderr, flush=True)
    conda_results = build_conda_results(intersections, workers)
    print(" " * 50, end="\r", file=sys.stderr, flush=True)

    # Classify once; reused by the detail loop and the summary tally.
    statuses: dict[str, tuple[str, str | None]] = {}
    conflicts: dict[str, str | None] = {}
    ok_count = 0
    not_in_conda: list[str] = []

    for pkg, info in sorted(intersections.items()):
        conda = conda_results.get(pkg, NOT_CHECKED)
        status, issue = classify_status(info, conda)
        statuses[pkg] = (status, issue)
        if status in CONFLICT_STATUSES:
            conflicts[pkg] = issue
        else:
            ok_count += 1
        if conda.missing:
            not_in_conda.append(pkg)

    sep = "=" * 120
    print(f"\n{sep}")
    print(colored(title, Color.BLUE, bold=True))
    print(f"{sep}\n")

    for pkg, info in sorted(intersections.items()):
        _print_package(pkg, info, statuses[pkg][0], conda_results.get(pkg, NOT_CHECKED))

    print(sep)
    print(colored("SUMMARY", Color.BLUE, bold=True))
    print(sep)
    print(f"Total packages analyzed: {len(intersections)}")
    print(f"  {colored(f'{ok_count} OK', Color.GREEN, bold=True)}")
    print(f"  {colored(f'{len(conflicts)} conflicts', Color.RED, bold=True)}")
    print(
        f"  {colored(f'{len(not_in_conda)} not in any conda channel', Color.YELLOW, bold=True)}"
    )
    print(f"\nGOATS:  {colored(goats_ref, Color.CYAN, bold=True)}")
    print(f"Python: {colored(PYTHON_VERSION, Color.CYAN, bold=True)}")
    print(f"Depth:  {colored(str(max_depth), Color.CYAN, bold=True)}")
    print()

    if conflicts:
        print(colored("CONFLICTS:", Color.RED, bold=True))
        print("-" * 120)
        for pkg, issue in sorted(conflicts.items()):
            print(f"\n  {colored(pkg, Color.RED, bold=True)}")
            if issue:
                print(f"  Issue: {issue}")
        print()

    if not_in_conda:
        print(colored("NOT IN ANY CONDA CHANNEL:", Color.YELLOW, bold=True))
        print("-" * 120)
        for pkg in sorted(not_in_conda):
            specs = ", ".join(
                f"{sp or '(any)'} (from {src})"
                for sp, src, _ in intersections[pkg].spec_sources
            )
            print(f"  {colored(pkg, Color.YELLOW, bold=True)}: {colored(specs, Color.DIM)}")
        print()

    if not conflicts and not not_in_conda:
        print(
            colored(
                "All dependencies compatible and available in conda!",
                Color.GREEN,
                bold=True,
            )
        )

    print(f"{sep}\n")
    return len(conflicts)


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def _bound_str(b: Bound | None) -> str | None:
    return f"{b[0]}{b[1]}" if b else None


def build_export(
    intersections: dict[str, PackageInfo],
    global_dict: dict[str, list[SpecSource]],
    goats_ref: str,
    workers: int = DEFAULT_WORKERS,
) -> dict[str, Any]:
    print("Fetching conda availability...", file=sys.stderr, flush=True)
    conda_results = build_conda_results(intersections, workers)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    # Only emit root nodes for sources that actually contributed specs
    # (JDAViz is optional and may be absent).
    active_sources = {
        src for specs in global_dict.values() for _, src, _ in specs if src in SOURCE_IDS
    }

    for sid in sorted(SOURCE_IDS & active_sources):
        nodes.append(
            {
                "id": sid,
                "label": sid,
                "status": "source",
                "issue": None,
                "sources": [],
                "specs": [],
                "lower_bound": None,
                "upper_bound": None,
            }
        )

    # GOATS -> TOMToolkit / DRAGONS / JDAViz edges
    for pkg in ("tomtoolkit", "dragons", "jdaviz"):
        if pkg not in active_sources:
            continue
        for spec, src, _ in global_dict.get(pkg, []):
            key = (src, pkg)
            if src in SOURCE_IDS and src != pkg and key not in seen_edges:
                seen_edges.add(key)
                edges.append({"source": src, "target": pkg, "label": spec, "conflict": False})

    package_count = 0
    for pkg, info in intersections.items():
        if pkg in SOURCE_IDS:
            continue
        package_count += 1

        conda = conda_results.get(pkg, NOT_CHECKED)
        status, issue = classify_status(info, conda)

        nodes.append(
            {
                "id": pkg,
                "label": pkg,
                "status": status,
                "issue": issue,
                "sources": sorted({src for _, src, _ in info.spec_sources}),
                "specs": [{"spec": sp, "from": src} for sp, src, _ in info.spec_sources],
                "lower_bound": _bound_str(info.lower_bound),
                "upper_bound": _bound_str(info.upper_bound),
                "conda_version": conda.version,
                "conda_status": conda.message,
            }
        )

        for spec, src, _ in info.spec_sources:
            key = (src, pkg)
            if key not in seen_edges and (src in SOURCE_IDS or src in intersections):
                seen_edges.add(key)
                edges.append(
                    {
                        "source": src,
                        "target": pkg,
                        "label": spec,
                        "conflict": status in CONFLICT_STATUSES,
                    }
                )

    return {
        "goats_version": goats_ref,
        "python_version": PYTHON_VERSION,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total": package_count,
            "conflicts": sum(1 for n in nodes if n["status"] in CONFLICT_STATUSES),
            "ok": sum(1 for n in nodes if n["status"] == "ok"),
            "not_in_conda": sum(
                1 for pkg, c in conda_results.items() if c.missing and pkg not in SOURCE_IDS
            ),
        },
    }


def export_json(
    intersections: dict[str, PackageInfo],
    global_dict: dict[str, list[SpecSource]],
    goats_ref: str,
    workers: int = DEFAULT_WORKERS,
) -> int:
    """Print the graph JSON and return the number of conflicting packages."""
    result = build_export(intersections, global_dict, goats_ref, workers)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return result["summary"]["conflicts"]


def serve_viewer(
    intersections: dict[str, PackageInfo],
    global_dict: dict[str, list[SpecSource]],
    goats_ref: str,
    workers: int = DEFAULT_WORKERS,
    open_browser: bool = True,
) -> int:
    """Write the graph JSON next to interactive.html, serve it locally, open a browser.

    Returns the number of conflicting packages.
    """
    import http.server
    import webbrowser

    here = Path(__file__).resolve().parent
    if not (here / "interactive.html").exists():
        die(f"interactive.html not found next to the script ({here})")

    data_name = "viewer_data.json"
    result = build_export(intersections, global_dict, goats_ref, workers)
    (here / data_name).write_text(json.dumps(result, indent=2))
    logger.info("Wrote %s", here / data_name)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("viewer: " + fmt, *args)

    handler = functools.partial(QuietHandler, directory=str(here))
    # Port 0 -> let the OS pick a free port. Bound to loopback only.
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/interactive.html?data={data_name}"

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(colored(f"\nViewer:  {url}", Color.GREEN, bold=True), file=sys.stderr)
    print(colored("Serving locally — press Ctrl+C to stop.", Color.DIM), file=sys.stderr)
    if open_browser:
        webbrowser.open(url)

    try:
        threading.Event().wait()  # block until interrupted
    except KeyboardInterrupt:
        print(colored("\nStopped.", Color.DIM), file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()

    return result["summary"]["conflicts"]


# ---------------------------------------------------------------------------
# Source collection
# ---------------------------------------------------------------------------


def _fetch_dragons_deps(version: str) -> list[str]:
    """DRAGONS moved from setup.py to pyproject.toml; support both."""
    setup = fetch_github_raw(*DRAGONS_REPO, f"v{version}", "setup.py")
    if setup:
        m = re.search(r"install_requires\s*=\s*\[(.*?)\]", setup, re.DOTALL)
        if m:
            deps = [d.strip() for d in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if d.strip()]
            if deps:
                return deps

    pyproject = fetch_github_raw(*DRAGONS_REPO, f"v{version}", "pyproject.toml")
    if pyproject:
        logger.info("DRAGONS: using pyproject.toml")
        return parse_pyproject(pyproject)

    logger.warning("DRAGONS v%s: no dependency metadata found", version)
    return []


def collect_goats_deps(
    goats_ref: str, goats_path: str | None
) -> tuple[list[str], dict[str, str]]:
    """Return (requirement strings, versions pinned via uv git tags)."""
    if goats_path:
        root = Path(goats_path)
        pyproject = fetch_local_file(root / "pyproject.toml")
        ci = fetch_local_file(root / "ci_environment.yaml")
    else:
        pyproject = fetch_github_raw(*GOATS_REPO, goats_ref, "pyproject.toml")
        ci = fetch_github_raw(*GOATS_REPO, goats_ref, "ci_environment.yaml")

    if not pyproject:
        die("Could not fetch GOATS pyproject.toml")
    deps = parse_pyproject(pyproject) + (parse_ci_environment(ci) if ci else [])
    return deps, parse_uv_git_pins(pyproject)


def collect_sources(goats_ref: str, goats_path: str | None) -> dict[str, list[SpecSource]]:
    """Merge the dependency declarations of every upstream project."""
    goats_deps, uv_pins = collect_goats_deps(goats_ref, goats_path)
    goats_dict = build_source_dict(parse_requirements(goats_deps), "goats")

    def upstream_version(name: str) -> str | None:
        return get_pinned_version(goats_dict, name)[0] or uv_pins.get(name)

    tomtoolkit_version = upstream_version("tomtoolkit")
    dragons_version = upstream_version("dragons")
    jdaviz_version = upstream_version("jdaviz")
    logger.info(
        "TOMToolkit: %s | DRAGONS: %s | JDAViz: %s",
        tomtoolkit_version,
        dragons_version,
        jdaviz_version,
    )
    if not tomtoolkit_version or not dragons_version:
        die("Could not determine TOMToolkit or DRAGONS versions from GOATS metadata")

    tom_py = fetch_github_raw(*TOMTOOLKIT_REPO, tomtoolkit_version, "pyproject.toml")
    if not tom_py:
        die(f"Could not fetch TOMToolkit pyproject.toml for {tomtoolkit_version}")
    tom_dict = build_source_dict(parse_requirements(parse_pyproject(tom_py)), "tomtoolkit")

    dragons_dict = build_source_dict(
        parse_requirements(_fetch_dragons_deps(dragons_version)), "dragons"
    )

    jdaviz_dict: dict[str, list[SpecSource]] = {}
    if jdaviz_version:
        jdaviz_py = fetch_github_raw(*JDAVIZ_REPO, f"v{jdaviz_version}", "pyproject.toml")
        if jdaviz_py:
            jdaviz_dict = build_source_dict(
                parse_requirements(parse_pyproject(jdaviz_py)), "jdaviz"
            )
        else:
            logger.warning("Could not fetch JDAViz pyproject.toml — skipping JDAViz")
    else:
        logger.info("JDAViz not pinned by GOATS — skipping")

    global_dict: dict[str, list[SpecSource]] = {}
    for d in (goats_dict, tom_dict, dragons_dict, jdaviz_dict):
        for k, v in d.items():
            global_dict.setdefault(k, []).extend(v)
    return global_dict


def add_transitive_deps(
    global_dict: dict[str, list[SpecSource]], max_depth: int, workers: int
) -> int:
    """Expand `global_dict` with transitive deps. Returns how many were added."""
    roots = [(pkg, get_pinned_version(global_dict, pkg)[0]) for pkg in list(global_dict)]
    direct_count = len(global_dict)
    for parent, requirement in resolve_transitive(roots, max_depth, workers):
        for name, spec, marker in parse_requirements([requirement]):
            global_dict.setdefault(name, []).append((spec, parent, marker))
    return len(global_dict) - direct_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    max_depth: int = 0,
    goats_version: str | None = None,
    goats_path: str | None = None,
    verbose: bool = False,
    json_output: bool = False,
    open_viewer: bool = False,
    fail_on_conflict: bool = False,
    python_version: str = DEFAULT_PYTHON_VERSION,
    workers: int = DEFAULT_WORKERS,
) -> int:
    """Run the analysis. Returns the process exit code."""
    if verbose:
        logger.setLevel(logging.DEBUG)
    configure_python(python_version)

    goats_ref = "Local" if goats_path else (goats_version or latest_goats_release())
    if not goats_ref:
        die("Could not determine GOATS version (GitHub unreachable or rate limited)")

    if not json_output:
        print(f"\n{colored('GOATS:', Color.BLUE, bold=True)}  {colored(goats_ref, Color.CYAN, bold=True)}")
        print(f"{colored('Python:', Color.BLUE, bold=True)} {colored(python_version, Color.CYAN, bold=True)}")
        print(f"{colored('Depth:', Color.BLUE, bold=True)}  {colored(str(max_depth), Color.CYAN, bold=True)}\n")

    global_dict = collect_sources(goats_ref, goats_path)

    if max_depth > 0:
        print(
            colored(f"Resolving transitive deps (depth={max_depth})...", Color.DIM),
            file=sys.stderr,
        )
        added = add_transitive_deps(global_dict, max_depth, workers)
        print(
            colored(f"Done — {added} new packages found", Color.GREEN, bold=True),
            file=sys.stderr,
        )

    intersections = find_intersections(global_dict)

    if open_viewer:
        conflict_count = serve_viewer(intersections, global_dict, goats_ref, workers)
    elif json_output:
        conflict_count = export_json(intersections, global_dict, goats_ref, workers)
    else:
        conflict_count = print_analysis(intersections, goats_ref, max_depth, workers)

    if fail_on_conflict and conflict_count > 0:
        logger.error("%d conflicting package(s) found (--fail-on-conflict)", conflict_count)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GOATS Dependency Resolver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-v",
        "--version",
        metavar="TAG",
        help="GOATS version tag (e.g. 26.4.3). Defaults to latest release.",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=0,
        metavar="N",
        help="Transitive dependency resolution depth (default: 0).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON for the interactive viewer. All logs go to stderr.",
    )
    parser.add_argument(
        "--goats-path",
        metavar="PATH",
        help="Path to a local GOATS repository (uses its pyproject.toml instead of GitHub).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Generate the graph data and open the interactive viewer in a browser "
        "(serves locally; press Ctrl+C to stop).",
    )
    parser.add_argument(
        "--fail-on-conflict",
        action="store_true",
        help="Exit with code 2 if any version conflicts are found (for CI gating).",
    )
    parser.add_argument(
        "--python",
        default=DEFAULT_PYTHON_VERSION,
        metavar="X.Y",
        help=f"Python version used to evaluate markers (default: {DEFAULT_PYTHON_VERSION}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"Per-request network timeout (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"Parallel network workers (default: {DEFAULT_WORKERS}).",
    )
    color = parser.add_mutually_exclusive_group()
    color.add_argument("--no-color", action="store_true", help="Disable colored output.")
    color.add_argument("--color", action="store_true", help="Force colored output.")
    return parser


def cli(argv: list[str] | None = None) -> int:
    global DEFAULT_TIMEOUT

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.depth < 0:
        parser.error("--depth must be >= 0")
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.timeout < 1:
        parser.error("--timeout must be >= 1")
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", args.python):
        parser.error("--python must look like 3.12 or 3.12.1")
    if args.goats_path and not Path(args.goats_path).is_dir():
        parser.error(f"--goats-path is not a directory: {args.goats_path}")
    if args.depth > 5:
        print(
            colored("Warning: --depth > 5 may be slow", Color.YELLOW, bold=True),
            file=sys.stderr,
        )

    if args.no_color or args.json:
        configure_color(False)
    elif args.color:
        configure_color(True)

    DEFAULT_TIMEOUT = args.timeout

    return main(
        max_depth=args.depth,
        goats_version=args.version,
        goats_path=args.goats_path,
        verbose=args.verbose,
        json_output=args.json,
        open_viewer=args.open,
        fail_on_conflict=args.fail_on_conflict,
        python_version=args.python,
        workers=args.workers,
    )


if __name__ == "__main__":
    try:
        sys.exit(cli())
    except KeyboardInterrupt:
        print(colored("\nInterrupted.", Color.DIM), file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        # Downstream closed the pipe (e.g. `check_deps.py | head`).
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(141)
