"""
Serializer registry for Spectral Energy Distribution (SED) types. Provides mapping from
SED type keys to their corresponding serializer classes.
"""

__all__ = ["SEDRegistry", "SEDType"]

from enum import Enum

from rest_framework import serializers

from .black_body import BlackBodySerializer


class SEDType(str, Enum):
    """
    Enumeration of supported SED types. Only 'Black Body' is currently implemented.
    """

    BLACK_BODY = "blackBodyTempK"
    # STELLAR_LIBRARY = "stellarLibrary"
    # COOL_STAR = "coolStar"
    # GALAXY = "galaxy"
    # PLANET = "planet"
    # QUASAR = "quasar"
    # HII_REGION = "hiiRegion"
    # PLANETARY_NEBULA = "planetaryNebula"
    # POWER_LAW = "powerLaw"
    # FLUX_DENSITIES = "fluxDensities"
    # FLUX_DENSITIES_ATTACHMENT = "fluxDensitiesAttachment"


class SEDRegistry:
    _registry = {
        SEDType.BLACK_BODY.value: BlackBodySerializer,
    }

    @classmethod
    def get_serializer(cls, key: str | SEDType) -> type[serializers.Serializer]:
        """
        Retrieve the serializer class for a given SED type key.

        Parameters
        ----------
        key : str | SEDType
            The SED type key as a string or SEDType enum.

        Returns
        -------
        type[serializers.Serializer]
            The corresponding serializer class.

        Raises
        ------
        ValidationError
            If the SED type key is not supported.
        """
        lookup_key = key.value if isinstance(key, SEDType) else key
        try:
            return cls._registry[lookup_key]
        except KeyError:
            raise serializers.ValidationError(f"Unsupported SED type: {lookup_key}")
