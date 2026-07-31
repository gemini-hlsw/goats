import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.models import (
    AntaresGroupJoinRequest, AntaresKafkaLogin, AntaresPIGroup,
    AntaresStreamSubscription, AntaresDashboardMembership,
)


@pytest.mark.django_db()
class TestAccessViews:
    def test_request_page_renders(self, client):
        u = User.objects.create_user("u1", password="pw")
        client.force_login(u)
        r = client.get(reverse("antares-request-access"))
        assert r.status_code == 200, r.status_code

    def test_request_page_lists_groups(self, client):
        pi = User.objects.create_user("thepi")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        u = User.objects.create_user("u2", password="pw")
        client.force_login(u)
        r = client.get(reverse("antares-request-access"))
        assert r.status_code == 200
        assert b"antares-thepi" in r.content

    def test_submit_request(self, client):
        pi = User.objects.create_user("thepi2")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pig = AntaresPIGroup.objects.get(pi=pi)
        u = User.objects.create_user("u3", password="pw")
        client.force_login(u)
        r = client.post(reverse("antares-request-access"),
                        {"pi_group": pig.pk, "request_save_targets": "1",
                         "message": "hello"})
        assert r.status_code == 302, r.content[:400]
        jr = AntaresGroupJoinRequest.objects.get(requester=u)
        assert jr.requested_save_targets is True
        assert jr.message == "hello"

    def test_manage_404_for_non_pi(self, client):
        u = User.objects.create_user("u4", password="pw")
        client.force_login(u)
        r = client.get(reverse("antares-manage-access"))
        assert r.status_code == 404

    def test_manage_renders_for_pi(self, client):
        pi = User.objects.create_user("thepi3", password="pw")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pig = AntaresPIGroup.objects.get(pi=pi)
        req = User.objects.create_user("asker")
        AntaresGroupJoinRequest.objects.create(requester=req, pi_group=pig,
                                               message="pls")
        client.force_login(pi)
        r = client.get(reverse("antares-manage-access"))
        assert r.status_code == 200, r.content[:400]
        assert b"asker" in r.content
        assert b"pls" in r.content

    def test_approve_via_view(self, client):
        pi = User.objects.create_user("thepi4", password="pw")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pig = AntaresPIGroup.objects.get(pi=pi)
        sub = AntaresStreamSubscription.objects.create(owner=pi, topics=["t"])
        req = User.objects.create_user("asker2")
        jr = AntaresGroupJoinRequest.objects.create(requester=req, pi_group=pig)
        client.force_login(pi)
        r = client.post(reverse("antares-decide-join-request", args=[jr.pk]),
                        {"action": "approve", "grant_view": "1", "grant_save": "1"})
        assert r.status_code == 302
        from goats_tom.antares_access import can_save_targets
        assert can_save_targets(req, sub)

    def test_pi_cannot_decide_other_groups_request(self, client):
        pi_a = User.objects.create_user("pia", password="pw")
        AntaresKafkaLogin.objects.create(user=pi_a, api_key="k", api_secret="s")
        pi_b = User.objects.create_user("pib", password="pw")
        AntaresKafkaLogin.objects.create(user=pi_b, api_key="k", api_secret="s")
        pig_b = AntaresPIGroup.objects.get(pi=pi_b)
        req = User.objects.create_user("asker3")
        jr = AntaresGroupJoinRequest.objects.create(requester=req, pi_group=pig_b)
        client.force_login(pi_a)
        r = client.post(reverse("antares-decide-join-request", args=[jr.pk]),
                        {"action": "approve"})
        assert r.status_code == 404, r.status_code
        jr.refresh_from_db()
        assert jr.status == AntaresGroupJoinRequest.STATUS_PENDING

    def test_revoke_via_view(self, client):
        pi = User.objects.create_user("thepi5", password="pw")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pig = AntaresPIGroup.objects.get(pi=pi)
        sub = AntaresStreamSubscription.objects.create(owner=pi, topics=["t"])
        m_user = User.objects.create_user("m1")
        m = AntaresDashboardMembership.objects.create(pi_group=pig, user=m_user,
                                                      can_view_dashboard=True)
        m_user.groups.add(pig.group)
        client.force_login(pi)
        r = client.post(reverse("antares-revoke-membership", args=[m.pk]))
        assert r.status_code == 302
        from goats_tom.antares_access import can_view_dashboard
        assert not can_view_dashboard(m_user, sub)
        assert not m_user.groups.filter(pk=pig.group.pk).exists()
