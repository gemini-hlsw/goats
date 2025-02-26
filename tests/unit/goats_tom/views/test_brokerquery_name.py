from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpRequest, JsonResponse
from goats_tom.views import (
    update_brokerquery_name
)
from rest_framework import status
from tom_alerts.models import BrokerQuery


@pytest.fixture()
def mock_request():
    return HttpRequest()

@pytest.mark.django_db()
class TestUpdateBrokerQueryName:
    @patch("goats_tom.views.brokerquery_name.BrokerQuery")
    def test_update_brokerquery_name_success(self, mock_brokerquery, mock_request):
        # Mock the BrokerQuery object and its methods.
        mock_query = MagicMock()
        mock_query.parameters = {"query_name": "Old Query Name"}
        mock_query.name = "Old Query Name"

        mock_brokerquery.objects.get.return_value = mock_query

        # Mock request.
        mock_request.method = "POST"
        mock_request.POST = {"name": "New Query Name"}

        # Call the view.
        response = update_brokerquery_name(mock_request, pk=1)

        # Assertions.
        mock_brokerquery.objects.get.assert_called_with(pk=1)
        assert mock_query.name == "New Query Name"
        assert mock_query.parameters["query_name"] == "New Query Name"
        mock_query.save.assert_called_once()

        assert isinstance(response, JsonResponse)

    @patch("goats_tom.views.brokerquery_name.BrokerQuery")
    def test_update_brokerquery_name_not_found(self, mock_brokerquery, mock_request):
        mock_brokerquery.DoesNotExist = BrokerQuery.DoesNotExist
        mock_brokerquery.objects.get.side_effect = mock_brokerquery.DoesNotExist

        # Mock request.
        mock_request.method = "POST"
        mock_request.POST = {"name": "New Query Name"}

        # Call the view.
        response = update_brokerquery_name(mock_request, pk=1)

        # Assertions.
        mock_brokerquery.objects.get.assert_called_with(pk=1)
        assert isinstance(response, JsonResponse), "Response should be a JsonResponse"
        assert response.status_code == 404, "Response status code should be 404"

    def test_update_brokerquery_name_invalid_method(self, mock_request):
        # Mock request.
        mock_request.method = "GET"

        # Call the view.
        response = update_brokerquery_name(mock_request, pk=1)

        # Assertions.
        assert isinstance(response, JsonResponse)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
