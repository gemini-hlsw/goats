import factory

from goats_tom.models import TNSGroup, TNSLogin

from .base import TokenLoginFactory


class TNSLoginFactory(TokenLoginFactory):
    """TNS credentials, optionally with the groups the bot files under.

    Groups are rows rather than a field on the login, so ``groups=["A"]``
    creates them for the owner and keeps a test's setup to one line.
    """

    class Meta:
        model = TNSLogin

    bot_id = factory.Faker("word")
    bot_name = factory.Faker("word")

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        """Create a `TNSGroup` row per name given."""
        if not create or not extracted:
            return
        for name in extracted:
            TNSGroup.objects.get_or_create(owner=self.user, name=name)
