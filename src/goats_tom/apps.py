import logging

from django.apps import AppConfig

from goats_tom.middleware.tns import current_tns_creds

logger = logging.getLogger(__name__)


class GOATSTomConfig(AppConfig):
    name = "goats_tom"

    def ready(self):
        # Imported for its side effect of connecting the receivers. Inside
        # `ready()` rather than at module level, since it imports models.
        from goats_tom import signals  # noqa: F401, PLC0415
        from django.conf import settings  # noqa: PLC0415
        from dramatiq import get_broker  # noqa: PLC0415
        from dramatiq_abort import Abortable, backends  # noqa: PLC0415

        broker = get_broker()

        if not any(isinstance(m, Abortable) for m in broker.middleware):
            abort_backend = backends.RedisBackend.from_url(settings.DRAMATIQ_REDIS_URL)
            broker.add_middleware(Abortable(backend=abort_backend))

        # Monkey-patch tom-tns so it prefers per-request creds over global ones.
        # We keep a reference to the original helper so we can delegate to it when
        # the credentials have not been set for the context or other uncaught issues
        # arise.
        from tom_tns import tns_api  # noqa: PLC0415

        original_get_tns_credentials = tns_api.get_tns_credentials
        original_group_names = tns_api.group_names
        original_default_authors = tns_api.default_authors

        def patched_get_tns_credentials():
            creds = current_tns_creds.get()
            if creds is not None:
                return creds
            return original_get_tns_credentials()

        def patched_group_names():
            creds = current_tns_creds.get()
            if creds is not None:
                return creds.get("group_names", [])
            return original_group_names()

        def patched_default_authors():
            """Prefer the selected group's recommended co-authors.

            `tom_tns.templatetags.tns_extras` already calls
            `default_authors()` to seed the Reporter and Classifier fields,
            so patching it here is what makes a group's recommended author
            list appear pre-filled on the form -- no change to the upstream
            forms or templates is needed.

            An empty string falls through to the original helper rather
            than being returned. `tom_tns` treats a falsy result as "no
            default" and keeps its own initial value (the submitting user's
            name), which is the right behaviour for a group whose owner has
            not set an author list; returning "" from here would instead
            hand it an empty author field to submit.
            """
            creds = current_tns_creds.get()
            if creds is not None:
                authors = creds.get("recommended_authors") or ""
                if authors.strip():
                    return authors.strip()
            return original_default_authors()

        tns_api.get_tns_credentials = patched_get_tns_credentials
        tns_api.group_names = patched_group_names
        tns_api.default_authors = patched_default_authors

        # `tom_tns.forms` does `from tom_tns.tns_api import group_names`,
        # which binds the *original* function into its own namespace at
        # import time. Rebinding `tns_api.group_names` above therefore does
        # not reach it, and `TNSReportForm.__init__` -- which is what
        # builds the "Reporting group" dropdown -- would keep reading the
        # settings-based list and ignore the per-request credentials
        # entirely. That matters more with sharing than without: the
        # dropdown is the only thing stopping a member who was granted one
        # group from selecting a different one belonging to the same owner.
        #
        # `tom_tns.templatetags.tns_extras` binds `default_authors` the same
        # way, but is deliberately *not* imported here: it calls
        # `get_tns_values()` four times at module scope, so importing it
        # during `ready()` would put four network requests on the critical
        # path of every process start, including migrations and management
        # commands. `goats_tom.templatetags.goats_tns_extras` wraps those
        # tags at render time instead, where the call is already happening.
        from tom_tns import forms as tns_forms  # noqa: PLC0415

        tns_forms.group_names = patched_group_names
