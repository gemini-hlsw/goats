"""
Instrument serializer and input model registry for GPP.
"""

__all__ = [
    "InstrumentRegistry",
    "InstrumentInputModelInstance",
    "InstrumentInputModelClass",
]

from gpp_client.api.enums import ObservingModeType
from gpp_client.api.input_types import (
    GmosNorthLongSlitInput,
    GmosSouthLongSlitInput,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .gmos_north_long_slit import GMOSNorthLongSlitSerializer
from .gmos_south_long_slit import GMOSSouthLongSlitSerializer

InstrumentInputModelClass = type[GmosNorthLongSlitInput] | type[GmosSouthLongSlitInput]
"""
Type alias for instrument input model classes. Must be updated when new instruments
are added.
"""

InstrumentInputModelInstance = GmosNorthLongSlitInput | GmosSouthLongSlitInput
"""
Type alias for instrument input model instances. Must be updated when new
instruments are added.
"""


class InstrumentRegistry:
    """
    Central registry for instrument serializers and GPP input model mappings.
    """

    _registry: dict[
        str, tuple[type[serializers.Serializer], InstrumentInputModelClass]
    ] = {
        # GMOS South Long Slit.
        ObservingModeType.GMOS_SOUTH_LONG_SLIT.value: (
            GMOSSouthLongSlitSerializer,
            GmosSouthLongSlitInput,
        ),
        # GMOS North Long Slit.
        ObservingModeType.GMOS_NORTH_LONG_SLIT.value: (
            GMOSNorthLongSlitSerializer,
            GmosNorthLongSlitInput,
        ),
    }
    """Mapping of observing mode keys to (serializer, input model) tuples."""

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
            return cls._registry[lookup_key][0]
        except KeyError:
            raise ValidationError(f"Unsupported instrument type: {lookup_key}")

    @classmethod
    def get_input_model(cls, key: str | ObservingModeType) -> InstrumentInputModelClass:
        """
        Retrieve the input model class for a given instrument key.

        Parameters
        ----------
        key : str | ObservingModeType
            The instrument key as a string or ObservingModeType enum.

        Returns
        -------
        InstrumentInputModelClass
            The corresponding input model class.

        Raises
        ------
        ValidationError
            If the instrument key is not supported.
        """
        lookup_key = key.value if isinstance(key, ObservingModeType) else key
        try:
            return cls._registry[lookup_key][1]
        except KeyError:
            raise ValidationError(f"Unsupported instrument type: {lookup_key}")
