__all__ = ["AstroDatalabLoginForm"]

from django import forms

from goats_tom.models import AstroDatalabLogin


class AstroDatalabLoginForm(forms.ModelForm):
    """Form to input Astro Datalab credentials.

    Notes
    -----
    `jupyter_token` is optional and only used when GOATS is deployed with
    ``GOATS_STREAM_EXECUTOR="datalab"``, where stream consumption runs as
    remote jobs on the user's own Data Lab account. A desktop install ignores
    it entirely, so the field must not be required -- making it mandatory
    would break the single-astronomer credential flow, which the offload work
    is not permitted to change.

    Rendered as a password input rather than a text input so it is not left
    on screen or captured in screenshots, and given `render_value=False` so
    reopening the page does not redisplay a stored secret.
    """

    class Meta:
        model = AstroDatalabLogin
        fields = ["username", "password", "jupyter_token"]
        labels = {
            "username": "Username",
            "password": "Password",
            "jupyter_token": "JupyterHub token (optional)",
        }
        help_texts = {
            "jupyter_token": (
                "Only needed on a shared GOATS server that offloads ANTARES "
                "stream processing to Data Lab. This is a separate credential "
                "from your Data Lab password."
            ),
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
            "jupyter_token": forms.PasswordInput(
                attrs={"class": "form-control"}, render_value=False
            ),
        }
