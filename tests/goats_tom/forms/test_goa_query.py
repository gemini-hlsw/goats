from django.test import TestCase

from goats_tom.forms import GOAQueryForm


class TestGOAQueryForm(TestCase):
    def test_form_fields(self):
        form = GOAQueryForm()
        assert "observation_class" in form.fields
        assert "observation_type" in form.fields
        assert "raw_reduced" in form.fields
        assert "qa_state" in form.fields
        assert "filename_prefix" in form.fields
        assert "download_calibrations" in form.fields
        assert "facility" in form.fields

    def test_required_fields(self):
        form = GOAQueryForm(data={})
        assert not form.is_valid()
        assert "download_calibrations" in form.errors
        print(form.errors)

    def test_valid_data(self):
        form_data = {"download_calibrations": "yes", "facility": "test_facility"}
        form = GOAQueryForm(data=form_data)
        assert form.is_valid()

    def test_clean_method(self):
        form_data = {
            "download_calibrations": "yes",
            "qa_state": "Pass",
            "filename_prefix": "test_prefix",
            "facility": "test_facility",
        }
        form = GOAQueryForm(data=form_data)
        assert form.is_valid()
        assert "query_params" in form.cleaned_data
        assert form.cleaned_data["query_params"]["kwargs"]["filepre"] == "test_prefix"
