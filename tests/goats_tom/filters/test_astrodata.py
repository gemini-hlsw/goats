from django.db.models import Q
from django.test import TestCase

from goats_tom.filters.astrodata import AstrodataFilter


class TestAstrodataFilter(TestCase):

    def test_empty_expression(self):
        """Test that an empty expression returns a Q object that matches everything."""
        q_object = AstrodataFilter.parse('')
        self.assertIsInstance(q_object, Q)
        self.assertEqual(str(q_object), str(Q()))

    def test_valid_expression(self):
        """Test parsing of a valid expression."""
        expression = "object == 'Hubble'"
        q_object = AstrodataFilter.parse(expression)
        self.assertIsInstance(q_object, Q)
        # Expecting that name == 'Hubble' translates into a Django Q object with __exact
        self.assertIn("astrodata_descriptors__object__exact", str(q_object))
        self.assertIn("'Hubble'", str(q_object))

    def test_invalid_expression(self):
        """Test that an invalid syntax returns None."""
        expression = "name = 'Hubble'"  # Invalid because it uses '=' instead of '=='
        q_object = AstrodataFilter.parse(expression)
        self.assertIsNone(q_object)

    def test_strict_mode_true(self):
        """Test that strict mode being true affects the output Q object."""
        expression = "exposure_time == 10"
        # Assuming strict mode enforces an exact match without tolerances
        q_object = AstrodataFilter.parse(expression, strict=True)
        self.assertIn("__exact", str(q_object))

    def test_complex_expression(self):
        """Test complex expressions combining multiple conditions."""
        expression = "name == 'Hubble' and (exposure_time > 5 or exposure_time < 15)"
        q_object = AstrodataFilter.parse(expression)
        self.assertIsInstance(q_object, Q)
        # This assertion checks for the presence of AND and OR in the Q object output
        self.assertIn("AND", str(q_object))
        self.assertIn("OR", str(q_object))

    def test_syntax_error_handled(self):
        """Test that a syntax error in the expression leads to None being returned."""
        expression = "This is not a valid expression"
        q_object = AstrodataFilter.parse(expression)
        self.assertIsNone(q_object)

    def test_inequality_expression(self):
        """Test that an inequality expression wraps the __exact with the inverse."""
        expression = "name != 'Hubble'"
        q_object = AstrodataFilter.parse(expression)
        self.assertIsInstance(q_object, Q)
        # We expect a NOT on the exact match for 'Hubble'
        self.assertIn("NOT", str(q_object))
        self.assertIn("astrodata_descriptors__name__exact", str(q_object))

    def test_numeric_tolerance_included(self):
        """Test that tolerances are included when strict mode is false."""
        expression = "central_wavelength == 500.7"
        q_object = AstrodataFilter.parse(expression, strict=False)
        self.assertIsInstance(q_object, Q)
        # Check for greater than or equal and less than or equal conditions
        self.assertIn("astrodata_descriptors__central_wavelength__gte", str(q_object))
        self.assertIn("astrodata_descriptors__central_wavelength__lte", str(q_object))

    def test_partial_string_matching(self):
        """Test that __icontains is used for string comparison when strict mode is false."""
        expression = "filter_name == 'Broad'"
        q_object = AstrodataFilter.parse(expression, strict=False)
        self.assertIsInstance(q_object, Q)
        # Check for icontains used in the Q object, which allows partial matching
        self.assertIn("astrodata_descriptors__filter_name__icontains", str(q_object))
