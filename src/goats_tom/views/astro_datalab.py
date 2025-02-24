"""Module that displays the template for Astro Data Lab."""

__all__ = ["AstroDatalabView"]

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class AstroDatalabView(LoginRequiredMixin, TemplateView):
    """View that displays the Astro Data Lab integration page."""

    template_name = "astro_datalab.html"

    def get_context_data(self, **kwargs):
        """Add user context for generating the correct Astro Data Lab login link."""
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context
