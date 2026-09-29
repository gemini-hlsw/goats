"""GOATS' own TNS report page and submit endpoints.

`tom_tns` assumes one user with one set of credentials in settings, so its
`TNSFormView` has nothing to choose between and its `TNSSubmitView` has
nobody to attribute a submission to. Both are subclassed rather than
replaced -- the report generation, the TNS API calls and the IAU-name
handling stay upstream's. GOATS adds the three things sharing needs: a picker
for which credentials to post with, a check that the user may see the target,
and a record of what went out under whose bot.
"""

__all__ = ["GOATSTNSFormView", "GOATSTNSSubmitView"]

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
        The target, once the user is known to be allowed to see it.

    Raises
    ------
    `django.core.exceptions.PermissionDenied`
        If the user has no view permission on the target.

    Notes
    -----
    `tom_tns.views.TNSFormView` mixes in guardian's `PermissionListMixin`,
    but that filters only a *list* queryset and the view fetches the target
    itself, so any signed-in user can open the TNS page for any target by
    primary key. Survivable while everyone posted as themselves; not once a
    bot is shared.

    Delegates to `goats_tom.visibility.visible_targets` so this agrees with
    the target list and detail pages, including TOM's superuser
    behaviour. Private targets require permission at every setting.
    """
    target = get_object_or_404(Target, pk=pk)
    if not visible_targets(user).filter(pk=target.pk).exists():
        raise PermissionDenied("You do not have access to this target.")
    return target


class GOATSTNSFormView(LoginRequiredMixin, TNSFormView):
    """The TNS page, with a picker for which credentials to post with.

    Notes
    -----
    Overrides `tns_configured`, which upstream computes from
    `get_tns_credentials()` imported by name at module load -- so the patch in
    `goats_tom.apps` never reaches it and the page claimed credentials were
    not configured for users who had them. Derived here from
    `goats_tom.tns_membership.posting_options`, the same source the
    middleware uses, so the page cannot disagree with the submission.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle the page load, honouring a newly-picked option.

        Notes
        -----
        The picker submits with GET, since choosing a bot changes nothing on
        TNS. The chosen key is written to the session and never used
        directly -- `resolve_posting_option` re-derives it from what the user
        actually holds, so a hand-edited value buys nothing.
        """
        chosen = request.GET.get("posting_option")
        if chosen:
            request.session[SESSION_KEY] = chosen
            # Re-enter the middleware with the updated choice before rendering.
            return redirect("tom_tns:report-tns", pk=self.kwargs["pk"])
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
        # Before upstream fetches the target, so an unauthorised user is
        # refused rather than served a page built from it.
        target = _visible_target_or_403(self.request.user, self.kwargs["pk"])

        context = super().get_context_data(**kwargs)
        user = self.request.user

        options = posting_options(user)
        active = resolve_posting_option(user, self.request.session.get(SESSION_KEY))

        # The mapping itself, not a JSON string: `json_script` escapes it,
        # and a pre-dumped string came out double-escaped and unparseable.
        context["group_authors"] = active.group_authors if active is not None else {}
        context["target"] = target
        context["posting_options"] = options
        context["active_option"] = active
        context["tns_configured"] = active is not None
        context["has_own_credentials"] = hasattr(user, "tnslogin")
        # `None` when there is nothing to request, so the template leaves the
        # panel out rather than rendering an empty dropdown.
        context["join_request_form"] = (
            TNSJoinRequestForm(user=user) if requestable_groups(user).exists() else None
        )
        return context


class GOATSTNSSubmitView(LoginRequiredMixin, TNSSubmitView):
    """Upstream's submit view, plus a permission check and an audit record.

    Notes
    -----
    Upstream's `form_valid` is where the report is built, TNS is called and
    the target renamed, so it is wrapped rather than reproduced. The outcome
    is inferred afterwards from the messages it queued and the target's
    state, which stay stable across `tom_tns` releases in a way its
    internals do not.
    """

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Refuse submissions without a visible target and credentials to use.

        Notes
        -----
        Both checks run before the form is bound. Upstream has none, and this
        endpoint is the one that actually sends to TNS.

        The credential check asks `resolve_posting_option`, the same call that
        decides what the page offers, so the endpoint cannot refuse what the
        picker showed or accept what it did not. Without it a user with no
        credentials falls through to `tom_tns`, which reads the instance-wide
        bot out of ``settings.BROKERS`` -- so anyone signed in could post
        under it, and the audit row would name no owner.
        """
        if request.user.is_authenticated:
            _visible_target_or_403(request.user, self.kwargs["pk"])
            session = getattr(request, "session", None)
            key = session.get(SESSION_KEY) if session is not None else None
            if resolve_posting_option(request.user, key) is None:
                raise PermissionDenied("You have no TNS credentials to submit with.")
        return super().dispatch(request, *args, **kwargs)

    def _kind(self) -> str:
        """Return whether this endpoint reports or classifies.

        Returns
        -------
        str
            `TNSSubmissionRecord.KIND_REPORT` or `KIND_CLASSIFY`.

        Notes
        -----
        Derived from the form class the URL bound, since one view class
        serves both endpoints.
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
        Reads the bot from the payload the middleware resolved, not the
        acting user's own login -- the point is to record *whose* bot was
        used. Write failures are logged and swallowed: the submission has
        already reached TNS, and raising would not unsend it.
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
        From the form's field rather than the option, since one bot may file
        under several groups and the option would give whichever came first.
        `tom_tns` stores the value as the TNS group id, so the choice's label
        is matched. A failed match yields `None` rather than raising: an
        audit row missing its group beats failing a submission that landed.
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
        Upstream renames the target in place when TNS returns an IAU name, so
        reading it back is how the record captures it.
        """
        target = Target.objects.filter(pk=self.kwargs.get("pk")).first()
        return target.name if target is not None else ""

    def form_valid(self, form):
        """Submit through upstream, then record what happened.

        Notes
        -----
        Success is read from the messages upstream queued, since it redirects
        either way and reports errors only that way.

        Reading them is destructive -- iterating the storage marks it used --
        so all of them are captured with their levels and re-added, not just
        the errors: upstream queues a *success* message carrying the IAU name,
        and dropping it would leave a correct submission unconfirmed.
        """
        response = super().form_valid(form)

        captured = [
            (message.level, str(message))
            for message in messages.get_messages(self.request)
        ]
        for level, text in captured:
            messages.add_message(self.request, level, text)

        errors = [text for level, text in captured if level >= messages.ERROR]
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
    Alongside the GET form on `GOATSTNSFormView`, for templates where a plain
    POST reads better. Both write the same session key and defer validation
    to `goats_tom.tns_membership.resolve_posting_option`.
    """
    request.session[SESSION_KEY] = request.POST.get("posting_option", "")
    return redirect("tom_tns:report-tns", pk=pk)
