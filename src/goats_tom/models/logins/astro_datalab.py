__all__ = ["AstroDatalabLogin"]

from django.db import models

from .base import UsernamePasswordLogin


class AstroDatalabLogin(UsernamePasswordLogin):
    """Extends `UsernamePasswordLogin` to store Astro Datalab user credentials.

    Attributes
    ----------
    jupyter_token : `models.CharField`
        JupyterHub API token for this account, used to spawn and drive the
        user's notebook server when ``GOATS_STREAM_EXECUTOR="datalab"``.
        Optional: blank on a desktop install, and blank for any user who has
        linked Data Lab but is not running remote jobs.

    Notes
    -----
    **Two different Data Lab credentials, not interchangeable.** The
    `username` and `password` here are exchanged at run time for a science
    token, which authenticates the ``/auth``, ``/storage`` and MyDB services.
    `jupyter_token` authenticates the JupyterHub in front of the notebook
    servers, which is a separate surface with its own API and its own token.
    Passing one where the other is expected does not fail cleanly -- Hub
    requests 404 or redirect to a login page, which reads as a missing server
    rather than an auth problem.

    The science token is deliberately **not** stored. It expires, and a stale
    one fails in an unusually unhelpful way: `queryClient` reports ``'OK'``
    whatever the service actually said, so an expired token looks like a
    silent no-op rather than an authentication error. Minting one per launch
    from the stored password avoids a whole class of confusing failures.

    Like every other credential in `goats_tom.models.logins`, this is held in
    **plain text**. Encrypting these at rest is an outstanding requirement
    before a shared multi-tenant deployment, where one host holds 300 PIs'
    credentials rather than one astronomer's own.
    """

    jupyter_token = models.CharField(max_length=255, blank=True, default="")
