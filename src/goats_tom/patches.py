"""
Patches to third-party libraries to modify their behavior.
"""

__all__ = ["apply_all_patches", "apply_tns_patches", "apply_ocs_patches"]

import logging

logger = logging.getLogger(__name__)


def apply_tns_patches() -> None:
    """
    Monkey-patch tom-tns so it prefers per-request creds over global ones. We keep a
    reference to the original helper so we can delegate to it when the credentials have
    not been set for the context or other uncaught issues arise.
    """
    from tom_tns import tns_api  # noqa: PLC0415

    from goats_tom.middleware.tns import current_tns_creds  # noqa: PLC0415

    # Avoid double-patching.
    if getattr(tns_api.get_tns_credentials, "_goats_patched", False):
        logger.debug("Skipping tom-tns patches; already applied")
        return

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

    # Mark as patched to avoid double-patching.
    patched_get_tns_credentials._goats_patched = True  # type: ignore[attr-defined]
    patched_group_names._goats_patched = True  # type: ignore[attr-defined]

    tns_api.get_tns_credentials = patched_get_tns_credentials
    tns_api.group_names = patched_group_names

    # logger.debug("Applied tom-tns patches for per-request credentials")


def apply_ocs_patches() -> None:
    """Patch OCSBaseForm to cache instruments/proposals per user."""
    from urllib.parse import urljoin  # noqa: PLC0415

    from django.core.cache import cache  # noqa: PLC0415
    from tom_common.exceptions import ImproperCredentialsException  # noqa: PLC0415
    from tom_observations.facilities.ocs import (  # noqa: PLC0415
        OCSBaseForm,
        OCSBaseObservationForm,
        make_request,
    )

    if getattr(OCSBaseForm, "_goats_patched", False):
        logger.debug("Skipping OCSBaseForm patches; already applied")
        return

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
        cache_key = f"{self.facility_settings.facility_name}_user_{user.pk}_instruments"
        cached_instruments = cache.get(cache_key)

        if cached_instruments is not None:
            self._cached_instruments = cached_instruments
            return cached_instruments

        logger.debug("Fetching instruments from OCS portal for user %r", user.username)
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
            cached_instruments = self.facility_settings.default_instrument_config
        cache.set(
            cache_key,
            cached_instruments,
            60,
        )
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
        cache_key = f"{self.facility_settings.facility_name}_user_{user.pk}_proposals"
        cached_proposals = cache.get(cache_key)

        if cached_proposals is not None:
            self._cached_proposals = cached_proposals
            return cached_proposals

        logger.debug("Fetching proposals from OCS portal for user %r", user.username)
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
        for p in response.json().get("proposals", []):
            if p["current"]:
                cached_proposals.append(
                    (p["id"], "{} ({})".format(p["title"], p["id"]))
                )
        cache.set(
            cache_key,
            cached_proposals,
            60,
        )
        self._cached_proposals = cached_proposals
        return cached_proposals

    def patched_validate_at_facility(self):
        from tom_observations.facility import get_service_class  # noqa: PLC0415

        user = getattr(getattr(self, "facility_settings", None), "_user", None)

        facility_cls = get_service_class(self.cleaned_data["facility"])
        facility = facility_cls()

        if (
            user
            and getattr(user, "is_authenticated", False)
            and hasattr(facility, "set_user")
        ):
            facility.set_user(user)

        payload = self.observation_payload()

        logger.debug(
            f"validate_at_facility: {facility.__class__.__name__} for user '{user}'",
        )

        response = facility.validate_observation(payload)

        if response.get("request_durations", {}).get("duration"):
            duration = response["request_durations"]["duration"]
            self.validation_message = (
                f"This observation is valid with a duration of {duration} seconds."
            )

        if response.get("errors"):
            self.add_error(None, self._flatten_error_dict(response["errors"]))

    OCSBaseObservationForm.validate_at_facility = patched_validate_at_facility
    OCSBaseForm._goats_patched = True  # type: ignore[attr-defined]
    OCSBaseForm._get_instruments = patched__get_instruments
    OCSBaseForm.proposal_choices = patched_proposal_choices

    # logger.debug("Applied OCSBaseForm patches for per-user caching")


def apply_all_patches() -> None:
    """Apply all patches."""
    # logger.debug("Applying all patches")
    apply_tns_patches()
    apply_ocs_patches()
