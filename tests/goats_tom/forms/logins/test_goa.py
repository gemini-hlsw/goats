from goats_tom.forms import GOALoginForm


class TestGOALoginForm:
    def test_valid_form(self):
        form = GOALoginForm(data={"username": "goa_user", "password": "hunter2"})
        assert form.is_valid()

    def test_missing_fields(self):
        form = GOALoginForm(data={})
        assert not form.is_valid()
        assert "username" in form.errors
        assert "password" in form.errors
