import logging

from django.apps import AppConfig

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

        from urllib.parse import urljoin  # noqa: PLC0415

        from django.core.cache import cache  # noqa: PLC0415
        from tom_common.exceptions import ImproperCredentialsException  # noqa: PLC0415
        from tom_observations.facilities.ocs import (  # noqa: PLC0415
            OCSBaseForm,
            make_request,
        )
        from tom_tns import tns_api  # noqa: PLC0415

        from goats_tom.middleware.tns import current_tns_creds  # noqa: PLC0415

        # Monkey-patch tom-tns so it prefers per-request creds over global ones.
        # We keep a reference to the original helper so we can delegate to it when
        # the credentials have not been set for the context or other uncaught issues
        # arise.
        # Monkey-patch facility proposals fetching to cache results and use
        # per-user API keys.
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

        def patched__get_instruments(self):
            # Taken from OCSBaseForm._get_instruments, modified to use per-user cache.
            if hasattr(self, "_cached_instruments"):
                return self._cached_instruments
            # logger.debug("Using patched instruments with per-user API keys")

            user = getattr(self.facility_settings, "_user", None)
            # Validate user presence.
            if not user or not user.is_authenticated:
                cached_instruments = self.facility_settings.default_instrument_config
                # Do not cache default instruments if no user is present.
                return cached_instruments

            # Derive cache key for the user.
            cache_key = (
                f"{self.facility_settings.facility_name}_user_{user.pk}_instruments"
            )
            cached_instruments = cache.get(cache_key)
            logger.debug(
                "Cached hit %s for instruments with key %r",
                bool(cached_instruments),
                cache_key,
            )

            if not cached_instruments:
                try:
                    response = make_request(
                        "GET",
                        urljoin(
                            self.facility_settings.get_setting("portal_url"),
                            "/api/instruments/",
                        ),
                        headers={
                            "Authorization": "Token {0}".format(
                                self.facility_settings.get_setting("api_key")
                            )
                        },
                    )
                    cached_instruments = {k: v for k, v in response.json().items()}
                except ImproperCredentialsException:
                    cached_instruments = (
                        self.facility_settings.default_instrument_config
                    )
            cache.set(
                cache_key,
                cached_instruments,
                60,
            )
            logger.debug("Returning instruments")
            self._cached_instruments = cached_instruments
            return cached_instruments

        def patched_proposal_choices(self):
            # Taken from OCSBaseForm.proposal_choices, modified to use per-user cache.
            if hasattr(self, "_cached_proposals"):
                return self._cached_proposals
            # logger.debug("Using patched proposal choices with per-user API keys")
            no_proposals_found = [(0, "No proposals found")]
            user = getattr(self.facility_settings, "_user", None)
            # Validate user presence.
            if not user or not user.is_authenticated:
                return no_proposals_found

            # Derive cache key for the user.
            cache_key = (
                f"{self.facility_settings.facility_name}_user_{user.pk}_proposals"
            )
            cached_proposals = cache.get(cache_key)
            logger.debug(
                "Cached hit %s for proposals with key %r",
                bool(cached_proposals),
                cache_key,
            )

            if not cached_proposals:
                try:
                    response = make_request(
                        "GET",
                        urljoin(
                            self.facility_settings.get_setting("portal_url"),
                            "/api/profile/",
                        ),
                        headers={
                            "Authorization": "Token {0}".format(
                                self.facility_settings.get_setting("api_key")
                            )
                        },
                    )
                except ImproperCredentialsException:
                    return no_proposals_found
                cached_proposals = []
                for p in response.json()["proposals"]:
                    if p["current"]:
                        cached_proposals.append(
                            (p["id"], "{} ({})".format(p["title"], p["id"]))
                        )
                cache.set(
                    cache_key,
                    cached_proposals,
                    60,
                )
            logger.debug("Returning proposals: %r", cached_proposals)
            self._cached_proposals = cached_proposals
            return cached_proposals

        tns_api.get_tns_credentials = patched_get_tns_credentials
        tns_api.group_names = patched_group_names
        OCSBaseForm.proposal_choices = patched_proposal_choices
        OCSBaseForm._get_instruments = patched__get_instruments
