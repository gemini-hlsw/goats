from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from django.template import Context, Template
from django.utils import timezone
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

MODULE = "goats_tom.templatetags.tom_overrides"


@pytest.fixture
def mod():
    """Import the template-tag module under test."""
    __import__(MODULE)
    return __import__(MODULE, fromlist=["*"])


@pytest.fixture
def target(db):
    """
    Create a reusable SIDEREAL target for tests.
    """
    return Target.objects.create(
        name="TEST_TARGET",
        type="SIDEREAL",
        ra=10.0,
        dec=-10.0,
    )


@dataclass
class DummyData:
    url: str


@dataclass
class DummyProduct:
    data: Any = None
    data_product_type: str | None = None


def test__define_data_product_type_sets_fits_file_on_fits_fz(mod):
    p1 = DummyProduct(data=DummyData(url="http://x/y/file.fits.fz"))
    p2 = DummyProduct(data=DummyData(url="http://x/y/file.fits"))  # should not change
    p3 = DummyProduct(
        data=DummyData(url="http://x/y/file.fits.fz"), data_product_type="already"
    )  # preserved

    out = mod._define_data_product_type([p1, p2, p3])

    assert out[0].data_product_type == "fits_file"
    assert out[1].data_product_type is None
    assert out[2].data_product_type == "already"


def test_define_data_product_type_tag_returns_empty_string_and_mutates(mod):
    p = DummyProduct(data=DummyData(url="http://x/y/file.fits.fz"))
    rendered = mod.define_data_product_type([p])

    assert rendered == ""
    assert p.data_product_type == "fits_file"


def test_goats_dataproduct_list_for_observation_saved_paginates_and_defines_type(
    mocker, mod
):
    """
    Covers:
    - request.GET["page_saved"]
    - pagination with page size 25
    - _define_data_product_type called on paginator.get_page(page)
    """
    # 30 items ensures pagination exists
    saved = [
        DummyProduct(data=DummyData(url=f"http://x/{i}.fits.fz")) for i in range(30)
    ]
    data_products = {"saved": saved}

    request = SimpleNamespace(GET={"page_saved": "1"})

    define_spy = mocker.spy(mod, "_define_data_product_type")

    ctx = mod.goats_dataproduct_list_for_observation_saved(
        data_products=data_products,
        request=request,
        observation_record=SimpleNamespace(pk=123),
    )

    assert "products_page" in ctx
    assert "observation_record" in ctx

    # ensure we paginated (page size is 25)
    products_page = ctx["products_page"]
    assert len(products_page.object_list) == 25

    # ensure define was applied to the page object
    define_spy.assert_called_once()
    for p in products_page.object_list:
        assert p.data_product_type == "fits_file"


@dataclass
class DummyDatum:
    value: Any
    timestamp: datetime


class DummyQS(list):
    """A minimal chainable queryset-like object."""

    def filter(self, **kwargs):
        # For test purposes, return self (or you can implement filtering if you want)
        return self


def _make_deserialized():
    # SpectrumSerializer().deserialize(datum.value) returns an object with:
    #   .wavelength.value and .flux.value
    return SimpleNamespace(
        wavelength=SimpleNamespace(value=[1, 2, 3]),
        flux=SimpleNamespace(value=[10, 20, 30]),
    )


def test_spectroscopy_for_target_permissions_only_true_uses_base_query(
    mocker, mod, settings
):
    """
    Covers:
    - settings.TARGET_PERMISSIONS_ONLY True branch
    - ReducedDatum.objects.filter(...) used
    - get_objects_for_user NOT called
    - offline.plot called and returned into context["plot"]
    """
    settings.TARGET_PERMISSIONS_ONLY = True

    # Patch ReducedDatum.objects.filter(...) to return a chainable QS of datums
    datums = DummyQS(
        [
            DummyDatum(
                value={"raw": 1}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc)
            ),
            DummyDatum(
                value={"raw": 2}, timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc)
            ),
        ]
    )
    mocker.patch(f"{MODULE}.ReducedDatum.objects.filter", return_value=datums)

    get_objs = mocker.patch(f"{MODULE}.get_objects_for_user")
    # Avoid real plotly
    mocker.patch(f"{MODULE}.offline.plot", return_value="<div>plot</div>")
    # Avoid real deserialization
    deserialize = mocker.patch(
        f"{MODULE}.SpectrumSerializer.deserialize", return_value=_make_deserialized()
    )

    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    target = SimpleNamespace(pk=1)

    out = mod.spectroscopy_for_target(context, target, dataproduct=None)

    assert out["target"] is target
    assert out["plot"] == "<div>plot</div>"

    get_objs.assert_not_called()
    assert deserialize.call_count == 2


