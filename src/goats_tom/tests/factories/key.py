import factory
from goats_tom.models import (
    Key,
)
from .user import UserFactory


class KeyFactory(factory.django.DjangoModelFactory):
    """Base factory for keys."""

    class Meta:
        model = Key
        abstract = True

    user = factory.SubFactory(UserFactory)
    password = "default_password"
    site = factory.Iterator(["GS", "GN"])
