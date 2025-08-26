__all__ = ["TargetViewSet"]

from typing import Optional

from astropy import units as u
from astropy.coordinates import SkyCoord
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from tom_targets.api_views import TargetViewSet as BaseTargetViewSet
from tom_targets.models import Target

from goats_tom.astroquery import Observations as GOA


class TargetViewSet(BaseTargetViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="observations-in-radius")
    def observations_in_radius(
        self, request: Request, pk: Optional[str] = None
    ) -> Response:
        """
        Return all unique observation IDs from GOA within 15 arcseconds of a given
        target.

        Parameters
        ----------
        request : Request
            The incoming HTTP GET request.
        pk : str, optional
            The primary key of the target.

        Returns
        -------
        Response
            A JSON response with a list of unique `observation_ids` found within the
            radius.
        """
        # Ensure the user has GOA credentials set.
        if not hasattr(request.user, "goalogin"):
            return Response(
                {"detail": "GOA login credentials are not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the target object.
        try:
            target = self.get_object()
        except Target.DoesNotExist:
            return Response(
                {"detail": "Target not found."}, status=status.HTTP_404_NOT_FOUND
            )

        credentials = request.user.goalogin
        GOA.login(credentials.username, credentials.password)

        # Check if credentials are valid for this user.
        if not GOA.authenticated():
            return Response(
                {"detail": "GOA login credentials are not valid for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Grab the unique observations.
        radius = 15.0 * u.arcsec
        coordinates = SkyCoord(ra=target.ra * u.deg, dec=target.dec * u.deg)
        try:
            table = GOA.query_raw("science", coordinates=coordinates, radius=radius)
        except Exception as e:
            return Response(
                {"detail": f"Error during GOA query: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if table is None or len(table) == 0 or "observation_id" not in table.colnames:
            return Response(
                {"observation_ids": []},
                status=status.HTTP_200_OK,
            )
        observation_ids = sorted(
            {oid for oid in table["observation_id"] if oid is not None}
        )

        return Response({"observation_ids": observation_ids}, status=status.HTTP_200_OK)