def test_spectroscopy_for_target_permissions_only_false_uses_get_objects_for_user(
    mocker, mod, settings
):
    """
    Covers:
    - settings.TARGET_PERMISSIONS_ONLY False branch
    - get_objects_for_user called with correct permission and klass=base_query
    """
    settings.TARGET_PERMISSIONS_ONLY = False

    base_query = DummyQS(
        [
            DummyDatum(
                value={"raw": 1}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc)
            )
        ]
    )

    # ReducedDatum.objects.filter(...) returns base_query; later get_objects_for_user(...) returns datums to iterate
    mocker.patch(f"{MODULE}.ReducedDatum.objects.filter", return_value=base_query)

    datums = DummyQS(
        [
            DummyDatum(
                value={"raw": 9}, timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc)
            )
        ]
    )
    get_objs = mocker.patch(f"{MODULE}.get_objects_for_user", return_value=datums)

    mocker.patch(f"{MODULE}.offline.plot", return_value="<div>plot</div>")
    mocker.patch(
        f"{MODULE}.SpectrumSerializer.deserialize", return_value=_make_deserialized()
    )

    user = SimpleNamespace(username="u")
    context = {"request": SimpleNamespace(user=user)}
    target = SimpleNamespace(pk=1)

    out = mod.spectroscopy_for_target(context, target, dataproduct=None)

    assert out["plot"] == "<div>plot</div>"
    get_objs.assert_called_once()
    args, kwargs = get_objs.call_args
    assert args[0] is user
    assert args[1] == "tom_dataproducts.view_reduceddatum"
    assert kwargs["klass"] is base_query


def test_spectroscopy_for_target_filters_by_dataproduct_when_provided(
    mocker, mod, settings
):
    """
    Covers:
    - if dataproduct: base_query = base_query.filter(data_product=dataproduct)
    """
    settings.TARGET_PERMISSIONS_ONLY = True

    base_query = DummyQS(
        [
            DummyDatum(
                value={"raw": 1}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc)
            )
        ]
    )

    filter_mock = mocker.Mock(return_value=base_query)
    # Make the first filter call return an object with a .filter for the dataproduct clause
    first_qs = SimpleNamespace(filter=filter_mock)
    mocker.patch(f"{MODULE}.ReducedDatum.objects.filter", return_value=first_qs)

    mocker.patch(f"{MODULE}.offline.plot", return_value="<div>plot</div>")
    mocker.patch(
        f"{MODULE}.SpectrumSerializer.deserialize", return_value=_make_deserialized()
    )

    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    target = SimpleNamespace(pk=1)
    dataproduct = SimpleNamespace(pk=99)

    out = mod.spectroscopy_for_target(context, target, dataproduct=dataproduct)

    assert out["plot"] == "<div>plot</div>"
    filter_mock.assert_called_once_with(data_product=dataproduct)


@pytest.mark.django_db
def test_goats_recent_photometry_returns_expected_context(target):
    from goats_tom.templatetags.tom_overrides import goats_recent_photometry

    rd_magnitude = ReducedDatum.objects.create(
        target=target,
        data_type="photometry",
        timestamp=timezone.now(),
        value={"magnitude": 18.2},
        source_name="ANTARES",
    )

    rd_limit = ReducedDatum.objects.create(
        target=target,
        data_type="photometry",
        timestamp=timezone.now() + timedelta(seconds=1),
        value={"limit": 20.1},
        source_name="ANTARES",
    )

    context = goats_recent_photometry(target, limit=10)

    assert len(context["data"]) == 2
    assert context["data"][0]["limit"] is True
    assert context["data"][1]["limit"] is False


@pytest.mark.django_db
def test_goats_recent_photometry_respects_limit_argument(target):
    from goats_tom.templatetags.tom_overrides import goats_recent_photometry
    from django.utils import timezone
    from datetime import timedelta
    from tom_dataproducts.models import ReducedDatum

    now = timezone.now()

    for i in range(5):
        ReducedDatum.objects.create(
            target=target,
            data_type="photometry",
            timestamp=now + timedelta(seconds=i),
            value={"magnitude": 19.0 + i, "filter": "r"},
            source_name="ANTARES",
        )

    context = goats_recent_photometry(target, limit=3)
    assert len(context["data"]) == 3


@pytest.mark.django_db
def test_goats_recent_photometry_empty_case(target):
    from goats_tom.templatetags.tom_overrides import goats_recent_photometry

    context = goats_recent_photometry(target, limit=5)
    assert context["data"] == []


@pytest.mark.django_db
def test_goats_recent_photometry_renders_template(target):
    ReducedDatum.objects.create(
        target=target,
        data_type="photometry",
        timestamp=timezone.now(),
        value={"magnitude": 18.5},
        source_name="ANTARES",
    )

    template = Template("""
        {% load tom_overrides %}
        {% goats_recent_photometry target limit=1 %}
    """)

    html = template.render(Context({"target": target}))

    assert "Recent Photometry" in html
    assert "Refresh" in html
