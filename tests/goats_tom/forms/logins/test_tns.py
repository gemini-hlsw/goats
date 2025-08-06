from goats_tom.forms import TNSLoginForm


class TestTNSLoginForm:
    def test_valid_form(self):
        form_data = {
            "token": "abc123",
            "bot_id": "my_bot_id",
            "bot_name": "my_bot_name",
            "group_names": "group1\ngroup2\ngroup3",
        }
        form = TNSLoginForm(data=form_data)
        assert form.is_valid()
        assert form.cleaned_data["group_names"] == ["group1", "group2", "group3"]

    def test_invalid_when_missing_fields(self):
        form = TNSLoginForm(data={})
        assert not form.is_valid()
        assert "token" in form.errors
        assert "bot_id" in form.errors
        assert "bot_name" in form.errors
        assert "group_names" in form.errors

    def test_group_names_strips_and_filters_blank_lines(self):
        form_data = {
            "token": "abc123",
            "bot_id": "bot123",
            "bot_name": "cool_bot",
            "group_names": "\ngroup1\n\n group2 \n\n",
        }
        form = TNSLoginForm(data=form_data)
        assert form.is_valid()
        assert form.cleaned_data["group_names"] == ["group1", "group2"]
