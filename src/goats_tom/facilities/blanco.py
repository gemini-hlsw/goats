"""GOATS-owned BLANCO observation form.

Two things are put right here, on the form the facility hands out. The
vendored form hard-codes NEWFIRM's instrument parameters and sends them
whatever the instrument, so DECam is asked for a ``detector_centering`` it
rejects and for a dither it does not have; those fields are rebuilt from the
portal's own schema instead. And the fields the toolkit never labels are
given the names the portal's form uses.
"""

__all__ = ["GOATSBLANCOImagingObservationForm"]

import re
from typing import Any

from django import forms
from tom_observations.facilities.blanco import BLANCOImagingObservationForm
from tom_observations.facilities.ocs import OCSFullObservationForm

from . import instrument_schema as schema

#: What the portal calls the request fields. Left unnamed, Django invents a
#: label from the field name, so ``observation_mode`` reads "Observation
#: mode" where the portal says "Mode".
PORTAL_LABELS = {
    "name": "Request Name",
    "observation_mode": "Mode",
    "ipp_value": "IPP Factor",
    "optimization_type": "Optimization Type",
}

#: What the toolkit says about the cadence fields is "Decimal Hours", which
#: the unit beside the control already says. What it does not say is that a
#: cadence is not a second window: the portal expands the request into one
#: observation per period, and the window it was given is dropped.
PORTAL_HELP = {
    "period": (
        "Hours between one observation and the next. Filling the cadence in "
        "replaces the window: the portal expands the request into one "
        "observation per period, each with a window of its own."
    ),
    "jitter": (
        "Hours an observation may fall either side of its cadence time, when "
        "the exact one cannot be scheduled."
    ),
}

#: The same, for the fields a configuration carries.
CONFIGURATION_LABELS = {
    "instrument_type": "Instrument",
    "configuration_type": "Type",
    "max_airmass": "Maximum Airmass",
    "min_lunar_distance": "Minimum Lunar Separation",
    "max_lunar_phase": "Maximum Lunar Phase",
}

#: The parameters the vendored form adds for NEWFIRM and sends for every
#: instrument. They come back from the schema as ``c_<n>_extra_<name>``.
VENDORED_PARAMETERS = (
    "dither_value",
    "dither_sequence",
    "detector_centering",
    "dither_sequence_random_offset",
)
VENDORED_EXPOSURE_PARAMETERS = ("coadds", "sequence_repeats")

#: The offsets that place an exposure, which the portal asks for and the
#: toolkit's form has no field for.
OFFSETS = {"ra": "Offset Right Ascension", "dec": "Offset Declination"}

#: What a field is measured in, by what its name ends in. Shown beside the
#: control, the way the GPP form shows its own.
UNITS = {
    "exposure_time": "s",
    "offset_ra": "arcsec",
    "offset_dec": "arcsec",
    f"{schema.EXTRA}_dither_value": "arcsec",
    "min_lunar_distance": "deg",
    "acceptability_threshold": "%",
    "period": "h",
    "jitter": "h",
}

#: What the toolkit leaves optional and the request cannot do without. An
#: exposure with no time is not refused: it is dropped, and a configuration
#: left with no exposure is dropped after it, so a request that looked filled
#: in comes back saying it has no configurations at all.
ALWAYS_REQUIRED = ("exposure_time",)

#: The telescope every instrument on offer here sits on. Said again on each
#: option -- "Blanco DECam", "DECam default" -- it is width spent repeating
#: what the form already says.
_TELESCOPE = "blanco"

#: ``c_1_ic_1_exposure_time`` is an ``exposure_time``.
_POSITION = re.compile(r"^c_\d+_(ic_\d+_)?")

#: The configuration and the exposure a field belongs to.
_EXPOSURE = re.compile(r"^c_(?P<configuration>\d+)_ic_(?P<exposure>\d+)_")


def _short(label: Any, said: set[str]) -> Any:
    """One option's name, with what it need not say again taken off."""
    words = str(label).split()
    kept = list(words)
    # Never down to nothing: what an instrument is called is its own name,
    # and a filter is called `r`, which is the whole of what it is called.
    while len(kept) > 1 and kept[0].lower() in said:
        kept.pop(0)
    if len(kept) == len(words):
        return label
    short = " ".join(kept)
    return short.capitalize() if short.isalpha() and short.islower() else short


