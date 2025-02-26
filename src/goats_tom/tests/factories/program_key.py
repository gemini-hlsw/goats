import factory
from goats_tom.models import (
    ProgramKey,
)
from .key import KeyFactory


class ProgramKeyFactory(KeyFactory):
    """Factory for ProgramKey model."""

    class Meta:
        model = ProgramKey

    program_id = factory.Sequence(lambda n: f"GN-2024A-Q-{n}")

    @factory.lazy_attribute
    def site(self):
        """Determine the site based on the program_id."""
        return self.program_id.split("-")[0]

