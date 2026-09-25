__all__ = ["UserListView"]

from django.views.generic import TemplateView
from tom_common.mixins import SuperuserRequiredMixin


class UserListView(SuperuserRequiredMixin, TemplateView):
    """The directory of accounts and groups, which is an administrator's tool.

    Notes
    -----
    Upstream's view is `LoginRequiredMixin` only. A user reaches their own
    credentials from their settings page, so nobody else needs this one.
    """

    template_name = "auth/user_list.html"
