import pytest
from gpp_client.generated import enums
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPEnumsViewSet
from goats_tom.tests.factories import UserFactory


@pytest.mark.django_db
class TestGPPEnumsViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.list_view = GPPEnumsViewSet.as_view({"get": "list"})
        self.url = "/api/gpp/enums/"
        self.user = UserFactory()

    def test_list_returns_the_schema_values(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["imageQuality"] == [
            e.value for e in enums.ImageQualityPreset
        ]
        assert response.data["band"] == [e.value for e in enums.Band]
        assert "THREE_POINT_ZERO" not in response.data["imageQuality"]

    def test_list_needs_no_gpp_credentials(self):
        """The values come from the schema, so no GPP call is made."""
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK

    def test_list_requires_authentication(self):
        response = self.list_view(self.factory.get(self.url))

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
