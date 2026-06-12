"""
GOATS Dependency Resolver

Analyzes version compatibility between GOATS, TOMToolkit, and DRAGONS,
checks conda availability, and reports conflicts.

Usage:
    python3 check_deps.py                    # latest GOATS, direct deps
    python3 check_deps.py -v 26.4.3          # specific version
    python3 check_deps.py -d 2               # include 2 levels of transitive deps
    python3 check_deps.py --json > deps.json # export JSON for dep_graph.html
    python3 check_deps.py --open             # open the interactive viewer in a browser
    python3 check_deps.py --fail-on-conflict # exit 2 if conflicts found (CI gating)
"""

from __future__ import annotations
from pathlib import Path
import argparse
import json
import logging
import re
import socket
import sys
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, NoReturn

import yaml
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# ---------------------------------------------------------------------------
# Logging — always stderr so --json output is clean
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

CONDA_CHANNELS = ["conda-forge", "astroconda", "defaults"]
GEMINI_REPODATA_URLS = [
    "http://astroconda.gemini.edu/public/linux-64/repodata.json",
    "http://astroconda.gemini.edu/public/osx-64/repodata.json",
    "http://astroconda.gemini.edu/public/noarch/repodata.json",
]

PACKAGE_NAME_MAP: dict[str, str] = {
    "channels-redis": "channels_redis",
    "channels_redis": "channels_redis",
    "redis": "redis-server",
    "msgpack": "msgpack-python",
}

PYTHON_VERSION = "3.12"
PYTHON_ENVIRONMENT = {
    "python_version": PYTHON_VERSION,
    "python_full_version": f"{PYTHON_VERSION}.0",
    "sys_platform": "linux",
    "platform_machine": "x86_64",
}

_TIMEOUT = object()  # sentinel for network timeouts

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


def colored(text: str, color: str, bold: bool = False) -> str:
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
# (operator, version_str, source_id, marker_or_None)
# ---------------------------------------------------------------------------

Bound = tuple[str, str, str, str | None]
SpecSource = tuple[str, str, str | None]


@dataclass
class PackageInfo:
    spec_sources: list[SpecSource]
    lower_bound: Bound | None = None
    upper_bound: Bound | None = None
    pinned: list[tuple[str, str, str | None]] = field(default_factory=list)
    has_conflict: bool = False


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------


def _http_get(url: str, timeout: int = 10) -> bytes | object | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        # Must come before URLError: HTTPError is a subclass of it.
        if e.code != 404:
            logger.debug("HTTP %s: %s", e.code, url)
        return None
    except (socket.timeout, urllib.error.URLError):
        return _TIMEOUT
    except Exception as e:
        logger.debug("Request failed: %s — %s", url, e)
        return None


def fetch_local_file(path: str) -> str | None:
    try:
        return Path(path).read_text()
    except Exception as e:
        logger.error("FAILED local read -> %s (%s)", path, e)
        return None


def fetch_github_raw(owner: str, repo: str, ref: str, path: str) -> str | None:
    url = RAW_URL.format(owner=owner, repo=repo, ref=ref, path=path)
    logger.info("FETCH -> %s", url)
    data = _http_get(url, timeout=15)
    if not data or data is _TIMEOUT:
        logger.error("FAILED -> %s", url)
        return None
    return data.decode()


def latest_goats_release() -> str | None:
    url = "https://api.github.com/repos/gemini-hlsw/goats/releases/latest"
    logger.info("Resolving latest GOATS release...")
    data = _http_get(url)
    if not data or data is _TIMEOUT:
        return None
    return json.loads(data).get("tag_name")


def fetch_pypi_requires(package: str, version: str | None = None) -> list[str]:
    url = (
        PYPI_URL.format(package=package, version=version)
        if version
        else PYPI_URL_LATEST.format(package=package)
    )
    logger.debug("PyPI -> %s", url)
    data = _http_get(url)
    if not data or data is _TIMEOUT:
        return []
    return json.loads(data)["info"].get("requires_dist") or []


def _fetch_anaconda_versions(package: str, channel: str) -> list[str] | object:
    url = ANACONDA_URL.format(channel=channel, package=package)
    data = _http_get(url)
    if data is _TIMEOUT:
        return _TIMEOUT
    if not data:
        return []
    return json.loads(data).get("versions", [])


