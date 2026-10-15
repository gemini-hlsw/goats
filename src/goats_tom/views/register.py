"""The public page to request an account."""

__all__ = ["register"]

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from goats_tom.accounts import create_account_request
from goats_tom.forms import RegistrationForm


@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    """Show and handle the form to request an account.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request.

    Returns
    -------
    `HttpResponse`
        The form, or a redirect to the "request sent" page once made. A
        signed-in user is sent home.
    """
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        create_account_request(
            form.save(commit=False),
            affiliation=form.cleaned_data["affiliation"],
            message=form.cleaned_data["message"],
        )
        return redirect("register-done")
    return render(request, "registration/register.html", {"form": form})
