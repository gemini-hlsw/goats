"""Ordering and pagination contracts for the GOATS list APIs."""

from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import (
    DataProductsViewSet,
    DRAGONSFilesViewSet,
    DRAGONSReduceViewSet,
    DRAGONSRunsViewSet,
    ReducedDatumViewSet,
)
from goats_tom.tests.factories import (
    DataProductFactory,
    DRAGONSFileFactory,
    DRAGONSReduceFactory,
    DRAGONSRunFactory,
    ReducedDatumFactory,
    UserFactory,
)

DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def set_date(record, date_field, value):
    """Set the source date, including a DRAGONS file's related product date."""
    if date_field == "data_product__created":
        record = record.data_product
        date_field = "created"
    type(record).objects.filter(pk=record.pk).update(**{date_field: value})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "viewset,factory,date_field",
    [
        (DataProductsViewSet, DataProductFactory, "created"),
        (ReducedDatumViewSet, ReducedDatumFactory, "timestamp"),
        (DRAGONSFilesViewSet, DRAGONSFileFactory, "data_product__created"),
        (DRAGONSReduceViewSet, DRAGONSReduceFactory, "created_at"),
        (DRAGONSRunsViewSet, DRAGONSRunFactory, "created"),
    ],
)
def test_newest_first_with_date_ties_across_pages(viewset, factory, date_field):
    first, second, older = factory.create_batch(3)
    for record in (first, second):
        set_date(record, date_field, DATE)
    set_date(older, date_field, DATE - timedelta(days=1))
    user = UserFactory(is_superuser=True)
    view = viewset.as_view({"get": "list"})
    actual = []
    for offset in range(3):
        request = APIRequestFactory().get("/", {"limit": 1, "offset": offset})
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["count"] == 3
        # ReducedDatum's public serializer exposes data_product, but no ID.
        key = "data_product" if viewset is ReducedDatumViewSet else "id"
        actual.extend(row[key] for row in response.data["results"])
    expected = [second, first, older]
    assert actual == [
        row.data_product_id if viewset is ReducedDatumViewSet else row.pk
        for row in expected
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("group_by,group_key", [("all", "All"), ("object", "Vega")])
def test_grouped_dragons_files_use_the_same_order(group_by, group_key):
    first, second, older = DRAGONSFileFactory.create_batch(
        3, astrodata_descriptors={"object": "Vega"}
    )
    for record in (first, second):
        set_date(record, "data_product__created", DATE)
    set_date(older, "data_product__created", DATE - timedelta(days=1))
    request = APIRequestFactory().get("/", {"group_by": [group_by]})
    force_authenticate(request, user=UserFactory())
    response = DRAGONSFilesViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert [row["id"] for row in response.data[group_key]["files"]] == [
        second.pk,
        first.pk,
        older.pk,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("group_by,group_key", [("all", "All"), ("object", "Vega")])
def test_grouped_dragons_files_expose_the_created_date(group_by, group_key):
    dragons_file = DRAGONSFileFactory(astrodata_descriptors={"object": "Vega"})
    set_date(dragons_file, "data_product__created", DATE)
    request = APIRequestFactory().get("/", {"group_by": [group_by]})
    force_authenticate(request, user=UserFactory())

    response = DRAGONSFilesViewSet.as_view({"get": "list"})(request)

    assert response.status_code == 200
    assert response.data[group_key]["files"][0]["created"] == "2024-01-01T00:00:00Z"


@pytest.mark.django_db
def test_dragons_file_detail_exposes_the_created_date():
    dragons_file = DRAGONSFileFactory()
    set_date(dragons_file, "data_product__created", DATE)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=UserFactory())

    response = DRAGONSFilesViewSet.as_view({"get": "retrieve"})(
        request, pk=dragons_file.pk
    )

    assert response.status_code == 200
    assert response.data["created"] == "2024-01-01T00:00:00Z"


@pytest.mark.django_db
@pytest.mark.parametrize("group_by,group_key", [("all", "All"), ("object", "Vega")])
def test_grouped_dates_match_detail_with_microseconds(group_by, group_key, settings):
    settings.TIME_ZONE = "America/Santiago"
    record = DRAGONSFileFactory(astrodata_descriptors={"object": "Vega"})
    set_date(record, "data_product__created", DATE.replace(microsecond=123456))
    user = UserFactory()
    request = APIRequestFactory().get("/", {"group_by": [group_by]})
    force_authenticate(request, user=user)
    grouped = DRAGONSFilesViewSet.as_view({"get": "list"})(request)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    detail = DRAGONSFilesViewSet.as_view({"get": "retrieve"})(request, pk=record.pk)
    assert grouped.data[group_key]["files"][0]["created"] == detail.data["created"]
    assert detail.data["created"] == "2024-01-01T00:00:00.123456Z"
