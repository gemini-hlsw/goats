"""GOATS' own TNS report page and submit endpoints.

`tom_tns` assumes one user with one set of credentials configured in
settings, so its `TNSFormView` has nothing to choose between and its
`TNSSubmitView` has nobody to attribute a submission to. Both are
subclassed here rather than replaced: the report generation, the TNS API
calls and the IAU-name handling are upstream's and stay that way.

What GOATS adds is the three things sharing needs -- a picker for which
credentials to post with, a check that the user may actually see the target,
and a record of what went out under whose bot.
"""

__all__ = ["GOATSTNSFormView", "GOATSTNSSubmitView"]

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from tom_targets.models import Target
from tom_tns.views import TNSFormView, TNSSubmitView

from goats_tom.forms import TNSJoinRequestForm
from goats_tom.middleware.tns import SESSION_KEY, current_tns_creds
from goats_tom.models import TNSSubmissionRecord
from goats_tom.tns_membership import (
    posting_options,
    requestable_groups,
    resolve_posting_option,
)
from goats_tom.visibility import visible_targets

logger = logging.getLogger(__name__)


def _visible_target_or_403(user, pk: int) -> Target:
    """Return the target if `user` may see it, otherwise refuse.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The acting user.
    pk : int
        Target primary key.

    Returns
    -------
    `tom_targets.models.Target`

    Raises
    ------
    `django.core.exceptions.PermissionDenied`
        If the user has no view permission on the target.

    Notes
    -----
    `tom_tns.views.TNSFormView` mixes in guardian's `PermissionListMixin`,
    but that only filters a *list* queryset -- the view is a `TemplateView`
    that fetches the target itself with `Target.objects.get(pk=...)`, so
    the mixin never runs and any signed-in user can open the TNS page for
    any target by primary key.

    That was survivable when everyone posted as themselves with their own
    credentials. It is not once a bot is shared: the pairing of "any target"
    with "somebody else's credentials" is exactly the combination an owner
    is trusting GOATS not to allow.

    Delegates to `goats_tom.visibility.visible_targets` rather than
    querying guardian directly, so this agrees with the target list and
    detail pages. That helper also honours `TARGET_PERMISSIONS_ONLY` and
    TOM's superuser-sees-everything behaviour; a bespoke permission check
    here would diverge from both, and a TNS page that refuses a target the
    user can plainly open elsewhere reads as a bug rather than a policy.
    """
    target = get_object_or_404(Target, pk=pk)
    if not visible_targets(user).filter(pk=target.pk).exists():
        raise PermissionDenied("You do not have access to this target.")
    return target


