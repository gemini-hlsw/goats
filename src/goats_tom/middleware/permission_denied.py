"""Show a permission refusal as a 403 page rather than a login redirect.

Replaces `tom_common.middleware.Raise403Middleware`, which turns **every**
403 response into a redirect to the login page:

```python
if response.status_code == 403:
    messages.error(request, msg)
    return redirect(reverse('login') + '?next=' + request.path)
```

For an anonymous visitor that is right -- they need to log in. For somebody
who is already logged in it is actively misleading: they are sent to a login
form they do not need, which reads as though their session expired, and the
real reason is buried in a message on the page they land on. It also means
GOATS' own `403.html` -- which exists, and matches the styling of `404.html`
-- never renders, because nothing ever gets to see the 403.

That was noticed when a user was refused deletion of a data product they did
not own and was shown the login page.

Ordering matters: this must sit where `Raise403Middleware` sat, outside the
view but inside `AuthStrategyMiddleware`, so it sees the 403 that
`AuthStrategyMiddleware` returns for anonymous visitors under
``AUTH_STRATEGY = "LOCKED"`` and turns it back into the login redirect that
setting intends.
"""

__all__ = ["PermissionDeniedMiddleware"]

from django.http import HttpRequest, HttpResponse


def _is_page_request(request: HttpRequest) -> bool:
    """Whether this request is a browser navigating to a page.

    Parameters
    ----------
    request : `HttpRequest`
        The request that was refused.

    Returns
    -------
    `bool`
        True when the response will be shown to somebody, so a redirect or a
        rendered error page is useful. False for background requests, which
        should keep their plain 403.

    Notes
    -----
    Two signals, both cheap. `X-Requested-With` is set by jQuery and by
    GOATS' own polling; the `Accept` header distinguishes a browser asking
    for a document from `fetch` asking for JSON.

    Erring towards False would swallow real refusals silently. Erring towards
    True produces the stray banner this exists to stop. Neither is
    catastrophic, and a request that asks for HTML and is not marked as an
    XHR is as close to "a person is looking at this" as the headers get.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return False
    return "text/html" in request.headers.get("Accept", "")


class PermissionDeniedMiddleware:
    """Render `403.html` for authenticated users, redirect anonymous ones."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Convert a 403 response into the right thing for this user.

        Parameters
        ----------
        request : `HttpRequest`
            The incoming request.

        Returns
        -------
        `HttpResponse`
            The original response, the styled 403 page, or a redirect to the
            login form.
        """
        response = self.get_response(request)

        if response.status_code != 403:
            return response

        # Imported here, not at module scope. `goats_tom.middleware` is
        # imported during app loading -- `DRAMATIQ_BROKER` names
        # `goats_tom.middleware.DRAGONSMiddleware`, which pulls in this
        # package's `__init__` -- and `django.contrib.auth.views` reaches
        # `django.contrib.auth.models` on the way in. Importing it up here
        # raises `AppRegistryNotReady: Apps aren't loaded yet` and takes down
        # every management command, `collectstatic` included. Nothing below
        # runs before a request, by which point the registry is ready.
        from django.contrib import messages  # noqa: PLC0415
        from django.contrib.auth.views import redirect_to_login  # noqa: PLC0415
        from django.shortcuts import render  # noqa: PLC0415

        if not _is_page_request(request):
            # A background request -- a poll, a fetch, an image, a WebSocket
            # handshake -- refused while the session was not yet established.
            #
            # Left exactly as it was, for two reasons. Redirecting one to the
            # login form is meaningless; the caller wanted JSON and gets HTML
            # it cannot use. And queuing a message on it puts a banner in the
            # session that surfaces on whatever page the user loads next,
            # which is how "Please log in to access this page." kept
            # appearing on pages the user was already logged into, sometimes
            # several at once. The message belonged to a request the user
            # never made and never saw.
            return response

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            # Anonymous: logging in genuinely might fix it, which is what
            # upstream assumed of everybody.
            #
            # Redirected silently. Upstream queues "You do not have
            # permission to access this page..." here, and on a site running
            # `AUTH_STRATEGY = "LOCKED"` that fires the moment anyone opens
            # the front page -- telling a first-time visitor they lack
            # permission, on the login form, before they have done anything.
            # The form already says what to do.
            return redirect_to_login(request.get_full_path())

        # Already logged in, so no amount of logging in again will help.
        # Say what happened, on a page that looks like the rest of GOATS.
        denied = render(request, "403.html", status=403)
        # Preserve a response body the view took the trouble to write --
        # `PermissionDenied("You do not have permission to delete this data
        # product.")` is more use than the generic page text.
        detail = getattr(response, "content", b"").decode(
            response.charset or "utf-8", errors="replace"
        ).strip()
        if detail and "<" not in detail:
            messages.error(request, detail)
        return denied