def _fetch_gemini_versions(package: str, repodata_url: str) -> set[str] | object:
    data = _http_get(repodata_url, timeout=15)
    if data is _TIMEOUT:
        return _TIMEOUT
    if not data:
        return set()
    repo = json.loads(data)
    found: set[str] = set()
    for section in ("packages", "packages.conda"):
        for info in repo.get(section, {}).values():
            if info.get("name", "").lower() == package.lower():
                found.add(info["version"])
    return found


def _conda_name_variants(package: str) -> set[str]:
    name = PACKAGE_NAME_MAP.get(package.lower(), package.lower())
    variants = {name}
    if "-" in name:
        variants.add(name.replace("-", "_"))
    elif "_" in name:
        variants.add(name.replace("_", "-"))
    return variants


def _fetch_channel_group(
    name: str,
    tasks: list[tuple],
) -> tuple[set[str], bool]:
    """Run a group of channel fetches in parallel. Returns (versions, had_timeout)."""
    versions: set[str] = set()
    had_timeout = False
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(fn, name, arg): arg for fn, arg in tasks}
        for future in as_completed(futures):
            result = future.result()
            if result is _TIMEOUT:
                had_timeout = True
            elif result:
                versions.update(result)
    return versions, had_timeout


def fetch_conda_versions(package: str) -> list[str]:
    """
    Fetch conda versions with channel priority:
      1. conda-forge (fastest, most packages)
      2. fallback channels (astroconda, defaults, Gemini) — only if conda-forge returns nothing

    Warns if all channels timed out so callers know the result may be incomplete.
    """
    all_versions: set[str] = set()
    had_timeout = False

    for name in _conda_name_variants(package):
        # Priority 1: conda-forge alone
        primary_tasks = [(_fetch_anaconda_versions, "conda-forge")]
        primary_versions, primary_timeout = _fetch_channel_group(name, primary_tasks)
        had_timeout = had_timeout or primary_timeout

        if primary_versions:
            all_versions.update(primary_versions)
            logger.debug("'%s' found in conda-forge, skipping fallback channels", name)
            continue

        # Priority 2: remaining channels in parallel
        logger.debug("'%s' not in conda-forge, trying fallback channels", name)
        fallback_channels = [ch for ch in CONDA_CHANNELS if ch != "conda-forge"]
        fallback_tasks = [
            (_fetch_anaconda_versions, ch) for ch in fallback_channels
        ] + [(_fetch_gemini_versions, url) for url in GEMINI_REPODATA_URLS]
        if fallback_tasks:
            fallback_versions, fallback_timeout = _fetch_channel_group(
                name, fallback_tasks
            )
            had_timeout = had_timeout or fallback_timeout
            all_versions.update(fallback_versions)

    if not all_versions and had_timeout:
        logger.warning(
            "All conda channels timed out for '%s' — result may be incomplete", package
        )

    # Drop versions that aren't PEP 440-parseable rather than failing the whole
    # package; conda channels occasionally expose odd build/version strings.
    parseable: list[str] = []
    for v in all_versions:
        try:
            Version(v)
            parseable.append(v)
        except Exception:
            logger.debug("Skipping unparseable conda version for '%s': %s", package, v)
    return sorted(parseable, key=Version, reverse=True)


def best_conda_match(
    package: str,
    lower_bound: Bound | None,
    upper_bound: Bound | None,
    pinned: list | None,
) -> tuple[str | None, str]:
    versions = fetch_conda_versions(package)
    if not versions:
        return None, "not found in any conda channel"

    specs: list[str] = []
    if pinned:
        specs.append(f"=={pinned[0][0]}")
    else:
        if lower_bound:
            specs.append(f"{lower_bound[0]}{lower_bound[1]}")
        if upper_bound:
            specs.append(f"{upper_bound[0]}{upper_bound[1]}")

    if not specs:
        return versions[0], f"no constraints -> latest {versions[0]}"

    specifier = SpecifierSet(",".join(specs))
    matching = [v for v in versions if v in specifier]

    if not matching:
        return None, (
            f"no conda version satisfies {','.join(specs)} "
            f"(available: {versions[-1]} ... {versions[0]})"
        )

    best = matching[0]
    msg = (
        f"would install {best} (latest is {versions[0]}, constrained by {','.join(specs)})"
        if best != versions[0]
        else f"would install {best} (latest, satisfies {','.join(specs)})"
    )
    return best, msg


