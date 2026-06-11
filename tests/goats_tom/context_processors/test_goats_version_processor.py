import re
import pytest
from unittest.mock import patch, MagicMock

from django.template import Template, RequestContext
from django.test import RequestFactory
from django.core.cache import caches

from goats_tom.context_processors.goats_version_processor import (
    goats_version_info_processor,
    get_goats_version,
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
        assert re.fullmatch(
            r"\d+\.\d+\.\d+(?:(?:a|b|rc|dev)\d+)?", rendered
        ), f"Unexpected format: {rendered}"

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

    def test_doc_url_always_uses_latest(self):
        """Test that doc_url always points to /latest/ regardless of current version."""
        ctx = goats_version_info_processor(None)
        assert (
            ctx["version_info"]["doc_url"]
            == "https://goats.readthedocs.io/en/latest/index.html"
        )

    @pytest.mark.parametrize(
        "cached_data,expected_current",
        [
            ({"current": "25.9.0"}, "25.9.0"),
            ({"current": ""}, get_goats_version()),
            ({"current": None}, get_goats_version()),
            ({}, get_goats_version()),
        ],
    )
    def test_fallback_logic_for_current(
        self, monkeypatch, cached_data, expected_current
    ):
        """Test various fallback scenarios for the 'current' version."""
        caches["redis"].set("version_info", cached_data)
        ctx = goats_version_info_processor(None)
        current = ctx["version_info"]["current"]
        assert current == expected_current
        assert (
            ctx["version_info"]["doc_url"]
            == "https://goats.readthedocs.io/en/latest/index.html"
        )

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
        monkeypatch.setattr(
            "django.core.cache.caches.__getitem__", lambda self, key: mock_cache
        )

        ctx = goats_version_info_processor(None)
        info = ctx["version_info"]

        assert "doc_url" in info
        assert isinstance(info["current"], str)
