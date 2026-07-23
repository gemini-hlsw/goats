"""Restricted execution of user-submitted ANTARES locus handler code.

Lets a GOATS user write a Python function, ``def myfilter(locus): ...``,
that receives each `locus` from the Kafka stream and returns whether to
keep processing it -- an additional filter beyond the topic subscription
itself. See the ANTARES `Locus` API for available attributes/methods:
https://nsf-noirlab.gitlab.io/csdc/antares/client/api.html#antares_client.models.Locus
(that page documents `properties` only generically as "ANTARES- and
user-generated properties"; specific keys like
`newest_alert_observation_time`, `newest_alert_id`, and `num_alerts` were
confirmed by direct testing against the live stream, not from the
official docs, which don't enumerate them).

SECURITY NOTE: this is a *restricted namespace*, not a true sandbox. It
strips dangerous builtins (`open`, `exec`, `eval`, `__import__`, etc.) and
disallows `import` statements at compile time (all imports are blocked;
`numpy`, `pandas`, `astropy`, and `astroquery` are instead pre-bound as
already-imported names, so user code can use them without an `import`
statement ever needing to compile). This stops accidental misuse and
casual mistakes. It does **not** reliably stop a determined, malicious
user: Python sandboxing via a restricted namespace alone is well known to
be escapable (e.g. via object introspection through
`__class__`/`__bases__`/`__subclasses__` chains reaching back to unsafe
builtins). This is acceptable ONLY because GOATS' ANTARES stream users are
treated as trusted (per product decision) -- do not reuse this module to
run untrusted code. Note also that `astroquery` performs real network
requests to external services -- allowing it means user code can make
outbound network calls (e.g. catalog cross-matches), which is intentional
here but worth knowing.
"""

__all__ = [
    "run_locus_handler",
    "check_handler_source",
    "validate_handler_code",
    "is_effectively_blank",
    "LocusHandlerError",
    "HANDLER_FUNCTION_NAME",
]

import logging

logger = logging.getLogger(__name__)


def is_effectively_blank(source: str) -> bool:
    """Check whether `source` contains no real code -- blank, whitespace,
    and/or comments only.

    Parameters
    ----------
    source : str
        The handler source to check.

    Returns
    -------
    bool
        `True` if `source` is empty/whitespace, or parses cleanly to an
        AST with no top-level statements (i.e. everything present is a
        comment). `False` if `source` has a syntax error -- a genuine
        mistake (missing paren, bad indentation, etc.) is not the same
        thing as intentionally commenting code out, and should still be
        reported as a real error by the normal validation path rather
        than silently treated as "no filter."

    Notes
    -----
    A fully commented-out handler, e.g. ``# def myfilter(locus): ...``,
    should behave identically to leaving the field blank -- both mean "no
    filter." Using `ast.parse(source).body` to check this (rather than a
    hand-rolled comment-stripping regex) is robust because Python's own
    parser already discards comments; an all-comments source reliably
    parses to an empty body.
    """
    if not source.strip():
        return True

    import ast as _ast  # noqa: PLC0415

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return False

    return len(tree.body) == 0

HANDLER_FUNCTION_NAME = "myfilter"

# Deliberately small: only what a locus-filtering function plausibly needs.
# No `open`, `exec`, `eval`, `__import__`, `compile`, `input`, `getattr`,
# `setattr`, `globals`, `locals`, `vars`, `dir`, etc.
_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}


def _build_preimported_modules() -> dict:
    """Pre-import the small set of allowed third-party packages once.

    Returns
    -------
    dict
        Maps the name user code will see (e.g. ``"numpy"``) to the actual
        imported module object. Done here, at import time of *this*
        trusted module, not inside user code -- user code never executes
        an `import` statement itself; these modules are simply already
        present as bound names in the restricted namespace.
    """
    import astropy
    import astroquery
    import numpy
    import pandas

    return {
        "numpy": numpy,
        "pandas": pandas,
        "astropy": astropy,
        "astroquery": astroquery,
    }


_PREIMPORTED_MODULES = _build_preimported_modules()

