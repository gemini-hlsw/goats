import ast

from django.db.models import Q
from django.test import TestCase

from goats_tom.filters._q_expression_transformer import _QExpressionTransformer


class TestQExpressionTransformer(TestCase):

    def setUp(self):
        # Initialize the transformer with the strict mode turned off for partial matches
        self.transformer = _QExpressionTransformer(strict=False)

    def test_simple_equality(self):
        # Test simple equality conversion
        expression = "name == 'Hubble'"
        node = ast.parse(expression, mode='eval').body
        q_object = self.transformer.visit(node)
        self.assertEqual(q_object, Q(astrodata_descriptors__name__exact='Hubble'))

    def test_not_equals(self):
        # Test not equals conversion
        expression = "instrument != 'ACS'"
        node = ast.parse(expression, mode='eval').body
        q_object = self.transformer.visit(node)
        self.assertEqual(q_object, ~Q(astrodata_descriptors__instrument__exact='ACS'))

    def test_less_than(self):
        # Test less than conversion
        expression = "exposure_time < 0.5"
        node = ast.parse(expression, mode='eval').body
        q_object = self.transformer.visit(node)
        self.assertEqual(q_object, Q(astrodata_descriptors__exposure_time__lt=0.5))

    def test_boolean_and(self):
        # Test AND operation
        expression = "name == 'Hubble' and year >= 1990"
        node = ast.parse(expression, mode='eval').body
        q_object = self.transformer.visit(node)
        expected = Q(astrodata_descriptors__name__exact='Hubble') & Q(astrodata_descriptors__year__gte=1990)
        self.assertEqual(q_object, expected)

    def test_boolean_or(self):
        # Test OR operation
        expression = "name == 'Hubble' or name == 'James Webb'"
        node = ast.parse(expression, mode='eval').body
        q_object = self.transformer.visit(node)
        expected = Q(astrodata_descriptors__name__exact='Hubble') | Q(astrodata_descriptors__name__exact='James Webb')
        self.assertEqual(q_object, expected)

    def test_datetime_parsing(self):
        # Test datetime string parsing
        self.transformer.current_field = 'ut_datetime'
        result = self.transformer._parse_datetime_string("2021-10-01 12:00:00")
        self.assertEqual(result, "2021-10-01T12:00:00")

    def test_numeric_tolerance(self):
        # Set the current field to test
        self.transformer.current_field = 'central_wavelength'
        value = 656.3  # Wavelength in nm

        # Generate the Q object from the transformer
        q_object = self.transformer._handle_numeric_tolerance(value)

        # Check for the presence of expected keys
        self.assertIn('astrodata_descriptors__central_wavelength__gte', q_object.children[0])
        self.assertIn('astrodata_descriptors__central_wavelength__lte', q_object.children[1])

    def test_datetime_formats(self):
        datetime_formats = {
            "ut_time": "23:59:59",
            "local_time": "15:59:59.123",
            "ut_date": "2021-10-01",
            "ut_datetime": "2021-10-01 12:00:00.123456"
        }
        for field, value in datetime_formats.items():
            with self.subTest(field=field, value=value):
                self.transformer.current_field = field
                result = self.transformer._parse_datetime_string(value)
                self.assertIsInstance(result, str)

    def test_partial_matching(self):
        partial_descriptors = {
            "filter_name": "test",
            "detector_name": "CCD1",
            "disperser": "Grism"
        }
        for field, value in partial_descriptors.items():
            with self.subTest(field=field, value=value):
                self.transformer.current_field = field
                expression = f"{field} == '{value}'"
                node = ast.parse(expression, mode='eval').body
                q_object = self.transformer.visit(node)
                self.assertIsInstance(q_object, Q)
                self.assertIn('__icontains', q_object.children[0][0])

    def test_incorrect_datetime_format(self):
        self.transformer.current_field = 'ut_datetime'
        value = "10/01/2021 12:00:00"  # Incorrect format
        with self.assertRaises(ValueError):
            self.transformer._parse_datetime_string(value)

    def test_strict_mode(self):
        self.transformer.strict = True
        partial_descriptors = {
            "filter_name": "broad",
            "detector_name": "CCD1",
            "disperser": "Grism"
        }
        for field, value in partial_descriptors.items():
            with self.subTest(field=field, value=value):
                self.transformer.current_field = field
                expression = f"{field} == '{value}'"
                node = ast.parse(expression, mode='eval').body
                q_object = self.transformer.visit(node)
                self.assertIsInstance(q_object, Q)
                self.assertIn('__exact', q_object.children[0][0])

    # Test unsupported operation error handling
    def test_unsupported_operation(self):
        expression = "[1, 2, 3]"
        with self.assertRaises(Exception) as context:
            node = ast.parse(expression, mode='eval').body
            self.transformer.visit(node)
        self.assertIn("Unsupported operation", str(context.exception))

    def test_strict_mode_numeric_exact_match(self):
        # Enable strict mode
        self.transformer.strict = True

        # Numeric fields to test for exact matches
        numeric_descriptors = {
            "central_wavelength": 500.7,
            "exposure_time": 5.0
        }
        for field, value in numeric_descriptors.items():
            with self.subTest(field=field, value=value):
                self.transformer.current_field = field
                expression = f"{field} == {value}"
                node = ast.parse(expression, mode='eval').body

                # Generate Q object and verify
                q_object = self.transformer.visit(node)

                # Check that the Q object contains only one child with the correct condition
                self.assertEqual(len(q_object.children), 1, "Q object should contain exactly one condition")
                condition_key, condition_value = q_object.children[0]
                expected_key = f"astrodata_descriptors__{field}__exact"

                # Verify the key and the exact value
                self.assertEqual(condition_key, expected_key)
                self.assertEqual(condition_value, value, f"Expected {expected_key} with value {value} not found in Q object")
