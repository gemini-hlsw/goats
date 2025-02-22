from django.test import TestCase
from goats_tom.forms import BaseLoginForm


class TestBaseLoginForm(TestCase):
    """Tests for the BaseLoginForm."""

    def test_form_valid_data(self) -> None:
        """Test that the form is valid when both username and password are provided."""
        form_data = {
            "username": "testuser",
            "password": "secret123",
        }
        form = BaseLoginForm(data=form_data)
        self.assertTrue(form.is_valid(), "Form should be valid with correct data.")

    def test_form_missing_username(self) -> None:
        """Test that the form is invalid if the username is missing."""
        form_data = {
            "username": "",
            "password": "secret123",
        }
        form = BaseLoginForm(data=form_data)
        self.assertFalse(form.is_valid(), "Form should be invalid if username is empty.")
        self.assertIn("username", form.errors, "Errors should include 'username'.")

    def test_form_missing_password(self) -> None:
        """Test that the form is invalid if the password is missing."""
        form_data = {
            "username": "testuser",
            "password": "",
        }
        form = BaseLoginForm(data=form_data)
        self.assertFalse(form.is_valid(), "Form should be invalid if password is empty.")
        self.assertIn("password", form.errors, "Errors should include 'password'.")