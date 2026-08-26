from datetime import datetime, timedelta, timezone

from django.test import TestCase
from django.urls import reverse
from tom_alerts.models import BrokerQuery
from tom_observations.models import ObservationTemplate
from tom_targets.models import Target
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import UserFactory

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
        self.assertIn("?order=-created", content)

    def test_sortable_header_toggles_when_sorted(self):
        response = self.client.get(reverse(self.url_name), {"order": "-created"})
        self.assertIn("?order=created", response.content.decode())


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
