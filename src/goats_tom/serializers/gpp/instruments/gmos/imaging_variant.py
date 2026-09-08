"""
Serializer for the GMOS imaging offset variant, submitted as JSON.
"""

__all__ = ["ImagingVariantSerializer"]

from typing import Any

from gpp_client.generated.enums import (
    GuideState,
    ImagingVariantType,
    TelescopeConfigGeneratorType,
    WavelengthOrder,
)
from gpp_client.generated.input_types import ImagingVariantInput
from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer

# Payload key holding each variant's block, keyed by variant type.
VARIANT_KEYS = {
    ImagingVariantType.GROUPED.value: "grouped",
    ImagingVariantType.INTERLEAVED.value: "interleaved",
    ImagingVariantType.PRE_IMAGING.value: "preImaging",
}

# The four named offsets a pre-imaging variant carries.
PRE_IMAGING_OFFSET_KEYS = ("offset1", "offset2", "offset3", "offset4")

# Unprefixed parameters each generator needs, used both to validate and to format.
GENERATOR_FIELDS = {
    TelescopeConfigGeneratorType.ENUMERATED.value: ("explicitOffsets",),
    TelescopeConfigGeneratorType.UNIFORM.value: (
        "uniformCornerAP",
        "uniformCornerAQ",
        "uniformCornerBP",
        "uniformCornerBQ",
    ),
    TelescopeConfigGeneratorType.SPIRAL.value: ("spiralSize",),
    TelescopeConfigGeneratorType.RANDOM.value: ("randomSize",),
}


class OffsetComponentSerializer(serializers.Serializer):
    """Serializer for one axis of an offset."""

    arcseconds = serializers.FloatField(allow_null=True)


class OffsetSerializer(serializers.Serializer):
    """Serializer for a p/q offset."""

    p = OffsetComponentSerializer()
    q = OffsetComponentSerializer()


class TelescopeConfigSerializer(serializers.Serializer):
    """Serializer for one entry of an enumerated offset list."""

    offset = OffsetSerializer()
    guiding = serializers.ChoiceField(
        choices=[g.value for g in GuideState],
        required=False,
        allow_null=True,
    )