_FORBIDDEN_SUBSTRINGS = (
    "import ",  # blocks all import statements; allowed modules are pre-bound instead
    "__",  # blocks dunder attribute access chains (e.g. __class__, __globals__)
    "exec",
    "eval",
    "open(",
    "compile(",
    "getattr",
    "setattr",
    "globals",
    "locals",
)


class LocusHandlerError(Exception):
    """Raised when user-submitted handler code fails to compile or run."""


def check_handler_source(source: str) -> None:
    """Reject obviously dangerous or malformed source before running it.

    Parameters
    ----------
    source : str
        User-submitted function definition, expected to define
        ``def myfilter(locus): ...``.

    Raises
    ------
    LocusHandlerError
        If the source contains a forbidden substring, fails to parse, or
        does not define a real (not commented-out) function named
        `HANDLER_FUNCTION_NAME` at module level.

    Notes
    -----
    The forbidden-substring check is a coarse, string-level pre-filter --
    easy to reason about, but not exhaustive (see module docstring). It
    runs before compilation as a cheap first line of defense. Public (not
    underscore-prefixed) because the subscription form also calls this
    directly, to reject obviously bad code at submit time using the exact
    same rules the runtime consumer enforces, rather than maintaining two
    copies that could drift apart.

    The `myfilter` presence check parses the source into an AST and looks
    for an actual `FunctionDef` node named `HANDLER_FUNCTION_NAME`, rather
    than a plain substring search on the raw text. A substring search
    would incorrectly accept e.g. an entirely commented-out
    ``# def myfilter(locus): ...`` -- valid-looking text that produces no
    real function when the code actually runs, which previously meant
    this passed form validation but then failed on every single message
    once the consumer was live.

    This function only checks structure (compiles, defines the right
    function name, no forbidden patterns) -- it does NOT execute the code,
    so it cannot catch bugs that only show up when `myfilter` actually
    runs (e.g. wrong return type). See `validate_handler_code` for that.
    """
    import ast as _ast  # noqa: PLC0415

    lowered = source.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        if forbidden in lowered:
            raise LocusHandlerError(
                f"Handler code contains a disallowed pattern: {forbidden!r}"
            )

    try:
        tree = _ast.parse(source)
    except SyntaxError as exc:
        raise LocusHandlerError(f"Syntax error: {exc}") from exc

    has_handler_function = any(
        isinstance(node, _ast.FunctionDef) and node.name == HANDLER_FUNCTION_NAME
        for node in tree.body
    )
    if not has_handler_function:
        raise LocusHandlerError(
            f"Handler code must define a function named "
            f"'{HANDLER_FUNCTION_NAME}', e.g. "
            f"'def {HANDLER_FUNCTION_NAME}(locus): ...'. (A commented-out "
            f"definition doesn't count -- it must be real, uncommented "
            f"code.)"
        )


def _build_test_locus():
    """Build a fully-populated `Locus` instance for dry-running handler
    code at submission time.

    Returns
    -------
    `antares_client.models.Locus`
        A real `Locus` instance (not a hand-rolled stand-in, so its
        attributes/methods behave exactly like the real thing) with
        plausible values for every field, including the three that
        normally lazy-load from the ANTARES HTTP API (`alerts`,
        `catalog_objects`, `lightcurve`) -- pre-populated here rather than
        left `None`, specifically so a handler that reads them during
        this dry run gets real fake data back instead of triggering an
        actual network fetch. This test locus has no real backing record
        in ANTARES, so a lazy-load attempt against it would just fail
        (there's nothing to fetch), not meaningfully validate anything.

        Handlers ARE allowed to use these three fields against real loci
        during live ingestion -- lazy-loading there is a legitimate,
        deliberate choice for whoever writes the handler. This
        pre-population exists only to make dry-run validation work
        cleanly against a locus that isn't real, not to discourage or
        restrict what handler code can reference.

    Notes
    -----
    This is a best-effort smoke test, not a guarantee: real ANTARES loci
    can have missing/`None` property values or shapes this test object
    doesn't cover, so a handler that passes this dry run can still fail
    later against some specific real locus. It substantially reduces --
    it does not eliminate -- the chance of shipping a broken handler to
    the live stream.
    """
    import pandas as _pd  # noqa: PLC0415
    from antares_client.models import Alert, Locus  # noqa: PLC0415

    test_alert = Alert(
        alert_id="test_alert_id",
        mjd=60000.0,
        properties={"ztf_magpsf": 18.0, "ztf_fid": 2},
    )

    return Locus(
        locus_id="ANT2020test000000",
        ra=180.0,
        dec=0.0,
        properties={
            "newest_alert_magnitude": 18.0,
            "newest_alert_observation_time": 60000.0,
            "newest_alert_id": "test_alert_id",
            "num_alerts": 1,
        },
        tags=["nuclear_transient"],
        catalogs=["tns_public_objects"],
        alerts=[test_alert],
        catalog_objects={"tns_public_objects": [{"name": "test_object"}]},
        lightcurve=_pd.DataFrame(
            {"ant_mjd": [60000.0], "ant_mag": [18.0], "ant_passband": ["g"]}
        ),
        watch_list_ids=[],
        watch_object_ids=[],
        grav_wave_events=[],
    )