# ---------------------------------------------------------------------------
# Dependency parsing
# ---------------------------------------------------------------------------


def parse_pyproject(text: str) -> list[str]:
    return tomllib.loads(text).get("project", {}).get("dependencies", [])


def parse_ci_environment(text: str) -> list[str]:
    data = yaml.safe_load(text)
    out: list[str] = []
    for entry in data.get("dependencies", []):
        if isinstance(entry, str):
            out.append(
                entry.replace("=", "==", 1)
                if "=" in entry and "==" not in entry
                else entry
            )
        elif isinstance(entry, dict) and "pip" in entry:
            out.extend(entry["pip"])
    return out


def parse_requirements(deps: list[str]) -> list[SpecSource]:
    result: list[SpecSource] = []
    for dep in deps:
        try:
            req = Requirement(dep)
            if req.marker:
                try:
                    if not req.marker.evaluate(PYTHON_ENVIRONMENT):
                        continue
                except Exception:
                    pass
            result.append(
                (
                    req.name.lower(),
                    req.specifier,
                    str(req.marker) if req.marker else None,
                )
            )
        except Exception:
            pass
    return result


def build_source_dict(
    parsed: list[SpecSource], source: str
) -> dict[str, list[SpecSource]]:
    result: dict[str, list[SpecSource]] = {}
    for name, spec, marker in parsed:
        result.setdefault(name, []).append((str(spec), source, marker))
    return result


def get_pinned_version(d: dict, pkg: str) -> tuple[str | None, str | None, str | None]:
    for spec, source, marker in d.get(pkg, []):
        if "==" in spec:
            return spec.replace("==", "").strip(), source, marker
    return None, None, None


# ---------------------------------------------------------------------------
# Transitive resolution
# ---------------------------------------------------------------------------


def resolve_transitive(
    package: str,
    version: str | None = None,
    depth: int = 0,
    seen: set[str] | None = None,
    max_depth: int = 2,
) -> list[str]:
    if seen is None:
        seen = set()
    if depth >= max_depth or package in seen:
        return []

    seen.add(package)
    logger.info(
        "[depth %d] Resolving: %s%s", depth, package, f" v{version}" if version else ""
    )
    deps = fetch_pypi_requires(package, version)
    if not deps:
        return []

    all_deps: list[str] = []
    for dep in deps:
        all_deps.append(dep)
        try:
            req = Requirement(dep)
            pinned = next(
                (s.version for s in req.specifier if s.operator == "=="), None
            )
            all_deps.extend(
                resolve_transitive(req.name, pinned, depth + 1, seen, max_depth)
            )
        except Exception as e:
            logger.warning("Could not parse dep '%s': %s", dep, e)

    return all_deps


# ---------------------------------------------------------------------------
# Intersection analysis
# ---------------------------------------------------------------------------


def _parse_bound(spec: str) -> dict[str, str] | None:
    for op in ("==", ">=", "<=", ">", "<", "!="):
        if spec.strip().startswith(op):
            return {"type": op, "version": spec.strip()[len(op) :].strip()}
    return None


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

        for spec, source, marker in deduped:
            for part in (s.strip() for s in spec.split(",") if s.strip()):
                b = _parse_bound(part)
                if not b:
                    continue
                if b["type"] == "==":
                    pinned.append((b["version"], source, marker))
                elif b["type"] in (">=", ">"):
                    lower_bounds.append((b["type"], b["version"], source, marker))
                elif b["type"] in ("<=", "<"):
                    upper_bounds.append((b["type"], b["version"], source, marker))

        lower_bound: Bound | None = None
        if lower_bounds:
            try:
                lower_bound = max(lower_bounds, key=lambda x: Version(x[1]))
            except Exception:
                lower_bound = lower_bounds[0]

        upper_bound: Bound | None = None
        if upper_bounds:
            try:
                upper_bound = min(upper_bounds, key=lambda x: Version(x[1]))
            except Exception:
                upper_bound = upper_bounds[0]

        intersections[pkg] = PackageInfo(
            spec_sources=deduped,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            pinned=pinned,
            has_conflict=len({p[0] for p in pinned}) > 1 if pinned else False,
        )

    return intersections


