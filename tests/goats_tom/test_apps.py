"""Tests for what the GOATS app sets up when Django starts."""

import plotly.graph_objects as go
import plotly.io as pio

GRID = "#C8D4E3"


def test_plots_use_the_light_theme() -> None:
    """Plots are drawn light; the dark theme inverts them in CSS."""
    assert pio.templates.default == "plotly_white"


def test_sky_maps_have_a_visible_grid() -> None:
    """TOM's distribution maps keep plotly's near-white grid unless GOATS darkens it."""
    geo = go.Figure(layout={"geo": {"projection": {"type": "mollweide"}}}).layout.template.layout.geo

    assert geo.lonaxis.gridcolor == GRID
    assert geo.lataxis.gridcolor == GRID
    assert geo.showframe is True
    assert geo.framecolor == GRID
