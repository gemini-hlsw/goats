import re
import pytest
from django.template import Template, RequestContext
from django.test import RequestFactory

from goats_tom.context_processors.goats_version_processor import (
    goats_version_info_processor,
    get_goats_version,
)

@pytest.fixture(autouse=True)
def clear_goats_version_cache():
    """Ensure get_goats_version cache is cleared before each test."""
    get_goats_version.cache_clear()

def test_goats_version_context_processor():
    """The context processor should inject version_info.current with correct format."""
    ctx = goats_version_info_processor(None)
    version = ctx.get("version_info").get("current")
    assert version, "version_info.current missing from context"
    assert re.fullmatch(r"\d+\.\d+\.\d", version), f"Unexpected version format: {version!r}"

def test_goats_version_auto_injected_in_template():
    """version_info.current should be available to Django templates via context processors."""
    request = RequestFactory().get("/")
    template = Template(" {{ version_info.current }} ")
    rendered = template.render(RequestContext(request, {})).strip()
    assert rendered, "version_info.current is missing in rendered template"
    assert re.fullmatch(r"\d+\.\d+\.\d", rendered), f"Unexpected version in template: {rendered!r}"

def test_goats_version_is_cached():
    """Verify that `get_goats_version()` uses the cache (`@lru_cache`)."""
    info0 = get_goats_version.cache_info()
    _ = get_goats_version()
    info1 = get_goats_version.cache_info()
    _ = get_goats_version()
    info2 = get_goats_version.cache_info()

    assert info1.misses == info0.misses + 1
    assert info2.hits == info1.hits + 1
    assert info2.currsize == 1
