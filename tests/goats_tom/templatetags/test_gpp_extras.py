from unittest.mock import patch

from django.template import Context, Template


def test_explore_url_renders_environment_url():
    with patch(
        "goats_tom.templatetags.gpp_extras.get_explore_url",
        return_value="https://explore-dev.lucuma.xyz",
    ):
        rendered = Template("{% load gpp_extras %}{% explore_url %}/").render(
            Context()
        )

    assert rendered == "https://explore-dev.lucuma.xyz/"
