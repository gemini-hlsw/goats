import pytest
from django.template import Context, Template
from django.test import RequestFactory

from goats_tom.templatetags.sorting import sortable_header

TEMPLATE = Template(
    '{% load sorting %}<table><tr>{% sortable_header "created" "Created (UTC)" %}</tr></table>'
)


def render(query_string):
    request = RequestFactory().get(f"/targets/{query_string}")
    return TEMPLATE.render(Context({"request": request}))


def test_renders_label_and_link():
    rendered = render("")
    assert "Created (UTC)" in rendered
    assert 'href="?order=-created"' in rendered


@pytest.mark.parametrize(
    ("query_string", "expected"),
    [
        # No ordering yet: first click sorts newest first.
        ("", "?order=-created"),
        ("?order=-created", "?order=created"),
        ("?order=created", "?order=-created"),
        # An ordering on another column is replaced, not toggled.
        ("?order=name", "?order=-created"),
    ],
)
def test_toggles_direction(query_string, expected):
    assert f'href="{expected}"' in render(query_string)


def test_keeps_other_filters_and_drops_page():
    rendered = render("?type=SIDEREAL&page=3")
    assert "type=SIDEREAL" in rendered
    assert "page=3" not in rendered
    assert "order=-created" in rendered


def test_marks_active_direction():
    assert "fa-arrow-down-wide-short" in render("?order=-created")
    assert "fa-arrow-up-short-wide" in render("?order=created")
    assert "fa-sort" in render("")


@pytest.mark.parametrize("query", ["", "?order=invalid", "?order=--created"])
def test_effective_default_order_controls_first_click(query):
    request = RequestFactory().get(f"/{query}")
    header = sortable_header(
        {"request": request, "current_order": "-created"}, "created", "Created"
    )
    assert header["descending"]
    assert header["url"] == "?order=created"


def test_header_removes_conflicting_ordering_but_keeps_filters():
    request = RequestFactory().get(
        "/?ordering=status&facility=LCO&facility=GEM&page=3"
    )
    header = sortable_header(
        {"request": request, "current_order": "status"}, "created", "Created"
    )
    assert header["url"] == "?facility=LCO&facility=GEM&order=-created"
