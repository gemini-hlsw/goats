"""What a given user may see, for the models that appear in a choice field.

`goats_tom.scoping` covers the rows an endpoint *returns*; this module covers
the rows the interface *offers*, in dropdowns, checkbox lists and filter
sidebars. The second is easy to miss -- a view can scope its own queryset
perfectly and still name every PI's targets in a `<select>` beside it,
because the list and the dropdown are built from different querysets.

Scoping a widget is never sufficient on its own; views that act on posted ids
re-check regardless. Target permissions are always applied, matching TOM's
target list and detail views.
"""

__all__ = ["visible_targets"]

import logging

from tom_targets.models import Target

logger = logging.getLogger(__name__)


def _resolve_user(user_or_request):
    """Return a user from either a user or a request.

    Notes
    -----
    Both are accepted because `django_filters` hands a callable ``queryset``
    the request, while views have ``self.request.user`` already.
    """
    if user_or_request is None:
        return None
    return getattr(user_or_request, "user", user_or_request)


def visible_targets(user_or_request):
    """Targets the user may view.

    Notes
    -----
    Delegates to `tom_targets.permissions.targets_for_user` so this agrees
    with the target list and detail pages, including TOM's
    superuser-sees-everything behaviour. A missing or unauthenticated user
    yields no targets. This keeps missing authentication from exposing data.
    """
    user = _resolve_user(user_or_request)
    if user is None or not getattr(user, "is_authenticated", False):
        return Target.objects.none()

    from tom_targets.permissions import targets_for_user  # noqa: PLC0415

    return targets_for_user(user, Target.objects.all(), "view_target")
