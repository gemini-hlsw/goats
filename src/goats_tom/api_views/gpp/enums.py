"""Serves the GPP enumerations the observation form offers as choices."""

__all__ = ["GPPEnumsViewSet"]

import logging
from enum import Enum

from gpp_client.generated import enums
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

logger = logging.getLogger(__name__)

# What the observation form offers, keyed by the name its fields ask for. The
# values are generated from the GPP schema, so a preset added or dropped there
# reaches the form without anybody editing a list by hand. The labels stay in
# GOATS: the schema describes `POINT_ONE` as "ImageQualityPreset PointOne",
# which is no use to an observer.
FORM_ENUMS: dict[str, type[Enum]] = {
    "imageQuality": enums.ImageQualityPreset,
    "cloudExtinction": enums.CloudExtinctionPreset,
    "skyBackground": enums.SkyBackground,
    "waterVapor": enums.WaterVapor,
    "posAngleConstraintMode": enums.PosAngleConstraintMode,
    "workflowState": enums.ObservationWorkflowState,
    "band": enums.Band,
    "brightnessUnits": enums.BrightnessIntegratedUnits,
    "gmosNorthFpu": enums.GmosNorthBuiltinFpu,
    "gmosSouthFpu": enums.GmosSouthBuiltinFpu,
    "gmosNorthFilter": enums.GmosNorthFilter,
    "gmosSouthFilter": enums.GmosSouthFilter,
    "gmosNorthGrating": enums.GmosNorthGrating,
    "gmosSouthGrating": enums.GmosSouthGrating,
    "gmosRoi": enums.GmosRoi,
    "gmosBinning": enums.GmosBinning,
    "gmosAmpReadMode": enums.GmosAmpReadMode,
}


class GPPEnumsViewSet(GenericViewSet, mixins.ListModelMixin):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return the values each form choice accepts.

        Parameters
        ----------
        request : Request
            The HTTP request object.

        Returns
        -------
        Response
            A DRF Response mapping each choice to its accepted values.
        """
        return Response(
            {name: [e.value for e in en] for name, en in FORM_ENUMS.items()}
        )
