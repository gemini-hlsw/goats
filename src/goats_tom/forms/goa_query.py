__all__ = ["GOAQueryForm"]

import re

from django import forms


class GOAQueryForm(forms.Form):
    """Form to query GOA data with specific filters."""

    RAW_REDUCED_CHOICES = [
        ("", "Any"),
        ("RAW", "Raw Only"),
        ("PREPARED", "IRAF Reduced (not Cals)"),
        ("PROCESSED_SCIENCE", "Processed Science Only"),
        ("PROCESSED_BIAS", "Processed Biases Only"),
        ("PROCESSED_FLAT", "Processed Flats Only"),
        ("PROCESSED_FRINGE", "Processed Fringe Frames Only"),
        ("PROCESSED_ARC", "Processed Arcs Only"),
        ("PROCESSED_DARK", "Processed Darks Only"),
        ("PROCESSED_STANDARD", "Processed Standards Only"),
        ("PROCESSED_SLITILLUM", "Processed Slit Illuminations Only"),
    ]

    QA_STATE_CHOICES = [
        ("NotFail", "Not Fail"),
        ("AnyQA", "Any"),
        ("Pass", "Pass"),
        ("Lucky", "Pass or Undefined"),
        ("Win", "Pass or Usable"),
        ("Usable", "Usable"),
        ("UndefinedQA", "Undefined"),
        ("Fail", "Fail"),
    ]

    OBSERVATION_TYPES = [
        ("", "Any"),
        ("OBJECT", "Object"),
        ("BIAS", "Bias"),
        ("DARK", "Dark"),
        ("FLAT", "Flat"),
        ("ARC", "Arc"),
        ("PINHOLE", "Pinhole"),
        ("RONCHI", "Ronchi"),
        ("CAL", "Calibration"),
        ("FRINGE", "Fring"),
        ("MASK", "MOS Mask"),
        ("BPM", "BPM"),
    ]

    OBSERVATION_CLASSES = [
        ("", "Any"),
        ("science", "Science"),
        ("acq", "Acquisition"),
        ("progCal", "Program Calibration"),
        ("dayCal", "Day Calibration"),
        ("partnerCal", "Partner Calibration"),
        ("acqCal", "Acquisition Calibration"),
    ]

    DOWNLOAD_CALIBRATION_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("only", "Only Calibrations"),
    ]

    observation_class = forms.ChoiceField(
        label="Observation Class",
        choices=OBSERVATION_CLASSES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    observation_type = forms.ChoiceField(
        label="Observation Type",
        choices=OBSERVATION_TYPES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    observation_id = forms.CharField(
        label="Observation ID",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )

    raw_reduced = forms.ChoiceField(
        choices=RAW_REDUCED_CHOICES,
        label="Raw/Reduced",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
        help_text="(Select data by processing state)",
    )

    qa_state = forms.ChoiceField(
        choices=QA_STATE_CHOICES,
        label="QA State",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
        help_text="(Quality of results you wish to access)",
    )

    filename_prefix = forms.CharField(
        label="Filename Prefix",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Leave empty for any"},
        ),
        required=False,
        help_text="(Specify the first part of the filename to match by)",
    )

    download_calibrations = forms.ChoiceField(
        choices=DOWNLOAD_CALIBRATION_CHOICES,
        label="Download Associated Calibrations",
        widget=forms.RadioSelect(attrs={"class": "form-control"}),
        required=True,
    )

    # Need input for hidden field.
    facility = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self) -> None:
        """Create query_params from cleaned_data."""
        cleaned_data = super().clean()

        filename_prefix = cleaned_data.get("filename_prefix")
        qa_state = cleaned_data.get("qa_state")
        observation_class = cleaned_data.get("observation_class")
        observation_type = cleaned_data.get("observation_type")
        raw_reduced = cleaned_data.get("raw_reduced")
        download_calibrations = cleaned_data.get("download_calibrations")
        prog_id = cleaned_data.get("observation_id")

        args_list = []
        if qa_state:
            args_list.append(qa_state)
        if observation_class:
            args_list.append(observation_class)
        if observation_type:
            args_list.append(observation_type)
        if raw_reduced:
            args_list.append(raw_reduced)

        query_params = {"args": tuple(args_list), "kwargs": {}}
        if filename_prefix:
            # Use regex to remove any extension from filename_prefix.
            filename_prefix = re.sub(r"(\.[^.]+)+$", "", filename_prefix)
            query_params["kwargs"]["filepre"] = filename_prefix
        if download_calibrations:
            query_params["kwargs"]["download_calibrations"] = download_calibrations
        if prog_id:
            query_params["kwargs"]["progid"] = prog_id

        cleaned_data["query_params"] = query_params
        self.cleaned_data = cleaned_data

