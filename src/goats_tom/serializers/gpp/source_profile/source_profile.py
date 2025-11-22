"""
Serializers for source profiles used in GPP requests.
"""

__all__ = ["SourceProfileSerializer"]

from enum import Enum
from typing import Any

from gpp_client.api.input_types import SourceProfileInput
from rest_framework import serializers

from .._base_gpp import _BaseGPPSerializer
from .brightnesses import BrightnessesSerializer
from .seds import SEDRegistry, SEDType


class SourceProfileType(str, Enum):
    """
    Enumeration of supported source profile types. Currently only 'Point' is
    implemented.
    """

    POINT = "point"
    # UNIFORM = "uniform"
    # GAUSSIAN = "gaussian"


class SourceProfileSerializer(_BaseGPPSerializer):
    sedProfileTypeSelect = serializers.ChoiceField(
        choices=[e.value for e in SourceProfileType],
        required=False,
        allow_blank=False,
        allow_null=True,
    )
    sedTypeSelect = serializers.ChoiceField(
        choices=[e.value for e in SEDType],
        required=False,
        allow_blank=False,
        allow_null=True,
    )
    pydantic_model = SourceProfileInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data, validating brightnesses and SED if present.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized data.
        """
        internal: dict[str, Any] = super().to_internal_value(data)

        # Validate brightnesses.
        brightnesses = BrightnessesSerializer(data=data)
        brightnesses.is_valid(raise_exception=True)
        self._brightnesses = brightnesses

        # Validate SED if sedTypeSelect is provided.
        sed_type = data.get("sedTypeSelect")
        if sed_type:
            sed_serializer = SEDRegistry.get_serializer(sed_type)
            sed = sed_serializer(data=data)
            sed.is_valid(raise_exception=True)
            self._sed = sed
        else:
            self._sed = None

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the source profile data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted source profile data, or ``None`` if no data was provided.
        """
        profile_type = self.validated_data.get("sedProfileTypeSelect")
        if not profile_type:
            # Nothing to format.
            return None

        band_normalized: dict[str, Any] = {}

        if self.sed is not None:
            sed_data = self.sed.format_gpp()
            if sed_data is not None:
                band_normalized["sed"] = sed_data

        brightness_data = self.brightnesses.format_gpp()
        if brightness_data is not None:
            band_normalized["brightnesses"] = brightness_data["brightnesses"]

        if not band_normalized:
            return None

        return {profile_type: {"bandNormalized": band_normalized}}

    @property
    def brightnesses(self) -> BrightnessesSerializer | None:
        """
        Get the brightnesses instance.

        Returns
        -------
        BrightnessesSerializer | None
            The brightnesses instance, or ``None`` if not set.
        """
        return getattr(self, "_brightnesses", None)

    @property
    def sed(self) -> _BaseGPPSerializer | None:
        """
        Get the SED instance, if present.

        Returns
        -------
        _BaseGPPSerializer | None
            The SED instance, or ``None``.
        """
        return getattr(self, "_sed", None)
