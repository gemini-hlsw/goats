__all__ = ["DateOrderingMixin", "date_ordering", "resolve_date_order"]

from typing import Any

from django.db.models import F, QuerySet
from django.db.models.expressions import OrderBy
from django.http import HttpRequest


def resolve_date_order(
    request: HttpRequest,
    orderable_fields: tuple[str, ...],
    default_ordering: str,
    param: str = "order",
) -> str:
    """Resolve the requested date order, falling back for unsupported values."""
    requested = request.GET.get(param, "")
    allowed = {*orderable_fields, *(f"-{field}" for field in orderable_fields)}
    return requested if requested in allowed else default_ordering


def date_ordering(
    request: HttpRequest,
    orderable_fields: tuple[str, ...],
    default_ordering: str,
    tiebreaker: str = "pk",
) -> list[OrderBy]:
    """Resolve ``?order=`` into an ordering, restricted to `orderable_fields`.

    Parameters
    ----------
    request : `HttpRequest`
        Request carrying the ``order`` query parameter.
    orderable_fields : tuple of str
        Fields accepted in ``?order=``. Anything else falls back to
        `default_ordering`.
    default_ordering : str
        Ordering applied when ``?order=`` is missing or not allowed.
    tiebreaker : str
        Field ordering rows that share a date, sorted ascending the way
        TOMToolkit orders its own lists. ``pk`` always closes the ordering, so
        repeated names still page deterministically.

    Returns
    -------
    list of `OrderBy`
        Ordering suitable for ``QuerySet.order_by``.
    """
    requested = resolve_date_order(request, orderable_fields, default_ordering)
    field = F(requested.removeprefix("-"))
    descending = requested.startswith("-")
    # Nullable dates (e.g. a query that never ran) belong at the bottom
    # whichever direction is asked for.
    ordering = [
        field.desc(nulls_last=True) if descending else field.asc(nulls_last=True)
    ]
    if tiebreaker != "pk":
        ordering.append(F(tiebreaker).asc(nulls_last=True))
    # ``pk`` closes the ordering: names repeat, so it is what keeps paging stable.
    ordering.append(F("pk").desc() if descending else F("pk").asc())
    return ordering


class DateOrderingMixin:
    """Add ``?order=`` support to a list view, restricted to date columns.

    Attributes
    ----------
    orderable_fields : tuple of str
        Model fields the view accepts in ``?order=``. Anything else falls back
        to ``default_ordering``.
    default_ordering : str
        Ordering applied when ``?order=`` is missing or not allowed.
    tiebreaker : str
        Field ordering rows that share a date.
    """

    orderable_fields: tuple[str, ...] = ("created",)
    default_ordering: str = "-created"
    tiebreaker: str = "pk"

    def get_ordering(self) -> list[OrderBy]:
        """Return the ordering requested by ``?order=``, or the default."""
        return date_ordering(
            self.request,
            self.orderable_fields,
            self.default_ordering,
            self.tiebreaker,
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Expose the effective order so headers can show and toggle it."""
        context = super().get_context_data(**kwargs)
        context["current_order"] = resolve_date_order(
            self.request, self.orderable_fields, self.default_ordering
        )
        return context

    def get_queryset(self, *args: Any, **kwargs: Any) -> QuerySet:
        """Return the parent queryset with the requested ordering applied."""
        # Applied here rather than left to ``MultipleObjectMixin``: the TOM list
        # views build their querysets directly, bypassing ``get_ordering()``.
        return super().get_queryset(*args, **kwargs).order_by(*self.get_ordering())