def is_range_valid(lower: Bound | None, upper: Bound | None) -> bool:
    if not lower or not upper:
        return True
    try:
        return Version(lower[1]) <= Version(upper[1])
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Conda parallel fetch
# ---------------------------------------------------------------------------


def build_conda_results(
    intersections: dict[str, PackageInfo],
) -> dict[str, tuple[str | None, str]]:
    results: dict[str, tuple[str | None, str]] = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {
            pool.submit(
                best_conda_match,
                pkg,
                info.lower_bound,
                info.upper_bound,
                info.pinned or None,
            ): pkg
            for pkg, info in intersections.items()
        }
        for future in as_completed(futures):
            pkg = futures[future]
            try:
                results[pkg] = future.result()
            except Exception as e:
                results[pkg] = (None, f"error: {e}")
    return results


def classify_status(
    info: PackageInfo,
    conda_ver: str | None,
    conda_status: str,
) -> tuple[str, str | None]:
    has_bounds = bool(info.lower_bound or info.upper_bound or info.pinned)
    conda_unsatisfied = conda_ver is None and (
        "no conda version satisfies" in conda_status
        or "not found in any conda channel" in conda_status
    )

    if info.has_conflict:
        issue = "Pinned to multiple versions: " + ", ".join(
            f"{v} (from {s})" for v, s, _ in info.pinned
        )
        return "conflict", issue

    if not is_range_valid(info.lower_bound, info.upper_bound):
        lb, ub = info.lower_bound, info.upper_bound
        issue = (
            f"Impossible range: {lb[0]}{lb[1]} AND {ub[0]}{ub[1]}"
            if lb and ub
            else None
        )
        return "invalid_range", issue

    if conda_unsatisfied and has_bounds:
        return "conda_conflict", conda_status

    return "ok", None


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------


def _fmt_marker(marker: str | None) -> str:
    return colored(f" [{marker}]", Color.DIM) if marker else ""


