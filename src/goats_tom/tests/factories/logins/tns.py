import factory

from goats_tom.models import TNSLogin

from .base import TokenLoginFactory


class TNSLoginFactory(TokenLoginFactory):
    class Meta:
        model = TNSLogin

    bot_id = factory.Faker("word")
    bot_name = factory.Faker("word")
    group_names = ["group1", "group2"]
