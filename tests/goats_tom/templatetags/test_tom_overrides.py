from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from django.template import Context, Template
from datetime import datetime, timedelta, timezone
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

MODULE = "goats_tom.templatetags.tom_overrides"


@pytest.fixture
def mod():
    __import__(MODULE)
    return __import__(MODULE, fromlist=["*"])


@pytest.fixture
def target(db):
    return Target.objects.create(
        name="ANTTEST_TARGET",
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


@dataclass
class DummyDatum:
    value: Any
    timestamp: datetime


class DummyQS(list):
    def filter(self, **kwargs):
        return self


def _make_deserialized():
    return SimpleNamespace(
        wavelength=SimpleNamespace(value=[1, 2, 3]),
        flux=SimpleNamespace(value=[10, 20, 30]),
    )


def _make_rd(pk=1, timestamp="2024-01-01", source_name="ZTF", value=None):
    return SimpleNamespace(
        pk=pk,
        timestamp=timestamp,
        source_name=source_name,
        value=value or {"magnitude": 18.0},
    )


def _call_get_photometry_data(
    mocker, mod, target, photometry_qs=None, target_share=False, data_sharing=None
):
    photometry_qs = photometry_qs or []
    fake_qs = SimpleNamespace(order_by=lambda *a: photometry_qs)
    mocker.patch(f"{MODULE}.ReducedDatum.objects.filter", return_value=fake_qs)
    form_instance = SimpleNamespace(
        fields={
            "data_type": SimpleNamespace(widget=None),
            "share_destination": SimpleNamespace(choices=[("hermes", "Hermes")]),
        }
    )
    mocker.patch(f"{MODULE}.DataShareForm", return_value=form_instance)
    mocker.patch(f"{MODULE}.settings.DATA_SHARING", data_sharing, create=True)
    context = {"request": SimpleNamespace(user=SimpleNamespace(username="tester"))}
    return mod.get_photometry_data(context, target, target_share=target_share)


def _setup_spectroscopy(mocker, settings, permissions_only, datums):
    settings.TARGET_PERMISSIONS_ONLY = permissions_only
    mocker.patch(f"{MODULE}.ReducedDatum.objects.filter", return_value=datums)
    get_objs_mock = mocker.patch(f"{MODULE}.get_objects_for_user", return_value=datums)
    mocker.patch(f"{MODULE}.offline.plot", return_value="<div>plot</div>")
    deserialize_mock = mocker.patch(
        f"{MODULE}.SpectrumSerializer.deserialize", return_value=_make_deserialized()
    )
    return deserialize_mock, get_objs_mock


@pytest.mark.parametrize(
    "url, preset, expected_type",
    [
        ("http://x/y/file.fits.fz", None, "fits_file"),
        ("http://x/y/file.fits", None, None),
        ("http://x/y/file.fits.fz", "already", "already"),
    ],
)
def test__define_data_product_type(mod, url, preset, expected_type):
    p = DummyProduct(data=DummyData(url=url), data_product_type=preset)
    assert mod._define_data_product_type([p])[0].data_product_type == expected_type


def test_define_data_product_type_tag_returns_empty_string_and_mutates(mod):
    p = DummyProduct(data=DummyData(url="http://x/y/file.fits.fz"))
    assert mod.define_data_product_type([p]) == ""
    assert p.data_product_type == "fits_file"


@pytest.mark.parametrize(
    "total_items, page_size, expected_page_len",
    [
        (30, 25, 25),
        (10, 25, 10),
        (25, 25, 25),
        (26, 25, 25),
    ],
)
def test_goats_dataproduct_list_for_observation_saved_paginates(
    mocker, mod, total_items, page_size, expected_page_len
):
    saved = [
        DummyProduct(data=DummyData(url=f"http://x/{i}.fits.fz"))
        for i in range(total_items)
    ]
    mocker.patch(f"{MODULE}.PAGE_SIZE_SAVED", page_size, create=True)
    ctx = mod.goats_dataproduct_list_for_observation_saved(
        data_products={"saved": saved},
        request=SimpleNamespace(GET={"page_saved": "1"}),
        observation_record=SimpleNamespace(pk=123),
    )
    assert len(ctx["products_page"].object_list) == expected_page_len


@pytest.mark.parametrize("key", ["products_page", "observation_record"])
def test_goats_dataproduct_list_for_observation_saved_context_keys(mocker, mod, key):
    saved = [
        DummyProduct(data=DummyData(url=f"http://x/{i}.fits.fz")) for i in range(5)
    ]
    ctx = mod.goats_dataproduct_list_for_observation_saved(
        data_products={"saved": saved},
        request=SimpleNamespace(GET={"page_saved": "1"}),
        observation_record=SimpleNamespace(pk=123),
    )
    assert key in ctx


def test_goats_dataproduct_list_for_observation_saved_defines_type(mocker, mod):
    saved = [
        DummyProduct(data=DummyData(url=f"http://x/{i}.fits.fz")) for i in range(5)
    ]
    define_spy = mocker.spy(mod, "_define_data_product_type")
    ctx = mod.goats_dataproduct_list_for_observation_saved(
        data_products={"saved": saved},
        request=SimpleNamespace(GET={"page_saved": "1"}),
        observation_record=SimpleNamespace(pk=123),
    )
    define_spy.assert_called_once()
    assert all(
        p.data_product_type == "fits_file" for p in ctx["products_page"].object_list
    )


@pytest.mark.parametrize(
    "permissions_only, datum_count, expect_get_objects_called",
    [
        (True, 2, False),
        (False, 1, True),
    ],
)
def test_spectroscopy_for_target_permission_branch(
    mocker, mod, settings, permissions_only, datum_count, expect_get_objects_called
):
    datums = DummyQS(
        [
            DummyDatum(
                value={"raw": i},
                timestamp=datetime(2025, 1, i + 1, tzinfo=timezone.utc),
            )
            for i in range(datum_count)
        ]
    )
    deserialize, get_objs = _setup_spectroscopy(
        mocker, settings, permissions_only, datums
    )
    user = SimpleNamespace(username="u")
    out = mod.spectroscopy_for_target(
        {"request": SimpleNamespace(user=user)}, SimpleNamespace(pk=1), dataproduct=None
    )
    assert out["target"].pk == 1
    assert out["plot"] == "<div>plot</div>"
    assert deserialize.call_count == datum_count
    if expect_get_objects_called:
        get_objs.assert_called_once()
    else:
        get_objs.assert_not_called()


@pytest.mark.parametrize("context_key", ["target", "plot"])
def test_spectroscopy_for_target_context_keys(mocker, mod, settings, context_key):
    datums = DummyQS(
        [
            DummyDatum(
                value={"raw": 1}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc)
            )
        ]
    )
    _setup_spectroscopy(mocker, settings, True, datums)
    out = mod.spectroscopy_for_target(
        {"request": SimpleNamespace(user=SimpleNamespace())},
        SimpleNamespace(pk=1),
        dataproduct=None,
    )
    assert context_key in out