class GOATSTNSFormView(LoginRequiredMixin, TNSFormView):
    """The TNS page, with a picker for which credentials to post with.

    Notes
    -----
    Overrides `tns_configured` rather than inheriting it. Upstream computes
    it from `get_tns_credentials()`, imported by name into
    `tom_tns.views` at module load -- so the patch in `goats_tom.apps`
    never reaches it and the answer is read from settings GOATS does not
    populate. The page consequently claimed credentials were not configured
    for users who had them stored. Here it is derived from
    `goats_tom.tns_membership.posting_options`, which is the same source
    the middleware uses to pick the credentials, so the page cannot say one
    thing while the submission does another.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle the page load, honouring a newly-picked option.

        Notes
        -----
        The picker submits with GET rather than POST because choosing which
        bot to post as changes nothing on TNS -- it re-renders the page with
        different forms. Making it a POST would need its own endpoint and a
        redirect for no gain.

        The chosen key is written to the session and never used directly:
        `goats_tom.tns_membership.resolve_posting_option` re-derives it from
        what the user actually holds on every request, so a hand-edited
        value buys nothing.
        """
        chosen = request.GET.get("posting_option")
        if chosen:
            request.session[SESSION_KEY] = chosen
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Build the page context.

        Returns
        -------
        dict
            Upstream's context plus the posting options, the active option,
            the groups the user could request, and a corrected
            `tns_configured`.
        """
        # Enforced before upstream's `get_context_data` fetches the target,
        # so an unauthorised user is refused rather than served a page
        # built from a target they cannot see.
        target = _visible_target_or_403(self.request.user, self.kwargs["pk"])

        context = super().get_context_data(**kwargs)
        user = self.request.user

        options = posting_options(user)
        active = resolve_posting_option(
            user, self.request.session.get(SESSION_KEY)
        )

        # Serialised for the script that keeps the author field in step with
        # "Reporting group". `json.dumps` rather than a template filter so
        # the shape is fixed here; the template renders it inside a
        # `type="application/json"` block, which the browser does not
        # execute, so a group name containing quotes cannot break out.
        context["group_authors_json"] = json.dumps(
            active.group_authors if active is not None else {}
        )
        context["target"] = target
        context["posting_options"] = options
        context["active_option"] = active
        context["tns_configured"] = active is not None
        context["has_own_credentials"] = hasattr(user, "tnslogin")
        # The form, not the raw queryset: a user with nothing to post with
        # can ask for access right here, which is where the need actually
        # arises. `None` when there is nothing they could request, so the
        # template can leave the panel out entirely rather than render an
        # empty dropdown.
        context["join_request_form"] = (
            TNSJoinRequestForm(user=user)
            if requestable_groups(user).exists()
            else None
        )
        return context


class GOATSTNSSubmitView(LoginRequiredMixin, TNSSubmitView):
    """Upstream's submit view, plus a permission check and an audit record.

    Notes
    -----
    `form_valid` is not overridden. It is where upstream builds the report,
    calls TNS, reads back the IAU name and renames the target -- reproducing
    any of that to wrap it would mean owning a copy that has to be kept in
    step with `tom_tns` releases. Instead the outcome is inferred after the
    fact from the messages upstream queued and the target's state, which is
    stable across those releases in a way its internals are not.
    """

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Refuse submissions for targets the user cannot see.

        Notes
        -----
        Checked here rather than in `form_valid` so it applies before the
        form is even bound. Upstream's view has no permission check at all,
        and this endpoint is the one that actually sends to TNS.
        """
        if request.user.is_authenticated:
            _visible_target_or_403(request.user, self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def _kind(self) -> str:
        """Return whether this endpoint reports or classifies.

        Returns
        -------
        str
            `TNSSubmissionRecord.KIND_REPORT` or `KIND_CLASSIFY`.

        Notes
        -----
        Derived from the form class the URL bound, which is how `tom_tns`
        distinguishes the two -- one view class serves both endpoints.
        """
        name = getattr(self.get_form_class(), "__name__", "")
        if "Classify" in name:
            return TNSSubmissionRecord.KIND_CLASSIFY
        return TNSSubmissionRecord.KIND_REPORT

    def _record(self, form, succeeded: bool, error: str = "") -> None:
        """Write the audit row for this attempt.

        Parameters
        ----------
        form : `django.forms.Form`
            The submitted form, valid or not.
        succeeded : bool
            Whether TNS accepted it.
        error : str, optional
            What went wrong.

        Notes
        -----
        Reads the bot from the credential payload the middleware resolved,
        not from the acting user's own login -- the whole point is to record
        *whose* bot was used, which for a shared group is somebody else's.

        Failures to write the record are logged and swallowed. The
        submission has already gone to TNS by this point; raising here would
        show the user an error for something that succeeded, and would not
        unsend it.
        """
        try:
            option = resolve_posting_option(
                self.request.user, self.request.session.get(SESSION_KEY)
            )
            creds = current_tns_creds.get() or {}
            data = getattr(form, "cleaned_data", {}) or {}
            group = self._submitted_group(form, option)

            TNSSubmissionRecord.objects.create(
                submitted_by=self.request.user,
                display_name=self.request.user.get_full_name().strip(),
                username=self.request.user.username,
                owner=option.owner if option else None,
                tns_group=group,
                group_name=group.name if group else "",
                bot_id=creds.get("bot_id", ""),
                target_pk=self.kwargs.get("pk"),
                object_name=str(data.get("object_name", "")),
                kind=self._kind(),
                succeeded=succeeded,
                iau_name=self._iau_name(),
                error=error[:2000],
            )
        except Exception:
            logger.exception(
                "Could not record TNS submission by %s; the submission "
                "itself was unaffected.",
                self.request.user.username,
            )

    def _submitted_group(self, form, option):
        """Which TNS group the report was actually filed under.

        Parameters
        ----------
        form : `django.forms.Form`
            The submitted form.
        option : `goats_tom.tns_membership.PostingOption` or None
            The credentials used.

        Returns
        -------
        `goats_tom.models.TNSGroup` or None
            `None` when no group was chosen, or when the choice does not
            match one of the option's groups.

        Notes
        -----
        The group comes from the form's "Reporting group" field rather than
        from the option, because the option is a *bot* now and a bot may be
        able to file under several groups. Reading it from the credentials
        would record whichever group happened to be first.

        `tom_tns` stores the field's value as the TNS group id, not the
        name, so the selected choice's label is what gets matched. Failing
        to match yields `None` rather than raising -- an audit row missing
        its group is far better than a submission that already reached the
        TNS failing afterwards on bookkeeping.
        """
        if option is None:
            return None
        value = (getattr(form, "cleaned_data", {}) or {}).get("reporting_group")
        if value in (None, ""):
            return None
        field = form.fields.get("reporting_group")
        label = None
        for choice_value, choice_label in getattr(field, "choices", []) or []:
            if str(choice_value) == str(value):
                label = str(choice_label).strip()
                break
        if label is None:
            return None
        for group in option.groups:
            if group.name == label:
                return group
        return None

    def _iau_name(self) -> str:
        """Return the target's current name, as the submission may have set it.

        Returns
        -------
        str
            Empty if the target has gone.

        Notes
        -----
        Upstream renames the target in place when TNS returns an IAU name,
        so reading it back afterwards is how the record captures it without
        reimplementing the submission.
        """
        target = Target.objects.filter(pk=self.kwargs.get("pk")).first()
        return target.name if target is not None else ""

    def form_valid(self, form):
        """Submit through upstream, then record what happened.

        Notes
        -----
        Success is read from the messages upstream queued rather than from
        a return value, because it has none to give -- it redirects either
        way and reports errors by adding a message. That is the only signal
        available without forking `form_valid` itself.

        Reading them is destructive: iterating the storage marks it used,
        so every message would be discarded before the redirect target got
        to render them. They are therefore captured with their levels and
        all re-added, not just the errors -- `tom_tns.tns_api` queues a
        *success* message carrying the IAU name it got back, and dropping
        that would leave a user who submitted correctly with a silent page
        and no confirmation their report landed.
        """
        response = super().form_valid(form)

        captured = [
            (message.level, str(message))
            for message in messages.get_messages(self.request)
        ]
        for level, text in captured:
            messages.add_message(self.request, level, text)

        errors = [
            text for level, text in captured if level >= messages.ERROR
        ]
        self._record(form, succeeded=not errors, error=" ".join(errors))
        return response

    def form_invalid(self, form):
        """Record a submission that never reached TNS."""
        self._record(
            form, succeeded=False, error=f"Form invalid: {form.errors.as_json()}"
        )
        return super().form_invalid(form)


@login_required
@require_POST
def tns_choose_posting_option(request: HttpRequest, pk: int) -> HttpResponse:
    """Store the user's chosen posting option and return to the TNS page.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request; reads `posting_option`.
    pk : int
        Target primary key, so the redirect lands back where it started.

    Returns
    -------
    `HttpResponse`
        Redirect to the target's TNS page.

    Notes
    -----
    Provided alongside the GET form on `GOATSTNSFormView` so the picker can
    be a plain POST where that reads better in a template. Both write the
    same session key and both defer validation to
    `goats_tom.tns_membership.resolve_posting_option`.
    """
    request.session[SESSION_KEY] = request.POST.get("posting_option", "")
    return redirect("tom_tns:report-tns", pk=pk)