def print_analysis(
    intersections: dict[str, PackageInfo],
    goats_ref: str,
    max_depth: int,
) -> int:
    """Print the analysis and return the number of conflicting packages."""
    title = "DEPENDENCY RESOLUTION ANALYSIS"
    if max_depth:
        title += f" (transitive depth: {max_depth})"

    print(colored("Fetching conda availability...", Color.DIM), end="\r", flush=True)
    conda_results = build_conda_results(intersections)
    print(" " * 50, end="\r", flush=True)

    # Classify once; reused by both the summary tally and the detail loop below.
    statuses: dict[str, tuple[str, str | None]] = {}
    conflicts: dict[str, tuple[PackageInfo, str, str | None]] = {}
    valid: list[str] = []
    not_in_conda: list[str] = []

    for pkg, info in sorted(intersections.items()):
        conda_ver, conda_status = conda_results.get(pkg, (None, "not checked"))
        status, issue = classify_status(info, conda_ver, conda_status)
        statuses[pkg] = (status, issue)
        if status in CONFLICT_STATUSES:
            conflicts[pkg] = (info, status, issue)
        else:
            valid.append(pkg)
        if conda_ver is None and "not found in any conda channel" in conda_status:
            not_in_conda.append(pkg)

    sep = "=" * 120
    print(f"\n{sep}")
    print(colored(title, Color.BLUE, bold=True))
    print(f"{sep}\n")

    for pkg, info in sorted(intersections.items()):
        conda_ver, conda_status = conda_results.get(pkg, (None, "not checked"))
        status, _ = statuses[pkg]

        scol = Color.RED if status in CONFLICT_STATUSES else Color.GREEN
        print(
            f"{colored(f'[{status.upper()}]', scol, bold=True)} {colored(pkg, Color.CYAN, bold=True)}"
        )

        print("  Requirements:")
        for spec, source, marker in info.spec_sources:
            c = SOURCE_COLOR.get(source, Color.YELLOW)
            print(
                f"    · {colored(spec, c)} (from {colored(source.upper(), c)}){_fmt_marker(marker)}"
            )

        if info.pinned:
            if info.has_conflict:
                print("  Pinned versions (CONFLICT):")
                for v, s, m in info.pinned:
                    c = SOURCE_COLOR.get(s, Color.YELLOW)
                    print(
                        f"    · {colored(v, Color.RED, bold=True)} (from {colored(s.upper(), c)}){_fmt_marker(m)}"
                    )
            else:
                v, s, m = info.pinned[0]
                c = SOURCE_COLOR.get(s, Color.YELLOW)
                print(
                    f"  Pinned: {colored(v, c, bold=True)} (from {colored(s.upper(), c)}){_fmt_marker(m)}"
                )

        if info.lower_bound or info.upper_bound:
            print("  Version bounds:")
            for label, b in (("Lower", info.lower_bound), ("Upper", info.upper_bound)):
                if b:
                    c = SOURCE_COLOR.get(b[2], Color.YELLOW)
                    print(
                        f"    {label}: {colored(b[0]+b[1], c)} (from {colored(b[2].upper(), c)})"
                    )
            if info.lower_bound and info.upper_bound:
                try:
                    lv, uv = Version(info.lower_bound[1]), Version(info.upper_bound[1])
                    rng = f"{info.lower_bound[1]} -> {info.upper_bound[1]}"
                    valid_rng = lv <= uv
                    print(
                        f"  Range: {colored(rng, Color.GREEN if valid_rng else Color.RED, bold=not valid_rng)}"
                    )
                except Exception:
                    pass

        conda_color = Color.GREEN if conda_ver else Color.RED
        print(f"  Conda: {colored(conda_status, conda_color)}")
        print()

    print(sep)
    print(colored("SUMMARY", Color.BLUE, bold=True))
    print(sep)
    print(f"Total packages analyzed: {len(intersections)}")
    print(f"  {colored(f'{len(valid)} OK', Color.GREEN, bold=True)}")
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
        for pkg, (_, _, issue) in sorted(conflicts.items()):
            print(f"\n  {colored(pkg, Color.RED, bold=True)}")
            if issue:
                print(f"  Issue: {issue}")
        print()

    if not_in_conda:
        print(colored("NOT IN ANY CONDA CHANNEL:", Color.YELLOW, bold=True))
        print("-" * 120)
        for pkg in sorted(not_in_conda):
            specs = ", ".join(
                f"{sp} (from {src})" for sp, src, _ in intersections[pkg].spec_sources
            )
            print(
                f"  {colored(pkg, Color.YELLOW, bold=True)}: {colored(specs, Color.DIM)}"
            )
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
) -> dict[str, Any]:
    print("Fetching conda availability...", file=sys.stderr, flush=True)
    conda_results = build_conda_results(intersections)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    # Only emit root nodes for sources that actually contributed specs
    # (JDAViz is optional and may be absent).
    active_sources = {
        src
        for specs in global_dict.values()
        for _, src, _ in specs
        if src in SOURCE_IDS
    }

    # Root nodes
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

    # GOATS -> TOMToolkit / DRAGONS edges
    for pkg in ("tomtoolkit", "dragons"):
        for spec, src, _ in global_dict.get(pkg, []):
            if src == "goats":
                key = ("goats", pkg)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append(
                        {
                            "source": "goats",
                            "target": pkg,
                            "label": spec,
                            "conflict": False,
                        }
                    )

    # Dependency nodes + edges
    for pkg, info in intersections.items():
        if pkg in SOURCE_IDS:
            continue

        conda_ver, conda_status = conda_results.get(pkg, (None, "not checked"))
        status, issue = classify_status(info, conda_ver, conda_status)

        nodes.append(
            {
                "id": pkg,
                "label": pkg,
                "status": status,
                "issue": issue,
                "sources": list({src for _, src, _ in info.spec_sources}),
                "specs": [
                    {"spec": sp, "from": src} for sp, src, _ in info.spec_sources
                ],
                "lower_bound": _bound_str(info.lower_bound),
                "upper_bound": _bound_str(info.upper_bound),
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

    result = {
        "goats_version": goats_ref,
        "python_version": PYTHON_VERSION,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total": len(nodes),
            "conflicts": sum(1 for n in nodes if n["status"] in CONFLICT_STATUSES),
            "ok": sum(1 for n in nodes if n["status"] == "ok"),
        },
    }
    return result


def export_json(
    intersections: dict[str, PackageInfo],
    global_dict: dict[str, list[SpecSource]],
    goats_ref: str,
) -> int:
    """Print the graph JSON and return the number of conflicting packages."""
    result = build_export(intersections, global_dict, goats_ref)
    print(json.dumps(result, indent=2))
    return result["summary"]["conflicts"]


def serve_viewer(
    intersections: dict[str, PackageInfo],
    global_dict: dict[str, list[SpecSource]],
    goats_ref: str,
) -> int:
    """Write the graph JSON next to interactive.html, serve it locally, open a browser.

    Returns the number of conflicting packages.
    """
    import functools
    import http.server
    import threading
    import webbrowser

    here = Path(__file__).resolve().parent
    if not (here / "interactive.html").exists():
        die(f"interactive.html not found next to the script ({here})")

    data_name = "viewer_data.json"
    result = build_export(intersections, global_dict, goats_ref)
    (here / data_name).write_text(json.dumps(result, indent=2))
    logger.info("Wrote %s", here / data_name)

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(here)
    )
    # Port 0 -> let the OS pick a free port.
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/interactive.html?data={data_name}"

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(colored(f"\nViewer:  {url}", Color.GREEN, bold=True), file=sys.stderr)
    print(
        colored("Serving locally — press Ctrl+C to stop.", Color.DIM), file=sys.stderr
    )
    webbrowser.open(url)

    try:
        threading.Event().wait()  # block forever until interrupted
    except KeyboardInterrupt:
        print(colored("\nStopped.", Color.DIM), file=sys.stderr)
        httpd.shutdown()

    return result["summary"]["conflicts"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _fetch_dragons_deps(version: str) -> list[str]:
    setup = fetch_github_raw(*DRAGONS_REPO, f"v{version}", "setup.py")
    if setup:
        m = re.search(r"install_requires\s*=\s*\[(.*?)\]", setup, re.DOTALL)
        if m:
            deps = [
                d.strip()
                for d in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))
                if d.strip()
            ]
            if deps:
                return deps

    pyproject = fetch_github_raw(*DRAGONS_REPO, f"v{version}", "pyproject.toml")
    if pyproject:
        logger.info("DRAGONS: using pyproject.toml")
        return parse_pyproject(pyproject)

    return []


