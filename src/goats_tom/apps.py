from django.apps import AppConfig

from goats_tom.middleware.tns import current_tns_creds


class GOATSTomConfig(AppConfig):
    name = "goats_tom"

    def ready(self):
        from django.conf import settings  # noqa: PLC0415
        from dramatiq import get_broker  # noqa: PLC0415
        from dramatiq_abort import Abortable, backends  # noqa: PLC0415

        event_backend = backends.RedisBackend.from_url(settings.DRAMATIQ_REDIS_URL)
        abortable = Abortable(backend=event_backend)
        get_broker().add_middleware(abortable)

        # Monkey-patch tom-tns so it prefers per-request creds over global ones.
        # We keep a reference to the original helper so we can delegate to it when
        # the credentials have not been set for the context or other uncaught issues
        # arise.
        from tom_tns import tns_api  # noqa: PLC0415

        original_get_tns_credentials = tns_api.get_tns_credentials
        original_group_names = tns_api.group_names

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

        tns_api.get_tns_credentials = patched_get_tns_credentials
        tns_api.group_names = patched_group_names
