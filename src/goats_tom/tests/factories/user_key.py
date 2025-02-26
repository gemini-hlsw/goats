import factory
from goats_tom.models import (
    UserKey,
)
from .key import KeyFactory


class UserKeyFactory(KeyFactory):
    """Factory for UserKey model."""

    class Meta:
        model = UserKey

    email = factory.LazyAttribute(lambda obj: f"{obj.user.username}@example.com")
    is_active = False
