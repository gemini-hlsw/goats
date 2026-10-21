"""
Serializer for the GMOS long slit spatial offsets, submitted as JSON.
"""

__all__ = ["SlitTelescopeConfigsSerializer"]

from typing import Any

from gpp_client.generated.enums import GuideState, SlitOffsetMode
from gpp_client.generated.input_types import SlitTelescopeConfigsInput
from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer

# Payload key holding the offsets of each mode.
MODE_KEYS = {
    SlitOffsetMode.NOD_ALONG_SLIT.value: "alongSlit",
    SlitOffsetMode.NOD_TO_SKY.value: "toSky",
}


class ArcsecondsSerializer(serializers.Serializer):
    """Serializer for one axis of an offset."""

    arcseconds = serializers.FloatField()


class SkyOffsetSerializer(serializers.Serializer):
    """Serializer for a p/q offset."""

    p = ArcsecondsSerializer()
    q = ArcsecondsSerializer()


class AlongSlitConfigSerializer(serializers.Serializer):
    """Serializer for one telescope config along the slit."""

    q = ArcsecondsSerializer()
    guiding = serializers.ChoiceField(choices=[g.value for g in GuideState])


class ToSkyConfigSerializer(serializers.Serializer):
    """Serializer for one telescope config to sky."""

    offset = SkyOffsetSerializer()
    guiding = serializers.ChoiceField(choices=[g.value for g in GuideState])


class SlitTelescopeConfigsSerializer(_BaseGPPSerializer):
    """Serializer for the spatial offsets sent by the observation form."""

    pydantic_model = SlitTelescopeConfigsInput

    offsetMode = serializers.ChoiceField(choices=list(MODE_KEYS))
    alongSlit = AlongSlitConfigSerializer(many=True, required=False)
    toSky = ToSkyConfigSerializer(many=True, required=False)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Check the chosen mode carries at least one offset.

        Parameters
        ----------
        data : dict[str, Any]
            The validated field data.

        Returns
        -------
        dict[str, Any]
            The same data.

        Raises
        ------
        serializers.ValidationError
            If the chosen mode has no offsets.
        """
        key = MODE_KEYS[data["offsetMode"]]
        if not data.get(key):
            raise serializers.ValidationError({key: "At least one offset is required."})
        return data

    def format_gpp(self) -> dict[str, Any]:
        """
        Format the offsets of the chosen mode for GPP.

        Returns
        -------
        dict[str, Any]
            A ``SlitTelescopeConfigsInput`` payload.
        """
        data = self.validated_data
        key = MODE_KEYS[data["offsetMode"]]

        if key == "alongSlit":
            configs = [
                {"q": {"arcseconds": c["q"]["arcseconds"]}, "guiding": c["guiding"]}
                for c in data[key]
            ]
        else:
            configs = [
                {
                    "offset": {
                        "p": {"arcseconds": c["offset"]["p"]["arcseconds"]},
                        "q": {"arcseconds": c["offset"]["q"]["arcseconds"]},
                    },
                    "guiding": c["guiding"],
                }
                for c in data[key]
            ]

        return {key: configs}
