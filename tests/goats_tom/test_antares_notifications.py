"""Tests for per-user notification targeting."""

from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth.models import User

from goats_tom.realtime import NotificationInstance, user_group_name


class TestUserGroupName:
    """Tests for `goats_tom.realtime.groups.user_group_name`."""

    @pytest.mark.django_db()
    def test_named_for_primary_key(self):
        """The group is keyed on pk, so a rename doesn't change it."""
        user = User.objects.create_user("someone")
        assert user_group_name(user) == f"user_{user.pk}"
        user.username = "renamed"
        user.save()
        assert user_group_name(user) == f"user_{user.pk}"

    def test_none_user(self):
        """`None` has no private group."""
        assert user_group_name(None) is None

    def test_anonymous_user(self):
        """An anonymous user has no private group."""
        from django.contrib.auth.models import AnonymousUser

        assert user_group_name(AnonymousUser()) is None

    @pytest.mark.django_db()
    def test_unsaved_user(self):
        """An unsaved user has no pk, so no group."""
        assert user_group_name(User(username="unsaved")) is None


class TestNotificationTargeting:
    """Tests for `NotificationInstance`'s optional `user` argument."""

    def test_defaults_to_broadcast(self):
        """Existing callers keep broadcasting to every client."""
        with patch(
            "goats_tom.realtime.notification_instance.get_channel_layer"
        ) as mock_layer:
            # AsyncMock, since `_send` wraps `group_send` in `async_to_sync`,
            # which rejects a non-async callable.
            mock_layer.return_value.group_send = AsyncMock()
            NotificationInstance.create_and_send(label="L", message="M")
            group = mock_layer.return_value.group_send.call_args[0][0]
        assert group == "updates_group"

    @pytest.mark.django_db()
    def test_targets_single_user(self):
        """Passing a user routes to their private group only."""
        user = User.objects.create_user("target")
        with patch(
            "goats_tom.realtime.notification_instance.get_channel_layer"
        ) as mock_layer:
            mock_layer.return_value.group_send = AsyncMock()
            NotificationInstance.create_and_send(
                label="L", message="M", user=user
            )
            group = mock_layer.return_value.group_send.call_args[0][0]
        assert group == f"user_{user.pk}"

    def test_unaddressable_user_is_dropped_not_broadcast(self):
        """An unaddressable recipient drops the message.

        Falling back to a broadcast would show a private message to everyone,
        which is the exact failure the `user` argument exists to prevent.
        """
        from django.contrib.auth.models import AnonymousUser

        with patch(
            "goats_tom.realtime.notification_instance.get_channel_layer"
        ) as mock_layer:
            mock_layer.return_value.group_send = AsyncMock()
            NotificationInstance.create_and_send(
                label="L", message="M", user=AnonymousUser()
            )
        mock_layer.return_value.group_send.assert_not_called()


@pytest.mark.django_db()
class TestMembershipNotifications:
    """Tests that join request transitions notify the right person."""

    def test_pi_notified_of_new_request(self, django_capture_on_commit_callbacks):
        """The PI, not the requester, is told about a new request."""
        from django.contrib.auth.models import Group

        from goats_tom.antares_membership import create_join_request
        from goats_tom.models import AntaresPIGroup

        pi = User.objects.create_user("thepi")
        asker = User.objects.create_user("theasker")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-thepi"), pi=pi
        )

        with patch.object(NotificationInstance, "create_and_send") as mock_send:
            with django_capture_on_commit_callbacks(execute=True):
                create_join_request(asker, pi_group)

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["user"] == pi
        assert "theasker" in mock_send.call_args.kwargs["message"]

    def test_requester_notified_of_approval(
        self, django_capture_on_commit_callbacks
    ):
        """The requester is told what was actually granted."""
        from django.contrib.auth.models import Group

        from goats_tom.antares_membership import (
            approve_join_request,
            create_join_request,
        )
        from goats_tom.models import AntaresPIGroup

        pi = User.objects.create_user("thepi2")
        asker = User.objects.create_user("theasker2")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-thepi2"), pi=pi
        )
        with django_capture_on_commit_callbacks(execute=True):
            join_request = create_join_request(asker, pi_group)

        with patch.object(NotificationInstance, "create_and_send") as mock_send:
            with django_capture_on_commit_callbacks(execute=True):
                approve_join_request(
                    join_request, decided_by=pi, grant_save=True
                )

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["user"] == asker
        assert "save targets" in mock_send.call_args.kwargs["message"]

    def test_notification_failure_does_not_break_request(
        self, django_capture_on_commit_callbacks
    ):
        """A broken channel layer must not fail the underlying change."""
        from django.contrib.auth.models import Group

        from goats_tom.antares_membership import create_join_request
        from goats_tom.models import AntaresGroupJoinRequest, AntaresPIGroup

        pi = User.objects.create_user("thepi3")
        asker = User.objects.create_user("theasker3")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-thepi3"), pi=pi
        )

        with patch.object(
            NotificationInstance, "create_and_send", side_effect=RuntimeError
        ):
            with django_capture_on_commit_callbacks(execute=True):
                create_join_request(asker, pi_group)

        assert AntaresGroupJoinRequest.objects.filter(requester=asker).exists()
