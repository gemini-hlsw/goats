"""
Serializer for GMOS-South imaging input data. This serializer is identical to the
GMOS-North imaging serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSSouthImagingSerializer"]

from gpp_client.generated.input_types import GmosSouthImagingInput

from goats_tom.serializers.gpp.instruments.gmos._base_gmos_imaging import (
    _BaseGMOSImagingSerializer,
)


class GMOSSouthImagingSerializer(_BaseGMOSImagingSerializer):
    """Serializer for GMOS-South imaging input data."""

    pydantic_model = GmosSouthImagingInput
