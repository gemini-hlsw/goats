from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from tom_alerts.models import BrokerQuery
from tom_dataproducts.models import DataProduct
from tom_observations.models import (
    ObservationGroup,
    ObservationRecord,
    ObservationTemplate,
)
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.models import Target
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import DataProductFactory, UserFactory

OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)


def set_created(model, pk, created):
    """Overwrite an ``auto_now_add`` timestamp so ordering is deterministic."""
    model.objects.filter(pk=pk).update(created=created)


class ListOrderingTestMixin:
    """Shared assertions for the date-orderable list views."""

    url_name: str
    context_key: str = "object_list"
    created_label: str = "Created (UTC)"

    def setUp(self):
        self.user = UserFactory(is_superuser=True, is_staff=True)
        self.client.force_login(self.user)

    def get_ids(self, order=None):
        url = reverse(self.url_name)
        response = self.client.get(url, {"order": order} if order else {})
        self.assertEqual(response.status_code, 200)
        return [obj.pk for obj in response.context[self.context_key]]

    def test_defaults_to_newest_first(self):
        self.assertEqual(self.get_ids(), [self.newer.pk, self.older.pk])

    def test_ascending_order(self):
        self.assertEqual(self.get_ids("created"), [self.older.pk, self.newer.pk])

    def test_descending_order(self):
        self.assertEqual(self.get_ids("-created"), [self.newer.pk, self.older.pk])

    def test_unknown_order_falls_back_to_default(self):
        self.assertEqual(self.get_ids("password"), [self.newer.pk, self.older.pk])

    def test_renders_sortable_header(self):
        response = self.client.get(reverse(self.url_name))
        content = response.content.decode()
        self.assertIn(self.created_label, content)
        self.assertIn("?order=created", content)

    def test_sortable_header_toggles_when_sorted(self):
        response = self.client.get(reverse(self.url_name), {"order": "-created"})
        self.assertIn("?order=created", response.content.decode())

    def test_equal_dates_use_primary_key_as_tiebreaker(self):
        set_created(type(self.newer), self.newer.pk, OLD)
        self.assertEqual(self.get_ids(), [self.newer.pk, self.older.pk])
        self.assertEqual(self.get_ids("created"), [self.older.pk, self.newer.pk])


class TestTargetListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "target-list"

    def setUp(self):
        super().setUp()
        self.older = SiderealTargetFactory.create()
        self.newer = SiderealTargetFactory.create()
        set_created(Target, self.older.pk, OLD)


class TestObservationTemplateListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "observation-template-list"
    created_label = "Created"

    def setUp(self):
        super().setUp()
        self.older = ObservationTemplate.objects.create(
            name="older", facility="LCO", parameters={}
        )
        self.newer = ObservationTemplate.objects.create(
            name="newer", facility="LCO", parameters={}
        )
        set_created(ObservationTemplate, self.older.pk, OLD)


class TestBrokerQueryListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "brokerquery-list"
    created_label = "Created"

    def setUp(self):
        super().setUp()
        self.older = BrokerQuery.objects.create(
            name="older", broker="ANTARES", parameters={}, last_run=OLD
        )
        self.newer = BrokerQuery.objects.create(
            name="newer", broker="ANTARES", parameters={}, last_run=OLD + timedelta(1)
        )
        set_created(BrokerQuery, self.older.pk, OLD)

    def test_orders_by_last_run(self):
        self.assertEqual(self.get_ids("last_run"), [self.older.pk, self.newer.pk])
        self.assertEqual(self.get_ids("-last_run"), [self.newer.pk, self.older.pk])

    def test_queries_never_run_sort_last(self):
        never_run = BrokerQuery.objects.create(
            name="never run", broker="ANTARES", parameters={}
        )
        self.assertEqual(self.get_ids("last_run")[-1], never_run.pk)
        self.assertEqual(self.get_ids("-last_run")[-1], never_run.pk)

    def test_renders_last_run_sortable_header(self):
        content = self.client.get(reverse(self.url_name)).content.decode()
        self.assertIn("Last Run", content)
        self.assertIn("?order=-last_run", content)


class TestOrderingSurvivesPagination(TestCase):
    """A page beyond the first must keep the requested ordering."""

    def setUp(self):
        self.user = UserFactory(is_superuser=True, is_staff=True)
        self.client.force_login(self.user)
        self.targets = []
        for index in range(25):
            target = SiderealTargetFactory.create()
            set_created(Target, target.pk, OLD + timedelta(days=index))
            self.targets.append(target)

    def test_second_page_continues_ascending_order(self):
        response = self.client.get(
            reverse("target-list"), {"order": "created", "page": 2}
        )
        self.assertEqual(
            [obj.pk for obj in response.context["object_list"]],
            [target.pk for target in self.targets[20:]],
        )


class TestObservationListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "observation-list"

    def setUp(self):
        super().setUp()
        target = SiderealTargetFactory.create()
        self.older = ObservingRecordFactory.create(target_id=target.id)
        self.newer = ObservingRecordFactory.create(target_id=target.id)
        set_created(ObservationRecord, self.older.pk, OLD)

    def test_equal_dates_use_primary_key_as_tiebreaker(self):
        """Observations sharing a date fall back to the observation id."""
        ObservationRecord.objects.filter(pk=self.newer.pk).update(
            created=OLD, observation_id="A"
        )
        ObservationRecord.objects.filter(pk=self.older.pk).update(observation_id="B")
        # Alphabetical whichever direction is asked for.
        self.assertEqual(self.get_ids(), [self.newer.pk, self.older.pk])
        self.assertEqual(self.get_ids("created"), [self.newer.pk, self.older.pk])

    def test_header_order_takes_precedence_over_form_ordering(self):
        response = self.client.get(
            reverse(self.url_name), {"ordering": "created", "order": "-created"}
        )
        self.assertEqual(
            [obj.pk for obj in response.context["object_list"]],
            [self.newer.pk, self.older.pk],
        )
        self.assertEqual(response.context["current_order"], "-created")

    def test_form_ordering_is_preserved_without_header_order(self):
        response = self.client.get(reverse(self.url_name), {"ordering": "created"})
        self.assertEqual(
            [obj.pk for obj in response.context["object_list"]],
            [self.older.pk, self.newer.pk],
        )
        self.assertEqual(response.context["current_order"], "created")

    def test_html_renders_only_the_requested_page(self):
        ObservingRecordFactory.create_batch(24, target_id=self.older.target_id)
        # All dates tie so this also exercises deterministic pagination.
        ObservationRecord.objects.all().update(created=OLD)
        for order in ("created", "-created"):
            response = self.client.get(
                reverse(self.url_name), {"page": 2, "order": order}
            )
            rows = list(response.context["object_list"])
            self.assertEqual(len(rows), 1)
            content = response.content.decode()
            self.assertEqual(content.count('name="selected"'), 1)
            # Ties fall back to the observation id, ascending either way.
            last = ObservationRecord.objects.order_by("observation_id", "pk").last()
            self.assertEqual(rows[0].pk, last.pk)
            self.assertIn(f'name="selected" value="{last.pk}"', content)


class TestDataProductListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "dataproduct-list"

    def setUp(self):
        super().setUp()
        self.older = DataProductFactory.create()
        self.newer = DataProductFactory.create()
        set_created(DataProduct, self.older.pk, OLD)

    def test_equal_dates_use_primary_key_as_tiebreaker(self):
        """Products sharing a date fall back to the file name."""
        DataProduct.objects.filter(pk=self.newer.pk).update(created=OLD, data="a.fits")
        DataProduct.objects.filter(pk=self.older.pk).update(data="b.fits")
        # Alphabetical whichever direction is asked for.
        self.assertEqual(self.get_ids(), [self.newer.pk, self.older.pk])
        self.assertEqual(self.get_ids("created"), [self.newer.pk, self.older.pk])


class TestObservationGroupListOrdering(ListOrderingTestMixin, TestCase):
    url_name = "observation-group-list"

    def setUp(self):
        super().setUp()
        self.older = ObservationGroup.objects.create(name="older")
        self.newer = ObservationGroup.objects.create(name="newer")
        set_created(ObservationGroup, self.older.pk, OLD)

    def test_equal_dates_use_primary_key_as_tiebreaker(self):
        """Groups keep the alphabetical tiebreaker TOMToolkit gives them."""
        set_created(ObservationGroup, self.newer.pk, OLD)
        # "newer" sorts before "older" by name, whichever direction is asked for.
        self.assertEqual(self.get_ids(), [self.newer.pk, self.older.pk])
        self.assertEqual(self.get_ids("created"), [self.newer.pk, self.older.pk])


class TestUserListOrdering(TestCase):
    """The user list is rendered by a template tag, so assert on the markup."""

    def setUp(self):
        self.user = UserFactory(is_superuser=True, is_staff=True, username="newer")
        self.client.force_login(self.user)
        self.older = UserFactory(username="older")
        User.objects.filter(pk=self.older.pk).update(date_joined=OLD)

    def usernames_in_order(self, order=None):
        response = self.client.get(
            reverse("user-list"), {"order": order} if order else {}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        return sorted(
            ["newer", "older"], key=lambda name: content.index(f">{name}</td>")
        )

    def test_defaults_to_newest_first(self):
        self.assertEqual(self.usernames_in_order(), ["newer", "older"])

    def test_ascending_order(self):
        self.assertEqual(self.usernames_in_order("date_joined"), ["older", "newer"])

    def test_renders_sortable_header(self):
        content = self.client.get(reverse("user-list")).content.decode()
        self.assertIn("Joined (UTC)", content)
        self.assertIn("?order=date_joined", content)
