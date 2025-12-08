from goats_tom.forms import AstroDatalabLoginForm

class TestAstroDatalabLoginForm:
    def test_valid_form(self):
        form = AstroDatalabLoginForm(data={"username": "astro_user", "password": "test"})
        assert form.is_valid()

    def test_missing_fields(self):
        form = AstroDatalabLoginForm(data={})
        assert not form.is_valid()
        assert "username" in form.errors
        assert "password" in form.errors
