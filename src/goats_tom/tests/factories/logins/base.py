import factory
from ..user import UserFactory


class BaseLoginFactory(factory.django.DjangoModelFactory):
    """Abstract factory for BaseLogin subclasses."""
    user = factory.SubFactory(UserFactory)
    username = factory.Faker("user_name")
    password = factory.Faker(
        "password",
        length=12,
        special_chars=True,
        digits=True,
        upper_case=True,
        lower_case=True,
    )

    class Meta:
        abstract = True