import factory
from django.contrib.auth.models import User


class UserFactory(factory.django.DjangoModelFactory):
    """Factory class for creating `User` model instances for testing.

    Attributes
    ----------
    username : factory.Sequence
        Generates a unique username sequence for each user instance.
    password : str
        A hashed password, generated using `make_password` for consistency in
        tests.

    """

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    password = factory.PostGenerationMethodCall("set_password", "password")