def validate_handler_code(source: str) -> None:
    """Fully validate handler code at submission time: structure AND an
    actual dry run against a realistic test locus.

    Parameters
    ----------
    source : str
        User-submitted source defining ``def myfilter(locus): ...``.

    Raises
    ------
    LocusHandlerError
        If `check_handler_source` fails, or if actually running
        `myfilter` against a realistic test locus raises or returns a
        non-bool value (see `run_locus_handler`). This catches bugs like
        `(tt > 20) * (tt < 21)` (returns an int, not a bool) before the
        handler is ever used against the live stream, not just after it's
        already caused a failure there.
    """
    check_handler_source(source)
    run_locus_handler(source, _build_test_locus())


def run_locus_handler(source: str, locus) -> bool:
    """Run a user-submitted ``myfilter(locus)`` function against one locus.

    Parameters
    ----------
    source : str
        User-submitted source defining ``def myfilter(locus): ...``, e.g.::

            def myfilter(locus):
                mag = locus.properties.get("newest_alert_magnitude") or 99
                return mag < 18

    locus : `antares_client.models.Locus`
        The locus to evaluate. See the ANTARES `Locus` API for available
        attributes/methods:
        https://nsf-noirlab.gitlab.io/csdc/antares/client/api.html#antares_client.models.Locus

    Returns
    -------
    bool
        Whether this locus should be kept/processed.

    Raises
    ------
    LocusHandlerError
        If the code contains disallowed patterns, doesn't define
        `myfilter`, fails to compile, raises while defining/calling it, or
        returns a non-bool value. Callers (see
        `goats_tom.tasks.ingest_antares_stream`) catch this and keep the
        locus by default rather than let a broken handler drop everything
        silently.
    """
    check_handler_source(source)

    restricted_globals = {"__builtins__": _SAFE_BUILTINS, **_PREIMPORTED_MODULES}
    local_vars = {}

    try:
        code = compile(source, "<antares_locus_handler>", "exec")
        exec(code, restricted_globals, local_vars)  # noqa: S102
        handler_fn = local_vars.get(HANDLER_FUNCTION_NAME)
        if handler_fn is None:
            raise LocusHandlerError(
                f"Handler code did not define a function named "
                f"'{HANDLER_FUNCTION_NAME}'."
            )
        result = handler_fn(locus)
    except LocusHandlerError:
        raise
    except Exception as exc:
        raise LocusHandlerError(f"Handler code raised an error: {exc}") from exc

    # numpy/pandas comparisons return numpy's own bool type (e.g. np.bool_),
    # not Python's native bool -- accept those too, or every handler that
    # uses numpy/pandas (the expected common case, since we pre-bind them)
    # would silently fail the isinstance check and be ignored.
    try:
        import numpy as _np

        is_bool = isinstance(result, (bool, _np.bool_))
    except ImportError:
        is_bool = isinstance(result, bool)

    if not is_bool:
        raise LocusHandlerError(
            f"{HANDLER_FUNCTION_NAME}() returned a non-bool value ({result!r}); "
            f"return True or False explicitly (e.g. use 'and'/'or' or wrap "
            f"the result in bool(...), not arithmetic like '*' between "
            f"comparisons, which produces an int)."
        )

    return bool(result)
