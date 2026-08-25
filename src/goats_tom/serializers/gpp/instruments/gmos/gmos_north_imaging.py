"""
Serializer for GMOS-North imaging input data. This serializer is identical to the
GMOS-South imaging serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSNorthImagingSerializer"]

from gpp_client.generated.input_types import GmosNorthImagingInput

from goats_tom.serializers.gpp.instruments.gmos._base_gmos_imaging import (
    _BaseGMOSImagingSerializer,
)


class GMOSNorthImagingSerializer(_BaseGMOSImagingSerializer):
    """Serializer for GMOS-North imaging input data."""

    pydantic_model = GmosNorthImagingInput
