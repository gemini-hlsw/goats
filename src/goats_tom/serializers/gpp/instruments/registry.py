"""
Instrument registry for GPP instrument serializers.
"""

__all__ = [
    "InstrumentRegistry",
]

from gpp_client.api.enums import ObservingModeType
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .gmos_north_long_slit import GMOSNorthLongSlitSerializer
from .gmos_south_long_slit import GMOSSouthLongSlitSerializer


class InstrumentRegistry:
    """
    Registry mapping observing mode types to their corresponding instrument serializers.
    """

    _registry: dict[str, type[serializers.Serializer]] = {
        # GMOS South Long Slit.
        ObservingModeType.GMOS_SOUTH_LONG_SLIT.value: GMOSSouthLongSlitSerializer,
        # GMOS North Long Slit.
        ObservingModeType.GMOS_NORTH_LONG_SLIT.value: GMOSNorthLongSlitSerializer,
    }
    """
    Defines the mapping from observing mode type keys to their corresponding serializer
    classes.
    """

    @classmethod
    def get_serializer(
        cls, key: str | ObservingModeType
    ) -> type[serializers.Serializer]:
        """
        Retrieve the serializer class for a given instrument key.

        Parameters
        ----------
        key : str | ObservingModeType
            The instrument key as a string or ObservingModeType enum.

        Returns
        -------
        type[serializers.Serializer]
            The corresponding serializer class.

        Raises
        ------
        ValidationError
            If the instrument key is not supported.
        """
        lookup_key = key.value if isinstance(key, ObservingModeType) else key
        try:
            return cls._registry[lookup_key]
        except KeyError:
            raise ValidationError(f"Unsupported instrument type: {lookup_key}")