class GOATSBLANCOImagingObservationForm(BLANCOImagingObservationForm):
    """BLANCO imaging form whose parameters follow the chosen instrument."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._drop_vendored_parameters()
        self._add_request_fields()
        self._add_instrument_parameters()
        self._name_after_the_portal()
        self._shorten_after_the_portal()
        self._explain_after_the_portal()
        self._measure_after_the_portal()

    # -- what the form offers ------------------------------------------------

    def configurations(self) -> range:
        """The configurations this form can carry."""
        return range(1, self.facility_settings.get_setting("max_configurations") + 1)

    def exposures(self) -> range:
        """The exposures a configuration can carry."""
        return range(
            1, self.facility_settings.get_setting("max_instrument_configs") + 1
        )

    def parameters_for(self, instrument_type: str) -> dict[str, dict]:
        """What one instrument declares its configuration accepts."""
        return schema.configuration_parameters(
            self.get_instruments().get(instrument_type) or {}
        )

    def exposure_parameters_for(self, instrument_type: str) -> dict[str, dict]:
        """What one instrument declares its exposures accept."""
        return schema.exposure_parameters(
            self.get_instruments().get(instrument_type) or {}
        )

    def exposure_parameters(self) -> dict[str, dict]:
        """One set of exposure parameters covering every instrument."""
        return schema.merge(
            [
                schema.exposure_parameters(instrument)
                for instrument in self.get_instruments().values()
            ]
        )

    def parameters(self) -> dict[str, dict]:
        """One set of parameters covering every instrument on offer."""
        return schema.merge(
            [
                schema.configuration_parameters(instrument)
                for instrument in self.get_instruments().values()
            ]
        )

    def narrowing(self) -> dict[str, dict]:
        """What each instrument accepts, for the interface to narrow itself."""
        return {
            code: schema.narrowing(instrument)
            for code, instrument in self.get_instruments().items()
        }

    # -- building the form ---------------------------------------------------

    def _drop_vendored_parameters(self) -> None:
        for index in self.configurations():
            for name in VENDORED_PARAMETERS:
                self.fields.pop(f"c_{index}_{name}", None)
            for exposure in self.exposures():
                for name in VENDORED_EXPOSURE_PARAMETERS:
                    self.fields.pop(f"c_{index}_ic_{exposure}_{name}", None)

    def _add_request_fields(self) -> None:
        """Add what the portal asks for above the configurations."""
        self.fields["acceptability_threshold"] = forms.FloatField(
            required=False,
            min_value=0,
            max_value=100,
            initial=self._threshold_on_offer(),
            label="Acceptability Threshold",
            help_text=(
                "The percentage of the observation that must be completed to "
                "mark the request as complete and avert rescheduling."
            ),
            widget=forms.TextInput(attrs={"placeholder": "Percent"}),
        )

    def _threshold_on_offer(self) -> float | None:
        """What the instruments settle for, when they all settle for the same."""
        thresholds = {
            instrument.get("default_acceptability_threshold")
            for instrument in self.get_instruments().values()
        }
        return thresholds.pop() if len(thresholds) == 1 else None

    def _add_instrument_parameters(self) -> None:
        """Add a field per parameter any instrument on offer declares."""
        parameters = self.parameters()
        exposure_parameters = self.exposure_parameters()
        for index in self.configurations():
            for name, spec in parameters.items():
                self.fields[f"c_{index}_{schema.EXTRA}_{name}"] = schema.build_field(
                    name, spec
                )
            for exposure in self.exposures():
                prefix = f"c_{index}_ic_{exposure}"
                for name, spec in exposure_parameters.items():
                    self.fields[f"{prefix}_{schema.EXTRA}_{name}"] = schema.build_field(
                        name, spec
                    )
                for axis, label in OFFSETS.items():
                    self.fields[f"{prefix}_offset_{axis}"] = forms.FloatField(
                        required=False,
                        label=label,
                        help_text=(
                            "Offset this exposure from the configuration's "
                            "target, in arcseconds. Used for dithering."
                        ),
                        widget=forms.TextInput(attrs={"placeholder": "Arc seconds"}),
                    )

    def _name_after_the_portal(self) -> None:
        """Give the fields the names the portal's own form uses."""
        labels = dict(PORTAL_LABELS)
        for index in self.configurations():
            for suffix, label in CONFIGURATION_LABELS.items():
                labels[f"c_{index}_{suffix}"] = label
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label

    def _shorten_after_the_portal(self) -> None:
        """Drop from every option what naming it again does not tell anyone."""
        said = {_TELESCOPE} | {
            word.lower()
            for instrument in self.get_instruments().values()
            for word in str(instrument.get("name", "")).split()
        }
        for field in self.fields.values():
            choices = getattr(field, "choices", None)
            if choices:
                field.choices = [
                    (value, _short(label, said)) for value, label in choices
                ]

    def _explain_after_the_portal(self) -> None:
        """Say what the toolkit's own help leaves unsaid."""
        for name, help_text in PORTAL_HELP.items():
            if name in self.fields:
                self.fields[name].help_text = help_text

    # -- building the payload ------------------------------------------------

    def _instrument_for(self, configuration_id: int) -> str:
        """The instrument chosen in one configuration."""
        return self.cleaned_data.get(
            f"c_{configuration_id}_instrument_type"
        ) or self.data.get(f"c_{configuration_id}_instrument_type", "")

    def _measure_after_the_portal(self) -> None:
        """Say what each field is measured in, beside the control."""
        for name, field in self.fields.items():
            unit = UNITS.get(_POSITION.sub("", name))
            if unit:
                field.widget.attrs["data-unit"] = unit
                # The unit is beside the control now, not inside it.
                field.widget.attrs.pop("placeholder", None)

    def _build_configuration(self, build_id: int) -> dict[str, Any] | None:
        # Skips BLANCO's version, which writes NEWFIRM's parameters whatever
        # the instrument, and fills them from the chosen instrument instead.
        configuration = OCSFullObservationForm._build_configuration(self, build_id)
        if configuration is None:
            return None
        configuration["extra_params"] = self._parameters_sent(build_id)
        return configuration

    def _parameters_sent(self, configuration_id: int) -> dict[str, Any]:
        """Gather what the chosen instrument takes, falling back to defaults."""
        return self._sent(
            f"c_{configuration_id}",
            self.parameters_for(self._instrument_for(configuration_id)),
        )

    def _sent(self, prefix: str, parameters: dict[str, dict]) -> dict[str, Any]:
        """The values one set of parameters carries, defaults filled in."""
        sent: dict[str, Any] = {}
        for name, spec in parameters.items():
            value = self.cleaned_data.get(f"{prefix}_{schema.EXTRA}_{name}")
            if value in (None, ""):
                if "default" not in spec:
                    continue
                value = spec["default"]
            sent[name] = schema.cast(value, spec)
        return sent

    def _build_instrument_config(
        self, instrument_type: str, configuration_id: int, instrument_config_id: int
    ) -> dict[str, Any] | None:
        # Skips BLANCO's version, which sends NEWFIRM's coadds and repeats
        # whatever the instrument.
        instrument_config = OCSFullObservationForm._build_instrument_config(
            self, instrument_type, configuration_id, instrument_config_id
        )
        if instrument_config is None:
            return None
        prefix = f"c_{configuration_id}_ic_{instrument_config_id}"
        instrument_config["extra_params"] = self._sent(
            prefix, self.exposure_parameters_for(instrument_type)
        )
        for axis in OFFSETS:
            offset = self.cleaned_data.get(f"{prefix}_offset_{axis}")
            # Left out when blank, so an unoffset exposure is unchanged.
            if offset is not None:
                instrument_config[f"offset_{axis}"] = offset
        return instrument_config

    def observation_payload(self) -> dict[str, Any]:
        payload = super().observation_payload()
        threshold = self.cleaned_data.get("acceptability_threshold")
        if threshold is not None:
            for request in payload.get("requests", []):
                request["acceptability_threshold"] = threshold
        return payload

    # -- checking what was entered -------------------------------------------

    def clean(self) -> dict[str, Any]:
        """Refuse what the instrument chosen for a configuration will not take."""
        cleaned_data = super().clean()
        self._require_what_cannot_be_left_out()
        for index in self.configurations():
            instrument_type = self._instrument_for(index)
            if not instrument_type:
                continue
            instrument = self.get_instruments().get(instrument_type) or {}
            self._refuse(
                f"c_{index}", self.parameters_for(instrument_type), schema.EXTRA
            )
            for exposure in self.exposures():
                prefix = f"c_{index}_ic_{exposure}"
                self._refuse(
                    prefix, self.exposure_parameters_for(instrument_type), schema.EXTRA
                )
                self._refuse(prefix, schema.base_bounds(instrument), None)
        return cleaned_data

    def _require_what_cannot_be_left_out(self) -> None:
        """Ask again for what only the exposures that were drawn have to answer.

        The field itself cannot be required: one is declared for every
        exposure the facility allows, and a request that draws one would be
        refused on behalf of the ones it never drew. Nor can a parameter be,
        since whether it is asked for at all is the chosen instrument's to
        say -- NEWFIRM insists on its coadds, DECam has none.
        """
        for index, exposure in self._exposures_asked_for():
            prefix = f"c_{index}_ic_{exposure}"
            for suffix in ALWAYS_REQUIRED:
                self._insist(f"{prefix}_{suffix}")
            parameters = self.exposure_parameters_for(self._instrument_for(index))
            for name, spec in parameters.items():
                if spec.get("required"):
                    self._insist(f"{prefix}_{schema.EXTRA}_{name}")

    def _insist(self, name: str) -> None:
        """Report a field left empty that had to be answered."""
        if name in self.fields and self.cleaned_data.get(name) in (None, ""):
            self.add_error(name, "This field is required.")

    def _exposures_asked_for(self) -> set[tuple[int, int]]:
        """The exposures the interface drew, which are the ones it sent."""
        asked: set[tuple[int, int]] = set()
        for name in self.data:
            match = _EXPOSURE.match(name)
            if match:
                asked.add((int(match["configuration"]), int(match["exposure"])))
        return asked

    def _refuse(
        self, prefix: str, parameters: dict[str, dict], marker: str | None
    ) -> None:
        """Report the values this instrument will not take."""
        for name, spec in parameters.items():
            field_name = f"{prefix}_{marker}_{name}" if marker else f"{prefix}_{name}"
            value = self.cleaned_data.get(field_name)
            if field_name not in self.fields or value in (None, ""):
                continue
            refusal = schema.check(value, spec)
            if refusal:
                self.add_error(field_name, refusal)