def test_spectroscopy_for_target_filters_by_dataproduct_when_provided(
    mocker, mod, settings
):
    base_query = DummyQS(
        [
            DummyDatum(
                value={"raw": 1}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc)
            )
        ]
    )
    filter_mock = mocker.Mock(return_value=base_query)
    mocker.patch(
        f"{MODULE}.ReducedDatum.objects.filter",
        return_value=SimpleNamespace(filter=filter_mock),
    )
    mocker.patch(f"{MODULE}.offline.plot", return_value="<div>plot</div>")
    mocker.patch(
        f"{MODULE}.SpectrumSerializer.deserialize", return_value=_make_deserialized()
    )
    settings.TARGET_PERMISSIONS_ONLY = True
    dataproduct = SimpleNamespace(pk=99)
    out = mod.spectroscopy_for_target(
        {"request": SimpleNamespace(user=SimpleNamespace())},
        SimpleNamespace(pk=1),
        dataproduct=dataproduct,
    )
    assert out["plot"] == "<div>plot</div>"
    filter_mock.assert_called_once_with(data_product=dataproduct)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values, expected_limits",
    [
        (
            [{"magnitude": 18.2, "filter": "r"}, {"limit": 20.1, "filter": "R"}],
            [True, False],
        ),
        (
            [{"limit": 20.1, "filter": "R"}, {"magnitude": 18.2, "filter": "r"}],
            [False, True],
        ),
        (
            [{"magnitude": 18.2, "filter": "r"}, {"magnitude": 19.0, "filter": "g"}],
            [False, False],
        ),
        (
            [{"limit": 20.0, "filter": "r"}, {"limit": 21.0, "filter": "g"}],
            [True, True],
        ),
    ],
)
def test_goats_recent_photometry_limit_flag(target, values, expected_limits):
    from goats_tom.templatetags.tom_overrides import goats_recent_photometry

    now = datetime.now(tz=timezone.utc)
    for i, value in enumerate(values):
        ReducedDatum.objects.create(
            target=target,
            data_type="photometry",
            timestamp=now + timedelta(seconds=i),
            value=value,
            source_name="ANTARES",
        )
    context = goats_recent_photometry(target, limit=10)
    assert [d["limit"] for d in context["data"]] == expected_limits


@pytest.mark.django_db
@pytest.mark.parametrize(
    "total, limit, expected_count",
    [
        (5, 3, 3),
        (5, 5, 5),
        (5, 10, 5),
        (0, 5, 0),
    ],
)
def test_goats_recent_photometry_respects_limit(target, total, limit, expected_count):
    from goats_tom.templatetags.tom_overrides import goats_recent_photometry

    now = datetime.now(tz=timezone.utc)
    for i in range(total):
        ReducedDatum.objects.create(
            target=target,
            data_type="photometry",
            timestamp=now + timedelta(seconds=i),
            value={"magnitude": 19.0 + i, "filter": "r"},
            source_name="ANTARES",
        )
    assert len(goats_recent_photometry(target, limit=limit)["data"]) == expected_count


