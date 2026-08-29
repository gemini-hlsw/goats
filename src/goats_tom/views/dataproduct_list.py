"""Data product list view whose "Data Groups" sidebar is scoped to the user.

`tom_dataproducts.views.DataProductListView` scopes its main queryset
correctly and then, in the very next method, does not::

    def get_queryset(self):
        ...
        return get_objects_for_user(self.request.user,
                                    'tom_dataproducts.view_dataproduct')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['product_groups'] = DataProductGroup.objects.all()
        return context

So the table lists only the viewer's own files while the sidebar beside it
names every PI's selections, with a working link to each. The group detail
page behind that link is scoped in GOATS, so following it gives a 403 rather
than the contents -- but the name, and the count of files in it, are on
screen either way.

This is the fourth surface of the same bug: a view that scopes what it
*returns* and hands the template an unscoped queryset for what it *offers*.
The others were the observation list's filter form, the target list's
grouping select, and the add-to-group form on the observation detail page.
`tests.goats_tom.test_context_scoping` now scans for the pattern directly
rather than relying on anyone remembering to look.
"""

__all__ = ["GOATSDataProductListView"]

from tom_dataproducts.views import DataProductListView

from goats_tom.visibility import visible_data_product_groups


class GOATSDataProductListView(DataProductListView):
    """Data product list whose group sidebar shows only the user's own."""

    def get_context_data(self, *args, **kwargs):
        """Replace the unscoped sidebar group list with the user's own.

        Notes
        -----
        Scoped to view rather than change: this sidebar is navigation, and
        a selection the user may read is one they may reasonably click
        through to. That is a weaker requirement than the add-to-group
        destination dropdown, which asks for change because adding a file
        modifies the selection.
        """
        context = super().get_context_data(*args, **kwargs)
        context["product_groups"] = visible_data_product_groups(self.request.user)
        return context
