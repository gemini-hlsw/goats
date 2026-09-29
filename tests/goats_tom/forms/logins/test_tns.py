from goats_tom.forms import TNSLoginForm


class TestTNSLoginForm:
    def test_valid_form(self):
        form_data = {
            "token": "abc123",
            "bot_id": "my_bot_id",
            "bot_name": "my_bot_name",
        }
        form = TNSLoginForm(data=form_data)
        assert form.is_valid()

    def test_invalid_when_missing_fields(self):
        form = TNSLoginForm(data={})
        assert not form.is_valid()
        assert "token" in form.errors
        assert "bot_id" in form.errors
        assert "bot_name" in form.errors

    def test_it_does_not_ask_for_group_names(self):
        """Groups are rows edited in their own table, not free text here.

        Typing them here made the name the identity of a group, so
        correcting a typo revoked everyone approved for the old spelling.
        """
        assert "group_names" not in TNSLoginForm().fields
