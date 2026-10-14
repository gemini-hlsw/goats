__all__ = ["goa_session"]

from collections.abc import Iterator
from contextlib import contextmanager

from .gemini import ObservationsClass


@contextmanager
def goa_session() -> Iterator[ObservationsClass]:
    """Yield a GOA client with its own HTTP session, logged out and closed on exit.

    Yields
    ------
    ObservationsClass
        A client no other request or task shares, so one user's login never
        reaches another's queries.
    """
    goa = ObservationsClass()
    try:
        yield goa
    finally:
        goa.logout()
        goa._session.close()
