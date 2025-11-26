import re
from unittest.mock import MagicMock

import pytest
from django.core.cache import caches
from django.template import RequestContext, Template
from django.test import RequestFactory

from goats_tom.context_processors.goats_version_processor import (
    get_goats_version,
    goats_version_info_processor,
)


class TestGoatsVersionProcessor:
    """Tests for the `goats_version_info_processor` context processor."""
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the LRU cache before each test."""
        get_goats_version.cache_clear()

    def test_returns_expected_keys(self):
        """Test that the context processor returns the expected keys."""
        ctx = goats_version_info_processor(None)
        info = ctx["version_info"]
        assert set(info.keys()) == {"current", "latest", "is_outdated", "doc_url"}

    def test_injects_into_template(self):
        """Test that version_info is accessible in a Django template."""
        request = RequestFactory().get("/")
        template = Template("{{ version_info.current }}")
        rendered = template.render(RequestContext(request, {})).strip()
        assert rendered, "version_info.current is missing in rendered template"
        assert re.fullmatch(r"\d+\.\d+\.\d", rendered), f"Unexpected format: {rendered}"

    def test_uses_lru_cache(self):
        """Test that get_goats_version uses LRU caching."""
        info0 = get_goats_version.cache_info()
        _ = get_goats_version()
        info1 = get_goats_version.cache_info()
        _ = get_goats_version()
        info2 = get_goats_version.cache_info()

        assert info1.misses == info0.misses + 1
        assert info2.hits == info1.hits + 1
        assert info2.currsize == 1

    def test_doc_url_falls_back_to_latest_if_version_is_unknown(self, monkeypatch):
        """Test that doc_url uses /latest/ if current version is 'unknown'."""
        monkeypatch.setattr(
            "goats_tom.context_processors.goats_version_processor.get_goats_version",
            lambda: "unknown",
        )
        ctx = goats_version_info_processor(None)
        assert ctx["version_info"]["doc_url"].endswith("/latest/index.html")

    def test_doc_url_uses_current_if_valid(self):
        """Test that doc_url uses the current version if it is valid."""
        caches["redis"].set("version_info", {
            "current": "25.10.0",
            "latest": "25.10.1",
            "is_outdated": True,
        })
        ctx = goats_version_info_processor(None)
        assert "25.10.0" in ctx["version_info"]["doc_url"]

    @pytest.mark.parametrize(
        "cached_data,expected_current,expected_url_fragment",
        [
            ({"current": "25.9.0"}, "25.9.0", "25.9.0"),
            ({"current": ""}, get_goats_version(), get_goats_version()),
            ({"current": None}, get_goats_version(), get_goats_version()),
            ({}, get_goats_version(), get_goats_version()),
        ],
    )
    def test_fallback_logic_for_current(self, monkeypatch, cached_data, expected_current, expected_url_fragment):
        """Test various fallback scenarios for the 'current' version."""
        # Clear any previous Redis data
        caches["redis"].set("version_info", cached_data)
        ctx = goats_version_info_processor(None)
        current = ctx["version_info"]["current"]
        assert current == expected_current
        assert expected_url_fragment in ctx["version_info"]["doc_url"]

    def test_handles_package_not_found(self, monkeypatch):
        """Test that get_goats_version returns 'unknown' if package is not found."""
        from importlib.metadata import PackageNotFoundError

        monkeypatch.setattr(
            "goats_tom.context_processors.goats_version_processor.version",
            lambda _: (_ for _ in ()).throw(PackageNotFoundError("not found")),
        )
        get_goats_version.cache_clear()
        assert get_goats_version() == "unknown"


    def test_handles_redis_failure_gracefully(self, monkeypatch):
        """If Redis is down, the processor should log and fallback without crashing."""
        mock_cache = MagicMock()
        mock_cache.get.side_effect = Exception("Redis is down")

        # Patch the entire cache backend lookup to return the failing mock
        monkeypatch.setattr("django.core.cache.caches.__getitem__", lambda self, key: mock_cache)

        ctx = goats_version_info_processor(None)
        info = ctx["version_info"]

        assert "doc_url" in info
        assert isinstance(info["current"], str)
