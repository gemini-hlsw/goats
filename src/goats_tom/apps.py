import logging
from urllib.parse import urljoin

from django.apps import AppConfig

from goats_tom.middleware.tns import current_tns_creds

logger = logging.getLogger(__name__)


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
        from tom_observations.facilities.ocs import (  # noqa: PLC0415
            OCSBaseForm,
            make_request,
        )
        from tom_tns import tns_api  # noqa: PLC0415

        original_get_tns_credentials = tns_api.get_tns_credentials
        original_group_names = tns_api.group_names
        original_proposal_choices = OCSBaseForm.proposal_choices

        def debug_proposal_choices(self):
            settings = self.facility_settings

            logger.warning(
                "form=%s settings=%s user=%s token_present=%s",
                self.__class__.__name__,
                settings.__class__.__name__,
                getattr(settings, "_user", None),
                bool(settings.get_setting("api_key")),
            )

            url = urljoin(settings.get_setting("portal_url"), "/api/profile/")
            headers = {"Authorization": f"Token {settings.get_setting('api_key')}"}

            logger.warning(
                "GET %s headers=%s",
                url,
                {
                    k: ("<redacted>" if k.lower() == "authorization" else v)
                    for k, v in headers.items()
                },
            )

            try:
                response = make_request("GET", url, headers=headers)
            except RuntimeError as exc:
                logger.error("ImproperCredentialsException: %s", exc)
                return original_proposal_choices(self)

            data = response.json()

            logger.warning(
                "raw response keys=%s",
                list(data.keys()),
            )

            proposals = data.get("proposals", [])
            logger.warning(
                "%d proposals returned",
                len(proposals),
            )

            for p in proposals:
                logger.warning(
                    "proposal id=%s title=%r current=%s raw=%s",
                    p.get("id"),
                    p.get("title"),
                    p.get("current"),
                    p,
                )

            # DO NOT change behavior yet — call original logic
            return original_proposal_choices(self)

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
        OCSBaseForm.proposal_choices = debug_proposal_choices
