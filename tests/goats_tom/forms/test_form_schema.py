from django import forms

from goats_tom.forms.form_schema import FULL, describe_field, describe_form


def test_a_field_is_described_with_what_it_takes():
    described = describe_field(
        "ipp_value",
        forms.FloatField(
            label="IPP factor",
            help_text="  Between 0.5 and 2.0.  ",
            min_value=0.5,
            max_value=2.0,
            initial=1.05,
        ),
    )

    assert described["type"] == "float"
    assert described["label"] == "IPP factor"
    assert described["help_text"] == "Between 0.5 and 2.0."
    assert described["min"] == 0.5
    assert described["max"] == 2.0
    assert described["initial"] == 1.05
    assert described["width"] == 6


def test_a_decimal_is_not_described_as_a_whole_number():
    """Django's FloatField and DecimalField both subclass IntegerField.

    Described as integers, their inputs get no step and the browser refuses
    the decimals the form itself offers.
    """
    assert describe_field("a", forms.FloatField())["type"] == "float"
    assert describe_field("b", forms.DecimalField())["type"] == "float"
    assert describe_field("c", forms.IntegerField())["type"] == "integer"


def test_help_that_is_only_whitespace_is_dropped():
    """``BLANCOSettings.exposure_time_help`` is a block of spaces."""
    described = describe_field("exposure_time", forms.FloatField(help_text="\n     "))

    assert described["help_text"] == ""


def test_a_form_is_described_in_the_order_asked_for():
    class Stub(forms.Form):
        first = forms.CharField()
        second = forms.CharField()

    described = describe_form(Stub(), ["second", "missing", "first"])

    assert [field["name"] for field in described] == ["second", "first"]


def test_a_field_can_be_asked_for_the_whole_row():
    class Stub(forms.Form):
        name = forms.CharField()

    described = describe_form(Stub(), ["name"], {"name": FULL})

    assert described[0]["width"] == FULL
