__all__ = ["DateOrderingMixin"]

from typing import Any

from django.db.models import F, QuerySet
from django.db.models.expressions import OrderBy


class DateOrderingMixin:
    """Add ``?order=`` support to a list view, restricted to date columns.

    Attributes
    ----------
    orderable_fields : tuple of str
        Model fields the view accepts in ``?order=``. Anything else falls back
        to ``default_ordering``.
    default_ordering : str
        Ordering applied when ``?order=`` is missing or not allowed.
    """

    orderable_fields: tuple[str, ...] = ("created",)
    default_ordering: str = "-created"

    def get_ordering(self) -> list[OrderBy]:
        """Return the ordering requested by ``?order=``, or the default."""
        requested = self.request.GET.get("order", "")
        if requested.lstrip("-") not in self.orderable_fields:
            requested = self.default_ordering
        field = F(requested.lstrip("-"))
        # Nullable dates (e.g. a query that never ran) belong at the bottom
        # whichever direction is asked for.
        if requested.startswith("-"):
            return [field.desc(nulls_last=True)]
        return [field.asc(nulls_last=True)]

    def get_queryset(self, *args: Any, **kwargs: Any) -> QuerySet:
        """Return the parent queryset with the requested ordering applied."""
        # Applied here rather than left to ``MultipleObjectMixin``: the TOM list
        # views build their querysets directly, bypassing ``get_ordering()``.
        return super().get_queryset(*args, **kwargs).order_by(*self.get_ordering())