class ImagingVariantSerializer(_BaseGPPSerializer):
    """Serializer for the imaging offset variant sent by the observation form."""

    pydantic_model = ImagingVariantInput

    variant = serializers.ChoiceField(
        choices=[v.value for v in ImagingVariantType],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    wavelengthOrder = serializers.ChoiceField(
        choices=[o.value for o in WavelengthOrder], required=False, allow_null=True
    )
    skyOffsetCount = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    preImagingOffsets = OffsetSerializer(
        many=True, required=False, max_length=len(PRE_IMAGING_OFFSET_KEYS)
    )

    # Science offsets.
    offsets = serializers.ChoiceField(
        choices=[t.value for t in TelescopeConfigGeneratorType],
        required=False,
        allow_null=True,
    )
    explicitOffsets = TelescopeConfigSerializer(many=True, required=False)
    uniformCornerAP = serializers.FloatField(required=False, allow_null=True)
    uniformCornerAQ = serializers.FloatField(required=False, allow_null=True)
    uniformCornerBP = serializers.FloatField(required=False, allow_null=True)
    uniformCornerBQ = serializers.FloatField(required=False, allow_null=True)
    spiralSize = serializers.FloatField(required=False, allow_null=True, min_value=0)
    randomSize = serializers.FloatField(required=False, allow_null=True, min_value=0)

    # Sky offsets.
    skyOffsets = serializers.ChoiceField(
        choices=[t.value for t in TelescopeConfigGeneratorType],
        required=False,
        allow_null=True,
    )
    skyExplicitOffsets = TelescopeConfigSerializer(many=True, required=False)
    skyUniformCornerAP = serializers.FloatField(required=False, allow_null=True)
    skyUniformCornerAQ = serializers.FloatField(required=False, allow_null=True)
    skyUniformCornerBP = serializers.FloatField(required=False, allow_null=True)
    skyUniformCornerBQ = serializers.FloatField(required=False, allow_null=True)
    skySpiralSize = serializers.FloatField(required=False, allow_null=True, min_value=0)
    skySpiralCenterP = serializers.FloatField(required=False, allow_null=True)
    skySpiralCenterQ = serializers.FloatField(required=False, allow_null=True)
    skyRandomSize = serializers.FloatField(required=False, allow_null=True, min_value=0)
    skyRandomCenterP = serializers.FloatField(required=False, allow_null=True)
    skyRandomCenterQ = serializers.FloatField(required=False, allow_null=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Check the payload carries everything the chosen variant needs.

        Parameters
        ----------
        data : dict[str, Any]
            The validated field data.

        Returns
        -------
        dict[str, Any]
            The same data, once it is known to be complete.
        """
        if data["variant"] == ImagingVariantType.PRE_IMAGING.value:
            self._validate_pre_imaging(data)
            return data

        self._validate_generator(data, "offsets", prefix="")
        self._validate_generator(data, "skyOffsets", prefix="sky")

        return data

    def _validate_pre_imaging(self, data: dict[str, Any]) -> None:
        """
        Check each pre-imaging offset is either complete or absent.

        Parameters
        ----------
        data : dict[str, Any]
            The validated field data.

        Raises
        ------
        serializers.ValidationError
            If an offset carries one axis but not the other.
        """
        for index, offset in enumerate(data.get("preImagingOffsets", []), start=1):
            has_p = offset["p"]["arcseconds"] is not None
            has_q = offset["q"]["arcseconds"] is not None
            if has_p != has_q:
                raise serializers.ValidationError(
                    {
                        "preImagingOffsets": (
                            f"Offset {index} needs both p and q, or neither."
                        )
                    }
                )

    def _validate_generator(
        self, data: dict[str, Any], field: str, prefix: str
    ) -> None:
        """
        Check one generator's parameters are present.

        Parameters
        ----------
        data : dict[str, Any]
            The validated field data.
        field : str
            Name of the field holding the generator type.
        prefix : str
            ``"sky"`` for the sky generator, empty for the science one.

        Raises
        ------
        serializers.ValidationError
            If the generator is missing a required parameter.
        """
        generator = data.get(field)
        if generator in (None, TelescopeConfigGeneratorType.NONE.value):
            return

        missing = [
            key
            for key in (self._key(prefix, name) for name in GENERATOR_FIELDS[generator])
            if self._is_missing(data.get(key))
        ]
        if missing:
            raise serializers.ValidationError(
                {
                    field: (
                        f"{', '.join(missing)} required for a "
                        f"{generator.lower()} generator."
                    )
                }
            )

    @staticmethod
    def _is_missing(value: Any) -> bool:
        """
        Report whether a generator parameter was left out.

        An empty list counts as missing, but a zero does not.

        Parameters
        ----------
        value : Any
            The submitted value.

        Returns
        -------
        bool
            ``True`` when the parameter carries nothing usable.
        """
        return value is None or value == []

    @staticmethod
    def _key(prefix: str, name: str) -> str:
        """
        Build the payload key for a generator parameter.

        Parameters
        ----------
        prefix : str
            ``"sky"`` for the sky generator, empty for the science one.
        name : str
            The unprefixed parameter name.

        Returns
        -------
        str
            The key as it arrives from the form.
        """
        return f"{prefix}{name[0].upper()}{name[1:]}" if prefix else name

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the validated variant for GPP.

        Returns
        -------
        dict[str, Any] | None
            An ``ImagingVariantInput`` payload, or ``None`` if empty.
        """
        data = self.validated_data
        variant = data["variant"]

        if variant == ImagingVariantType.PRE_IMAGING.value:
            block = self._format_pre_imaging(data)
        else:
            block = self._format_offset_variant(data, variant)

        return {VARIANT_KEYS[variant]: block} if block else None

    def _format_pre_imaging(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Format the four named pre-imaging offsets.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data.

        Returns
        -------
        dict[str, Any]
            A ``PreImagingVariantInput`` payload, skipping offsets with no value.
        """
        block: dict[str, Any] = {}

        for key, offset in zip(
            PRE_IMAGING_OFFSET_KEYS, data.get("preImagingOffsets", [])
        ):
            # An offset the form left empty is absent, not zero.
            if offset["p"]["arcseconds"] is None and offset["q"]["arcseconds"] is None:
                continue
            block[key] = self._offset(
                offset["p"]["arcseconds"], offset["q"]["arcseconds"]
            )

        return block

    def _format_offset_variant(
        self, data: dict[str, Any], variant: str
    ) -> dict[str, Any]:
        """
        Format a grouped or interleaved variant.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data.
        variant : str
            The variant type.

        Returns
        -------
        dict[str, Any]
            A grouped or interleaved variant payload.
        """
        block: dict[str, Any] = {}

        if variant == ImagingVariantType.GROUPED.value and (
            order := data.get("wavelengthOrder")
        ):
            block["order"] = order

        if (sky_count := data.get("skyOffsetCount")) is not None:
            block["skyCount"] = sky_count

        if (offsets := self._format_generator(data, "offsets", prefix="")) is not None:
            block["offsets"] = offsets

        sky_offsets = self._format_generator(data, "skyOffsets", prefix="sky")
        if sky_offsets is not None:
            block["skyOffsets"] = sky_offsets

        return block

    def _format_generator(
        self, data: dict[str, Any], field: str, prefix: str
    ) -> dict[str, Any] | None:
        """
        Format one telescope config generator.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data.
        field : str
            Name of the field holding the generator type.
        prefix : str
            ``"sky"`` for the sky generator, empty for the science one.

        Returns
        -------
        dict[str, Any] | None
            A ``TelescopeConfigGeneratorInput`` payload, or ``None`` when no
            generator is selected.
        """
        generator = data.get(field)
        if generator in (None, TelescopeConfigGeneratorType.NONE.value):
            return None

        if generator == TelescopeConfigGeneratorType.ENUMERATED.value:
            key = self._key(prefix, "explicitOffsets")
            values = [
                {
                    "offset": self._offset(
                        item["offset"]["p"]["arcseconds"],
                        item["offset"]["q"]["arcseconds"],
                    ),
                    "guiding": item.get("guiding") or GuideState.ENABLED.value,
                }
                for item in data[key]
            ]
            return {"enumerated": {"values": values}}

        if generator == TelescopeConfigGeneratorType.UNIFORM.value:
            corner = "uniformCorner"
            return {
                "uniform": {
                    "cornerA": self._offset(
                        data[self._key(prefix, f"{corner}AP")],
                        data[self._key(prefix, f"{corner}AQ")],
                    ),
                    "cornerB": self._offset(
                        data[self._key(prefix, f"{corner}BP")],
                        data[self._key(prefix, f"{corner}BQ")],
                    ),
                }
            }

        name = generator.lower()
        body: dict[str, Any] = {
            "size": {"arcseconds": data[self._key(prefix, f"{name}Size")]}
        }

        centre_p = data.get(self._key(prefix, f"{name}CenterP"))
        centre_q = data.get(self._key(prefix, f"{name}CenterQ"))
        if centre_p is not None or centre_q is not None:
            body["center"] = self._offset(centre_p or 0.0, centre_q or 0.0)

        return {name: body}

    @staticmethod
    def _offset(p: float, q: float) -> dict[str, Any]:
        """
        Build an ``OffsetInput`` payload.

        Parameters
        ----------
        p : float
            The p component, in arcseconds.
        q : float
            The q component, in arcseconds.

        Returns
        -------
        dict[str, Any]
            The offset payload.
        """
        return {"p": {"arcseconds": p}, "q": {"arcseconds": q}}
