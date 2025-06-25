import pytest
from django.db.utils import IntegrityError
from django.test import TestCase

from goats_tom.tests.factories import RecipesModuleFactory


@pytest.mark.django_db
class RecipesModuleTests(TestCase):
    def test_create_recipes_module(self):
        """Ensure that the RecipesModule can be created with valid attributes using the
        factory.

        """
        module = RecipesModuleFactory()
        self.assertIsNotNone(
            module.pk,
            "Failed to save the RecipesModule instance to the database."
        )

    def test_unique_constraints(self):
        """Verify that the unique constraints on `name`, `version`, and `instrument`
        are enforced by the database.

        """
        # Create an initial module with specific details.
        module1 = RecipesModuleFactory(name="Astro", version="1.0.0",
                                       instrument="Telescope")
        module1.save()

        # Attempt to create another module with the same details.
        module2 = RecipesModuleFactory.build(
            name="Astro", version="1.0.0", instrument="Telescope")
        with self.assertRaises(
            IntegrityError,
            msg="Database failed to enforce uniqueness."):
            module2.save()
