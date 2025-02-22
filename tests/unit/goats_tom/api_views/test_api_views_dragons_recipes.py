"""Test module for DRAGONS recipes."""

from django.urls import reverse
from goats_tom.tests.factories import (
    BaseRecipeFactory,
    DRAGONSRecipeFactory,
    DRAGONSRunFactory,
    UserFactory,
)
from goats_tom.api_views import DRAGONSRecipesViewSet
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate


class TestDRAGONSRecipesViewSet(APITestCase):
    """Class to test the `DRAGONSRecipe` API view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = UserFactory()
        self.list_view = DRAGONSRecipesViewSet.as_view({"get": "list"})
        self.detail_view = DRAGONSRecipesViewSet.as_view({"get": "retrieve"})
        self.partial_update_view = DRAGONSRecipesViewSet.as_view(
            {"patch": "partial_update"},
        )

    def authenticate(self, request):
        """Helper method to authenticate requests."""
        force_authenticate(request, user=self.user)

    def test_list_recipes(self):
        """Test listing all DRAGONS recipes."""
        DRAGONSRecipeFactory.create_batch(3)

        request = self.factory.get(reverse("dragonsrecipes-list"))
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 3

    def test_retrieve_recipe(self):
        """Test retrieving a single DRAGONS recipe."""
        dragons_recipe = DRAGONSRecipeFactory()

        request = self.factory.get(
            reverse("dragonsrecipes-detail", args=[dragons_recipe.id]),
        )
        self.authenticate(request)

        response = self.detail_view(request, pk=dragons_recipe.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["observation_type"] == dragons_recipe.observation_type

    def test_update_recipe(self):
        """Test updating a DRAGONS recipe."""
        dragons_recipe = DRAGONSRecipeFactory()
        new_function_definition = "Updated function definition"
        request = self.factory.patch(
            reverse("dragonsrecipes-detail", args=[dragons_recipe.id]),
            {"function_definition": new_function_definition},
        )
        self.authenticate(request)

        response = self.partial_update_view(request, pk=dragons_recipe.id)

        assert response.status_code == status.HTTP_200_OK
        dragons_recipe.refresh_from_db()
        assert (
            dragons_recipe.function_definition == new_function_definition
        ), "The function definition should be updated."

        # Test resetting the function definition.
        request = self.factory.patch(
            reverse("dragonsrecipes-detail", args=[dragons_recipe.id]),
            {"function_definition": None},
        )
        self.authenticate(request)

        response = self.partial_update_view(request, pk=dragons_recipe.id)

        assert response.status_code == status.HTTP_200_OK
        dragons_recipe.refresh_from_db()
        assert (
            dragons_recipe.active_function_definition
            == dragons_recipe.recipe.function_definition
        ), "The function definition should be reset."

    def test_filter_by_dragons_run(self):
        """Test filtering DRAGONS recipes by DRAGONS run."""
        dragons_run = DRAGONSRunFactory()
        DRAGONSRecipeFactory.create_batch(2, dragons_run=dragons_run)
        DRAGONSRecipeFactory.create_batch(3)

        request = self.factory.get(
            reverse("dragonsrecipes-list"), {"dragons_run": dragons_run.pk},
        )
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 2


    def test_authentication_required(self):
        """Test that authentication is required to access the view."""
        request = self.factory.get(reverse("dragonsrecipes-list"))

        response = self.list_view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
