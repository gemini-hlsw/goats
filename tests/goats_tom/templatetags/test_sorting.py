import pytest
from django.template import Context, Template
from django.test import RequestFactory

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
