"""Authentication helper shared by GOATS' WebSocket consumers.

WebSocket connections do **not** pass through Django's middleware, so none of
the request-level protections apply to them. In particular
``AUTH_STRATEGY = "LOCKED"`` closes the site to anonymous visitors but leaves
these sockets wide open, which is easy to miss precisely because locking the
site *looks* like it covered everything.

Kept in one place so both consumers apply the same rule, and so there is a
single obvious spot to change if the rule ever needs to differ.
"""

__all__ = ["_is_authenticated"]


def _is_authenticated(user) -> bool:
    """Return whether `user` is a signed-in account.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`, `AnonymousUser` or None
        Usually ``scope["user"]``, populated by Channels'
        ``AuthMiddlewareStack``.

    Returns
    -------
    bool
        `True` only for an authenticated user.

    Notes
    -----
    `None` is treated as unauthenticated rather than as a configuration
    error. It occurs when the auth middleware is absent -- most often in
    tests that drive a consumer directly -- and failing closed there is the
    right default: a test that forgets to authenticate should see the
    connection refused, not silently granted.

    `AnonymousUser.is_authenticated` is already `False`, so the `getattr`
    default only covers objects that are not users at all.
    """
    return bool(getattr(user, "is_authenticated", False))
