from goats_tom.forms import GPPLoginForm


class TestGPPLoginForm:
    def test_valid_form(self):
        form = GPPLoginForm(data={"token": "test"})
        assert form.is_valid()

    def test_missing_token(self):
        form = GPPLoginForm(data={})
        assert not form.is_valid()
        assert "token" in form.errors
