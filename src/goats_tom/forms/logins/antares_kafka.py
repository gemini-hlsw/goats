__all__ = ["AntaresKafkaLoginForm"]

from django import forms

from goats_tom.models import AntaresKafkaLogin


class AntaresKafkaLoginForm(forms.ModelForm):
    """Form for managing ANTARES Kafka streaming credentials.

    Notes
    -----
    Does not include a Kafka consumer group field -- that's set on the
    "Ingest from Kafka stream" ingestion page instead (see
    `goats_tom.forms.AntaresStreamSubscribeForm`), since it's changed far
    more often than these credentials (e.g. to force a full replay from a
    fresh group with no committed offset).
    """

    class Meta:
        model = AntaresKafkaLogin
        fields = ["api_key", "api_secret"]
        labels = {
            "api_key": "Kafka API Key",
            "api_secret": "Kafka API Secret",
        }
        widgets = {
            "api_key": forms.PasswordInput(attrs={"class": "form-control"}),
            "api_secret": forms.PasswordInput(attrs={"class": "form-control"}),
        }

