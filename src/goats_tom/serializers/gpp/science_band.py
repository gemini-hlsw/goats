__all__ = ["ScienceBandSerializer"]

from typing import Any

from gpp_client.api.enums import ScienceBand
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class ScienceBandSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP science band selection.
    """

    scienceBand = serializers.ChoiceField(
        choices=[(c.value, c.value) for c in ScienceBand],
        required=True,
        allow_blank=False,
        allow_null=True,
    )

    pydantic_model = None

    def format_gpp(self) -> dict[str, Any]:
        """
        Format the science band data for GPP.

        Returns
        -------
        dict[str, Any]
            The formatted science band data.
        """
        return self.science_band

    @property
    def science_band(self) -> str:
        """
        Get the selected science band value.

        Returns
        -------
        str
            The selected science band value.
        """
        return self.validated_data["scienceBand"]

    @property
    def science_band_enum(self) -> ScienceBand:
        """
        Get the selected science band as an enum.

        Returns
        -------
        ScienceBand
            The selected science band enum.
        """
        return ScienceBand(self.science_band)
