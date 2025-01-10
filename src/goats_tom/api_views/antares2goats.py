"""View set to handle adding items from the browser extension."""

__all__ = ["Antares2GoatsViewSet"]

from datetime import datetime

from django.db import IntegrityError
from rest_framework import mixins, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from tom_alerts.alerts import get_service_class as tom_alerts_get_service_class
from tom_alerts.models import BrokerQuery

from goats_tom.serializers import Antares2GoatsSerializer


class Antares2GoatsViewSet(GenericViewSet, mixins.CreateModelMixin):
    # FIXME: Hack until tomtoolkit merges in PR.
    queryset = BrokerQuery.objects.none()

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = Antares2GoatsSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a target or query based on the provided data.

        Parameters
        ----------`
        request : Request`
            The request object containing data for creating a target or query.

        Returns
        -------
        `Response`
            The HTTP response with the creation result.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Try to create target or query and handle errors.
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except IntegrityError:
            return Response(
                {"detail": "Target already exists, cannot create."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            return Response({"detail": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer: Antares2GoatsSerializer) -> None:
        """Performs the creation of a target or query.

        This method fetches data using ANTARES service and creates a new `Target` or
        creates a new `BrokerQuery` depending on the validated data from the serializer.

        Parameters
        ----------
        serializer : `Antares2GoatsSerializer`
            The serializer containing validated data.
        """
        if "locusid" in serializer.validated_data:
            # Get the class responsible for handling ANTARES broker service.
            broker_class = tom_alerts_get_service_class("ANTARES")()
            # Fetch alert based on the parsed query.
            alert = list(broker_class.fetch_alerts(serializer.validated_data))[0]
            # Convert the generic alert into target format.
            generic_alert = broker_class.to_generic_alert(alert)
            target, extras, aliases = generic_alert.to_target()
            target.save(extras=extras, names=aliases)

        elif "esquery" in serializer.validated_data:
            query = serializer.validated_data["esquery"]
            query_name = f"esquery_ANTARES_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            # Create a new query.
            broker_query = BrokerQuery.objects.create(
                name=query_name,
                broker="ANTARES",
                parameters={"query": query, "query_name": query_name},
            )
            # Save the new BrokerQuery instance to the database.
            broker_query.save()
