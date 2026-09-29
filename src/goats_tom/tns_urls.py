"""GOATS' replacement for `tom_tns.urls`.

Keeps `app_name = "tom_tns"` and the upstream route names unchanged, because
`tom_tns`'s own form partials hard-code them -- ``tns_report_form`` posts to
``tom_tns:submit-report``. Renaming the namespace would break templates GOATS
does not override, so only the views behind the URLs change and anything
linking to ``tom_tns:report-tns`` quietly gets the GOATS versions.
"""

__all__ = ["app_name", "urlpatterns"]

from django.urls import path
from tom_tns.forms import TNSClassifyForm, TNSReportForm

from goats_tom.views import (
    GOATSTNSFormView,
    GOATSTNSSubmitView,
    tns_choose_posting_option,
)

app_name = "tom_tns"

urlpatterns = [
    path("<int:pk>/", GOATSTNSFormView.as_view(), name="report-tns"),
    path(
        "<int:pk>/report",
        GOATSTNSSubmitView.as_view(form_class=TNSReportForm),
        name="submit-report",
    ),
    path(
        "<int:pk>/classify",
        GOATSTNSSubmitView.as_view(form_class=TNSClassifyForm),
        name="submit-classify",
    ),
    path(
        "<int:pk>/posting-option/",
        tns_choose_posting_option,
        name="choose-posting-option",
    ),
]