@pytest.mark.django_db
@pytest.mark.parametrize("expected_string", ["Recent Photometry", "Update"])
def test_goats_recent_photometry_renders_template(target, expected_string):
    ReducedDatum.objects.create(
        target=target,
        data_type="photometry",
        timestamp=datetime.now(tz=timezone.utc),
        value={"magnitude": 18.5, "filter": "i"},
        source_name="ANTARES",
    )
    html = Template(
        "{% load tom_overrides %}{% goats_recent_photometry target limit=1 %}"
    ).render(Context({"target": target}))
    assert expected_string in html


@pytest.mark.parametrize(
    "key",
    [
        "data",
        "target",
        "target_data_share_form",
        "sharing_destinations",
        "hermes_sharing",
        "target_share",
    ],
)
def test_get_photometry_data_context_keys(mocker, mod, target, key):
    assert key in _call_get_photometry_data(mocker, mod, target)


@pytest.mark.parametrize("flag", [True, False])
def test_get_photometry_data_target_share_flag(mocker, mod, target, flag):
    assert (
        _call_get_photometry_data(mocker, mod, target, target_share=flag)[
            "target_share"
        ]
        is flag
    )


@pytest.mark.parametrize(
    "value, expected_magnitude, expected_limit",
    [
        ({"magnitude": 18.5, "filter": "r"}, 18.5, False),
        ({"limit": 19.0, "filter": "o"}, 19.0, True),
        ({"magnitude": 0.0}, 0.0, False),
    ],
)
def test_get_photometry_data_magnitude_and_limit(
    mocker, mod, target, value, expected_magnitude, expected_limit
):
    entry = _call_get_photometry_data(
        mocker, mod, target, photometry_qs=[_make_rd(value=value)]
    )["data"][0]
    assert entry["magnitude"] == expected_magnitude
    assert entry["limit"] is expected_limit


@pytest.mark.parametrize(
    "value, expected_error",
    [
        ({"magnitude": 18.0, "error": 0.05}, 0.05),
        ({"magnitude": 18.0, "magnitude_error": 0.02}, 0.02),
        ({"magnitude": 18.0}, ""),
        ({"magnitude": 18.0, "error": 0.05, "magnitude_error": 0.02}, 0.05),
    ],
)
def test_get_photometry_data_error_fallback(mocker, mod, target, value, expected_error):
    result = _call_get_photometry_data(
        mocker, mod, target, photometry_qs=[_make_rd(value=value)]
    )
    assert result["data"][0]["error"] == expected_error


@pytest.mark.parametrize(
    "field, value_key, provided_value",
    [
        ("filter", "filter", "r"),
        ("mjd", "time", 60000.0),
        ("telescope", "telescope", "P48"),
    ],
)
def test_get_photometry_data_optional_field_present(
    mocker, mod, target, field, value_key, provided_value
):
    rd = _make_rd(value={"magnitude": 18.0, value_key: provided_value})
    assert (
        _call_get_photometry_data(mocker, mod, target, photometry_qs=[rd])["data"][0][
            field
        ]
        == provided_value
    )


@pytest.mark.parametrize("field", ["filter", "mjd", "telescope"])
def test_get_photometry_data_optional_field_defaults_empty(mocker, mod, target, field):
    result = _call_get_photometry_data(
        mocker, mod, target, photometry_qs=[_make_rd(value={"magnitude": 18.0})]
    )
    assert result["data"][0][field] == ""


@pytest.mark.parametrize(
    "data_sharing, expected",
    [
        ({"hermes": {"HERMES_API_KEY": "secret"}}, True),
        ({"hermes": {}}, False),
        (None, False),
        ({}, False),
    ],
)
def test_get_photometry_data_hermes_sharing(
    mocker, mod, target, data_sharing, expected
):
    assert (
        bool(
            _call_get_photometry_data(mocker, mod, target, data_sharing=data_sharing)[
                "hermes_sharing"
            ]
        )
        is expected
    )


@pytest.mark.parametrize("pk", [1, 42, 99, 1000])
def test_get_photometry_data_datum_id_matches_pk(mocker, mod, target, pk):
    result = _call_get_photometry_data(
        mocker, mod, target, photometry_qs=[_make_rd(pk=pk, value={"magnitude": 18.0})]
    )
    assert result["data"][0]["id"] == pk


@pytest.mark.parametrize("photometry_qs", [[], None])
def test_get_photometry_data_empty_returns_empty_list(
    mocker, mod, target, photometry_qs
):
    assert (
        _call_get_photometry_data(
            mocker, mod, target, photometry_qs=photometry_qs or []
        )["data"]
        == []
    )


@pytest.mark.parametrize("pks", [[1, 2, 3], [10, 20, 30], [5]])
def test_get_photometry_data_preserves_order(mocker, mod, target, pks):
    rds = [_make_rd(pk=pk, value={"magnitude": 18.0 + i}) for i, pk in enumerate(pks)]
    assert [
        e["id"]
        for e in _call_get_photometry_data(mocker, mod, target, photometry_qs=rds)[
            "data"
        ]
    ] == pks
