import factory

from goats_tom.models import TNSGroup, TNSGroupJoinRequest, TNSGroupMembership

from .user import UserFactory


class TNSGroupFactory(factory.django.DjangoModelFactory):
    """A TNS group owned by a credential holder.

    Note that this does **not** create a `TNSLogin` for the owner, and the
    owner's `group_names` will not list this group. Several helpers in
    `goats_tom.tns_membership` deliberately treat a group as unusable in
    that state, so tests that need a *postable* group have to set up the
    login as well -- see `tests/goats_tom/test_tns_membership.py`.
    """

    class Meta:
        model = TNSGroup

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Group{n}")
    allow_join_requests = False
    recommended_authors = ""


class TNSGroupMembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TNSGroupMembership

    tns_group = factory.SubFactory(TNSGroupFactory)
    user = factory.SubFactory(UserFactory)


class TNSGroupJoinRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TNSGroupJoinRequest

    requester = factory.SubFactory(UserFactory)
    tns_group = factory.SubFactory(TNSGroupFactory)
    status = TNSGroupJoinRequest.STATUS_PENDING
    message = ""
