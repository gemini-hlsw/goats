import pytest
from unittest.mock import Mock, patch

from goats_tom.api_views.status.mixins.base import status_mixins
from goats_tom.api_views.status.mixins.public import (
    ALeRCEPublicStatusMixin,
    ANTARESPublicStatusMixin,
    GaiaPublicStatusMixin,
    HorizonsPublicStatusMixin,
    NEDPublicStatusMixin,
    ScoutPublicStatusMixin,
    SIMBADPublicStatusMixin,
)
from goats_tom.service_checks import CheckResult


def test_antares_checks_its_api_url():
    mixin = ANTARESPublicStatusMixin()

    assert mixin.get_credentials(Mock()) == {}
    with patch(
        "goats_tom.api_views.status.mixins.base.check_reachable",
        return_value=CheckResult(True, "ANTARES is available."),
    ) as mock_check:
        assert mixin.check_service({}) == CheckResult(True, "ANTARES is available.")
    # The API's root answers 404: ask the search GOATS itself uses.
    mock_check.assert_called_once_with(
        "https://api.antares.noirlab.edu/v1/loci?page[limit]=1", "ANTARES", {}
    )


def test_antares_reports_no_credentials_state():
    request = Mock(query_params={})
    with patch(
        "goats_tom.api_views.status.mixins.base.check_reachable",
        return_value=CheckResult(False, "ANTARES is not available.", reachable=False),
    ):
        data = ANTARESPublicStatusMixin().get(request).data

    assert data["status"] == "down"
    assert data["credentials"] is None


def test_antares_is_listed_as_public():
    if "antares" in status_mixins:  # Another test may clear the registry.
        assert status_mixins["antares"]["group"] == "public"


@pytest.mark.parametrize(
    ("mixin_cls", "url"),
    [
        (ALeRCEPublicStatusMixin, "https://api.alerce.online/ztf/v1"),
        (GaiaPublicStatusMixin, "http://gsaweb.ast.cam.ac.uk/alerts/alertsindex"),
        (HorizonsPublicStatusMixin, "https://ssd.jpl.nasa.gov/api/horizons.api"),
        (ScoutPublicStatusMixin, "https://ssd-api.jpl.nasa.gov/scout.api"),
        (NEDPublicStatusMixin, "https://ned.ipac.caltech.edu/"),
        (SIMBADPublicStatusMixin, "https://simbad.cds.unistra.fr/simbad/"),
    ],
)
def test_public_services_check_what_goats_calls(mixin_cls, url):
    """Each row checks the endpoint the integration itself uses."""
    mixin = mixin_cls()

    with patch(
        "goats_tom.api_views.status.mixins.base.check_reachable",
        return_value=CheckResult(True, "up"),
    ) as mock_check:
        assert mixin.check_service({}).ok

    mock_check.assert_called_once_with(url, mixin_cls.service_name, {})
    assert mixin_cls.uses_credentials is False