def main(
    max_depth: int = 0,
    goats_version: str | None = None,
    goats_path: str | None = None,
    verbose: bool = False,
    json_output: bool = False,
    open_viewer: bool = False,
    fail_on_conflict: bool = False,
) -> None:
    if verbose:
        logger.setLevel(logging.DEBUG)

    goats_ref = "Local" if goats_path else (goats_version or latest_goats_release())
    if not goats_ref:
        die("Could not determine GOATS version")

    if not json_output:
        print(
            f"\n{colored('GOATS:', Color.BLUE, bold=True)}  {colored(goats_ref, Color.CYAN, bold=True)}"
        )
        print(
            f"{colored('Python:', Color.BLUE, bold=True)} {colored(PYTHON_VERSION, Color.CYAN, bold=True)}"
        )
        print(
            f"{colored('Depth:', Color.BLUE, bold=True)}  {colored(str(max_depth), Color.CYAN, bold=True)}\n"
        )

    # GOATS
    if goats_path:
        goats_py = fetch_local_file(f"{goats_path}/pyproject.toml")
        goats_ci = fetch_local_file(f"{goats_path}/ci_environment.yaml")
    else:
        goats_py = fetch_github_raw(*GOATS_REPO, goats_ref, "pyproject.toml")
        goats_ci = fetch_github_raw(*GOATS_REPO, goats_ref, "ci_environment.yaml")

    if not goats_py:
        die("Could not fetch GOATS pyproject.toml")
    goats_deps = parse_pyproject(goats_py) + (
        parse_ci_environment(goats_ci) if goats_ci else []
    )
    goats_dict = build_source_dict(parse_requirements(goats_deps), "goats")

    tomtoolkit_version, _, _ = get_pinned_version(goats_dict, "tomtoolkit")
    dragons_version, _, _ = get_pinned_version(goats_dict, "dragons")
    logger.info("TOMToolkit: %s | DRAGONS: %s", tomtoolkit_version, dragons_version)
    jdaviz_version, _, _ = get_pinned_version(goats_dict, "jdaviz")
    logger.info("JDAViz: %s", jdaviz_version)
    if not tomtoolkit_version or not dragons_version:
        die("Could not determine TOMToolkit or DRAGONS versions")

    # TOMToolkit
    tom_py = fetch_github_raw(*TOMTOOLKIT_REPO, tomtoolkit_version, "pyproject.toml")
    if not tom_py:
        die("Could not fetch TOMToolkit pyproject.toml")
    tom_dict = build_source_dict(
        parse_requirements(parse_pyproject(tom_py)), "tomtoolkit"
    )

    # DRAGONS
    dragons_dict = build_source_dict(
        parse_requirements(_fetch_dragons_deps(dragons_version)), "dragons"
    )

    # JDAViz (optional — GOATS may not pin it)
    jdaviz_dict: dict[str, list[SpecSource]] = {}
    if jdaviz_version:
        jdaviz_py = fetch_github_raw(
            *JDAVIZ_REPO, f"v{jdaviz_version}", "pyproject.toml"
        )
        if jdaviz_py:
            jdaviz_dict = build_source_dict(
                parse_requirements(parse_pyproject(jdaviz_py)), "jdaviz"
            )
        else:
            logger.warning("Could not fetch JDAViz pyproject.toml — skipping JDAViz")
    else:
        logger.info("JDAViz not pinned by GOATS — skipping")

    # Merge
    global_dict: dict[str, list[SpecSource]] = {}
    for d in (goats_dict, tom_dict, dragons_dict, jdaviz_dict):
        for k, v in d.items():
            global_dict.setdefault(k, []).extend(v)

    # Transitive deps via PyPI
    if max_depth > 0:
        print(
            colored(f"Resolving transitive deps (depth={max_depth})...", Color.DIM),
            file=sys.stderr,
        )
        direct_count = len(global_dict)
        for pkg in list(global_dict.keys()):
            pinned_ver, _, _ = get_pinned_version(global_dict, pkg)
            for name, spec, marker in parse_requirements(
                resolve_transitive(pkg, pinned_ver, max_depth=max_depth)
            ):
                global_dict.setdefault(name, []).append((str(spec), pkg, marker))
        added = len(global_dict) - direct_count
        print(
            colored(f"Done — {added} new packages found", Color.GREEN, bold=True),
            file=sys.stderr,
        )

    intersections = find_intersections(global_dict)

    if open_viewer:
        conflict_count = serve_viewer(intersections, global_dict, goats_ref)
    elif json_output:
        conflict_count = export_json(intersections, global_dict, goats_ref)
    else:
        conflict_count = print_analysis(intersections, goats_ref, max_depth)

    if fail_on_conflict and conflict_count > 0:
        logger.error(
            "%d conflicting package(s) found (--fail-on-conflict)", conflict_count
        )
        sys.exit(2)


if __name__ == "__main__":
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
        help="Output JSON for dep_graph.html. All logs go to stderr.",
    )
    parser.add_argument(
        "--goats-path",
        metavar="PATH",
        help="Path local to GOATS repository (uses local pyproject.toml instead of GitHub).",
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
    args = parser.parse_args()

    if args.depth < 0:
        parser.error("--depth must be >= 0")
    if args.depth > 5:
        print(
            colored("Warning: --depth > 5 may be slow", Color.YELLOW, bold=True),
            file=sys.stderr,
        )

    main(
        max_depth=args.depth,
        goats_version=args.version,
        goats_path=args.goats_path,
        verbose=args.verbose,
        json_output=args.json,
        open_viewer=args.open,
        fail_on_conflict=args.fail_on_conflict,
    )
