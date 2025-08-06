from goats_tom.forms import LCOLoginForm


class TestLCOLoginForm:
    def test_valid_form(self):
        form = LCOLoginForm(data={"token": "test"})
        assert form.is_valid()

    def test_missing_token(self):
        form = LCOLoginForm(data={})
        assert not form.is_valid()
        assert "token" in form.errors
