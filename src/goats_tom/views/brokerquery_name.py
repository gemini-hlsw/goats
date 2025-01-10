__all__ = ["update_brokerquery_name"]

from django.http import (
    HttpRequest,
    JsonResponse,
)
from rest_framework import status
from tom_alerts.models import BrokerQuery

from goats_tom.utils import build_json_response


def update_brokerquery_name(request: HttpRequest, pk: int) -> JsonResponse:
    """Update the name of a BrokerQuery object.

    Parameters
    ----------
    request : `HttpRequest`
        The incoming HTTP request.
    pk : `int`
        The ID of the BrokerQuery to be updated.

    Returns
    -------
    `JsonResponse`
        A JSON response indicating the status of the update operation. Returns
        a 200 status code if the update is successful. Returns an error message
        with a 404 status code if the query is not found, and with a 400 status
        code for any other invalid request.

    """
    if request.method == "POST":
        new_name = request.POST.get("name")

        try:
            query = BrokerQuery.objects.get(pk=pk)
            query.name = new_name
            # Need to update query_name to show in form.
            query.parameters["query_name"] = new_name
            query.save()
            return build_json_response()

        except BrokerQuery.DoesNotExist:
            return build_json_response("Query not found", status.HTTP_404_NOT_FOUND)

    return build_json_response("Invalid request", status.HTTP_400_BAD_REQUEST)
