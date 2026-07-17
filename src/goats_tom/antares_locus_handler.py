"""Restricted execution of user-submitted ANTARES locus handler code.

Lets a GOATS user write a Python function, ``def myfilter(locus): ...``,
that receives each `locus` from the Kafka stream and returns whether to
keep processing it -- an additional filter beyond the topic subscription
itself. See the ANTARES `Locus` API for available attributes/methods:
https://nsf-noirlab.gitlab.io/csdc/antares/client/api.html#antares_client.models.Locus

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
    "LocusHandlerError",
    "HANDLER_FUNCTION_NAME",
]

import logging

logger = logging.getLogger(__name__)

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
        If the source contains a forbidden substring, or does not define
        a function named `HANDLER_FUNCTION_NAME`.

    Notes
    -----
    The forbidden-substring check is a coarse, string-level pre-filter --
    easy to reason about, but not exhaustive (see module docstring). It
    runs before compilation as a cheap first line of defense. Public (not
    underscore-prefixed) because the subscription form also calls this
    directly, to reject obviously bad code at submit time using the exact
    same rules the runtime consumer enforces, rather than maintaining two
    copies that could drift apart.
    """
    lowered = source.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        if forbidden in lowered:
            raise LocusHandlerError(
                f"Handler code contains a disallowed pattern: {forbidden!r}"
            )

    if f"def {HANDLER_FUNCTION_NAME}(" not in source:
        raise LocusHandlerError(
            f"Handler code must define a function named "
            f"'{HANDLER_FUNCTION_NAME}', e.g. "
            f"'def {HANDLER_FUNCTION_NAME}(locus): ...'"
        )


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
