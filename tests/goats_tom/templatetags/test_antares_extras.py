import json
from urllib.parse import unquote, urlparse, parse_qs

import pytest

from goats_tom.templatetags.antares_extras import antares_url

BASE = "https://antares.noirlab.edu/loci"


def _extract_query_payload(url: str) -> dict:
    """
    Helper: parse `?query=<urlencoded json>` and return the decoded dict.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert "query" in qs, f"Missing 'query' param in url: {url}"
    raw = qs["query"][0]
    payload_json = unquote(raw)
    return json.loads(payload_json)


def test_antares_url_direct_object_when_name_contains_ANT():
    url = antares_url("ANT123", None, None)
    assert url == f"{BASE}/ANT123"


def test_antares_url_direct_object_quotes_name():
    # Space should be URL-encoded
    url = antares_url("ANT 123", None, None)
    assert url == f"{BASE}/ANT%20123"


def test_antares_url_returns_base_when_no_name_and_missing_coords():
    url = antares_url(None, None, None)
    assert url == BASE


def test_antares_url_returns_base_when_missing_ra_or_dec():
    assert antares_url("something-else", None, "00:00:00") == BASE
    assert antares_url("something-else", "00:00:00", None) == BASE


def test_antares_url_cone_search_builds_expected_query_payload():
    ra_hms = "12:34:56.7"
    dec_dms = "-01:02:03.4"

    url = antares_url("not-ant-name", ra_hms, dec_dms)
    assert url.startswith(f"{BASE}?query=")

    payload = _extract_query_payload(url)

    center = f"{ra_hms} {dec_dms}"

    assert payload["sortBy"] == "properties.newest_alert_observation_time"
    assert payload["sortDesc"] is True
    assert payload["perPage"] == 25

    assert "filters" in payload
    assert isinstance(payload["filters"], list)
    assert len(payload["filters"]) == 1

    f0 = payload["filters"][0]
    assert f0["type"] == "sky_distance"
    assert f0["text"] == f'Cone Search: {center}, 1"'
    assert f0["field"]["distance"] == "0.0002777777777777778 degree"
    assert f0["field"]["htm16"]["center"] == center
