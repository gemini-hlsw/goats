__all__ = ["AntaresKafkaLoginForm"]

from django import forms

from goats_tom.models import AntaresKafkaLogin


class AntaresKafkaLoginForm(forms.ModelForm):
    """Form for managing ANTARES Kafka streaming credentials."""

    class Meta:
        model = AntaresKafkaLogin
        fields = ["api_key", "api_secret", "group"]
        labels = {
            "api_key": "Kafka API Key",
            "api_secret": "Kafka API Secret",
            "group": "Kafka Group (optional)",
        }
        widgets = {
            "api_key": forms.PasswordInput(attrs={"class": "form-control"}),
            "api_secret": forms.PasswordInput(attrs={"class": "form-control"}),
            "group": forms.TextInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "group": (
                "Optional. If left blank, a built-in default group name is "
                "used. Set this explicitly rather than relying on the "
                "underlying client's own default (which falls back to the "
                "machine's hostname), so the consumer group -- and "
                "therefore offset tracking -- stays stable across restarts "
                "and across hosts."
            ),
        }
