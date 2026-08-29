"""Guards that no dropdown offers rows the viewer has no right to see.

`test_api_scoping` guards what endpoints *return*. This guards what the
interface *offers*: the `<select>` elements, checkbox lists and filter
sidebars built from `ModelChoiceField` and `ModelMultipleChoiceFilter`.

They fail independently, and that is the whole reason this file exists. Every
group leak found so far had the same shape -- the view's own queryset scoped
correctly, the action endpoint re-checking permissions correctly, and a
dropdown beside them built from ``Model.objects.all()``. Fixing the list page
and the action endpoint did not fix the dropdown, twice, because nothing tied
them together.

Two properties are checked:

**Scoped, not global.** A choice field over one of the permission-bearing
models must not resolve to every row for a user who may see none of them.

**Enforcing, not decorative.** For a Django form the queryset is also the
validator, so a hidden field matters as much as a visible one. A test that
only inspected rendered HTML would pass on a hidden `ModelChoiceField` over
``objects.all()``, which is precisely the hole in `DataProductUploadForm`.
"""

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from guardian.shortcuts import assign_perm
from tom_dataproducts.models import DataProduct, DataProductGroup
from tom_observations.models import ObservationGroup, ObservationRecord
from tom_targets.models import Target, TargetList

from goats_tom.filters import GOATSObservationFilter, GOATSTargetFilterSet
from goats_tom.views.observation_record_detail import _scoped_add_product_form
from goats_tom.visibility import (
    changeable_data_product_groups,
    visible_data_product_groups,
    visible_data_products,
    visible_observation_groups,
    visible_observation_records,
    visible_target_lists,
    visible_targets,
)


@pytest.fixture
def two_pis(db):
    """Two PIs, each owning one of every permission-bearing object.

    Notes
    -----
    Deliberately symmetric: every assertion below is "alice sees hers and
    not bob's". A fixture where only one user owns anything would pass
    against a helper that returns everything.
    """
    alice = User.objects.create_user("alice")
    bob = User.objects.create_user("bob")

    owned = {}
    for user in (alice, bob):
        target = Target.objects.create(
            name=f"{user.username}_target", type="SIDEREAL", ra=1.0, dec=1.0
        )
        assign_perm("tom_targets.view_target", user, target)

        record = ObservationRecord.objects.create(
            target=target,
            facility="F",
            parameters={},
            observation_id=f"{user.username}_obs",
        )
        assign_perm("tom_observations.view_observationrecord", user, record)

        product = DataProduct.objects.create(
            target=target, product_id=f"{user.username}_product"
        )
        assign_perm("tom_dataproducts.view_dataproduct", user, product)

        obs_group = ObservationGroup.objects.create(name=f"{user.username}_OG")
        assign_perm("tom_observations.view_observationgroup", user, obs_group)
        assign_perm("tom_observations.change_observationgroup", user, obs_group)

        dp_group = DataProductGroup.objects.create(name=f"{user.username}_DPG")
        assign_perm("tom_dataproducts.view_dataproductgroup", user, dp_group)
        assign_perm("tom_dataproducts.change_dataproductgroup", user, dp_group)

        target_list = TargetList.objects.create(name=f"{user.username}_TL")
        assign_perm("tom_targets.view_targetlist", user, target_list)

        owned[user.username] = {
            "user": user,
            "target": target,
            "record": record,
            "product": product,
            "obs_group": obs_group,
            "dp_group": dp_group,
            "target_list": target_list,
        }
    return owned


HELPERS = [
    (visible_targets, "target"),
    (visible_observation_records, "record"),
    (visible_data_products, "product"),
    (visible_observation_groups, "obs_group"),
    (changeable_data_product_groups, "dp_group"),
    (visible_data_product_groups, "dp_group"),
    (visible_target_lists, "target_list"),
]


@pytest.mark.parametrize(("helper", "key"), HELPERS)
def test_helper_returns_only_the_users_own(two_pis, helper, key):
    """Each visibility helper hides the other PI's object."""
    mine = two_pis["alice"][key]
    theirs = two_pis["bob"][key]
    result = helper(two_pis["alice"]["user"])

    assert mine in result
    assert theirs not in result


@pytest.mark.parametrize(("helper", "key"), HELPERS)
def test_helper_returns_nothing_for_anonymous(two_pis, helper, key):
    """An unauthenticated caller gets an empty queryset, not everything.

    Notes
    -----
    The failure mode being guarded against is a helper that treats a
    missing user as "no filtering required" -- which reads as harmless and
    returns the entire table.
    """
    from django.contrib.auth.models import AnonymousUser

    assert not helper(AnonymousUser()).exists()


def test_observation_filter_scopes_both_choice_fields(two_pis):
    """The observation list's group and target dropdowns are scoped.

    Notes
    -----
    This single form field is rendered twice -- in the filter sidebar and
    in the add/remove bar above the table -- so both surfaces are covered
    by this one assertion.
    """
    request = RequestFactory().get("/observations/list/")
    request.user = two_pis["alice"]["user"]
    filterset = GOATSObservationFilter(
        data={}, queryset=ObservationRecord.objects.all(), request=request
    )

    groups = filterset.form.fields["observationgroup"].queryset
    assert two_pis["alice"]["obs_group"] in groups
    assert two_pis["bob"]["obs_group"] not in groups

    targets = filterset.form.fields["target_id"].queryset
    assert two_pis["bob"]["target"] not in targets


def test_target_filter_scopes_target_group_choices(two_pis):
    """The target list's "Target Group" filter is scoped."""
    request = RequestFactory().get("/targets/")
    request.user = two_pis["alice"]["user"]
    filterset = GOATSTargetFilterSet(
        data={}, queryset=Target.objects.all(), request=request
    )

    lists = filterset.form.fields["targetlist__name"].queryset
    assert two_pis["alice"]["target_list"] in lists
    assert two_pis["bob"]["target_list"] not in lists


def test_add_product_to_group_form_is_scoped(two_pis):
    """The observation detail page's add-to-group form is scoped.

    Notes
    -----
    Checks the form querysets rather than the rendered page, because the
    queryset is what rejects a posted id. A test against the HTML would
    pass while the endpoint still accepted another PI's group.
    """
    form = _scoped_add_product_form(two_pis["alice"]["user"])

    assert two_pis["alice"]["dp_group"] in form.fields["group"].queryset
    assert two_pis["bob"]["dp_group"] not in form.fields["group"].queryset
    assert two_pis["bob"]["product"] not in form.fields["products"].queryset


def test_target_permissions_only_mode_is_unchanged(two_pis, settings):
    """The desktop install still sees everything.

    Notes
    -----
    The hard invariant: with ``TARGET_PERMISSIONS_ONLY`` at its default,
    none of this scoping applies and a single-astronomer install behaves
    exactly as before. A fix that quietly hid a lone user's own selections
    from them would be a regression, not a security improvement.
    """
    settings.TARGET_PERMISSIONS_ONLY = True

    for helper, key in HELPERS:
        result = helper(two_pis["alice"]["user"])
        assert two_pis["bob"][key] in result
