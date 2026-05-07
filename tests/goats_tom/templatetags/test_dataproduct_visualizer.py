from __future__ import annotations

from types import SimpleNamespace

import pytest
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct

MODULE = "goats_tom.templatetags.dataproduct_visualizer"


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


def _call(mocker, mod, target, data_type="spectroscopy", dataproducts=None):
    dataproducts = dataproducts or []
    fake_qs = SimpleNamespace(filter=lambda *a, **kw: dataproducts)
    mocker.patch(f"{MODULE}.DataProduct.objects.filter", return_value=fake_qs)
    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    return mod.dataproduct_visualizer(context, target, data_type=data_type)


@pytest.mark.parametrize("key", ["target", "dataproducts", "data_type"])
def test_dataproduct_visualizer_context_keys(mocker, mod, target, key):
    assert key in _call(mocker, mod, target)


@pytest.mark.parametrize(
    "data_type", ["spectroscopy", "photometry", "fits_file", "custom"]
)
def test_dataproduct_visualizer_data_type_forwarded(mocker, mod, target, data_type):
    result = _call(mocker, mod, target, data_type=data_type)
    assert result["data_type"] == data_type


def test_dataproduct_visualizer_target_forwarded(mocker, mod, target):
    result = _call(mocker, mod, target)
    assert result["target"] is target


@pytest.mark.parametrize(
    "data_type, expected_q_calls",
    [
        ("spectroscopy", 3),  # base Q + fits_file Q + fits.fz Q
        ("photometry", 1),  # only base Q
        ("fits_file", 1),
        ("custom", 1),
    ],
)
def test_dataproduct_visualizer_filter_composition(
    mocker, mod, target, data_type, expected_q_calls
):
    q_mock = mocker.patch(
        f"{MODULE}.Q", wraps=__import__("django.db.models", fromlist=["Q"]).Q
    )
    _call(mocker, mod, target, data_type=data_type)
    assert q_mock.call_count == expected_q_calls


@pytest.mark.django_db
@pytest.mark.parametrize(
    "product_type, data_suffix, data_type, should_appear",
    [
        ("spectroscopy", ".fits", "spectroscopy", True),
        ("fits_file", ".fits", "spectroscopy", True),
        ("photometry", ".fits", "spectroscopy", False),
        ("photometry", ".fits", "photometry", True),
        ("spectroscopy", ".fits", "photometry", False),
        ("fits_file", ".fits", "photometry", False),
    ],
)
def test_dataproduct_visualizer_filters_by_type(
    target, product_type, data_suffix, data_type, should_appear
):
    from goats_tom.templatetags.dataproduct_visualizer import dataproduct_visualizer

    dp = DataProduct.objects.create(
        target=target,
        data_product_type=product_type,
        data=f"path/to/file{data_suffix}",
    )
    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    result = dataproduct_visualizer(context, target, data_type=data_type)
    ids = [d.pk for d in result["dataproducts"]]
    if should_appear:
        assert dp.pk in ids
    else:
        assert dp.pk not in ids


@pytest.mark.django_db
def test_dataproduct_visualizer_spectroscopy_includes_fits_fz(target):
    from goats_tom.templatetags.dataproduct_visualizer import dataproduct_visualizer

    dp = DataProduct.objects.create(
        target=target,
        data_product_type="spectroscopy",
        data="path/to/file.fits.fz",
    )
    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    result = dataproduct_visualizer(context, target, data_type="spectroscopy")
    assert dp.pk in [d.pk for d in result["dataproducts"]]


@pytest.mark.django_db
def test_dataproduct_visualizer_returns_only_products_for_target(target, db):
    from goats_tom.templatetags.dataproduct_visualizer import dataproduct_visualizer

    other_target = Target.objects.create(name="OTHER", type="SIDEREAL", ra=0.0, dec=0.0)
    dp_mine = DataProduct.objects.create(
        target=target, data_product_type="spectroscopy", data="a.fits"
    )
    dp_other = DataProduct.objects.create(
        target=other_target, data_product_type="spectroscopy", data="b.fits"
    )

    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    result = dataproduct_visualizer(context, target, data_type="spectroscopy")
    ids = [d.pk for d in result["dataproducts"]]
    assert dp_mine.pk in ids
    assert dp_other.pk not in ids


@pytest.mark.django_db
@pytest.mark.parametrize("data_type", ["spectroscopy", "photometry"])
def test_dataproduct_visualizer_empty_when_no_products(target, data_type):
    from goats_tom.templatetags.dataproduct_visualizer import dataproduct_visualizer

    context = {"request": SimpleNamespace(user=SimpleNamespace())}
    result = dataproduct_visualizer(context, target, data_type=data_type)
    assert list(result["dataproducts"]) == []
