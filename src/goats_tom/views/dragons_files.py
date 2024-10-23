"""Module that handles the DRAGONS files API."""

from django.db.models import QuerySet
from django.db.models.fields.json import KeyTransform
from django.http import HttpRequest
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from goats_tom.filters import AstrodataFilter
from goats_tom.models import DRAGONSFile
from goats_tom.serializers import (
    DRAGONSFileFilterSerializer,
    DRAGONSFileSerializer,
)
from goats_tom.utils import get_astrodata_header


class DRAGONSFilesViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """A viewset that provides `retrieve`, `list`, and `update` actions for
    DRAGONS files.
    """

    serializer_class = DRAGONSFileSerializer
    filter_serializer_class = DRAGONSFileFilterSerializer
    permission_classes = [IsAuthenticated]
    queryset = DRAGONSFile.objects.all()

    def get_queryset(self) -> QuerySet:
        """Retrieves the queryset filtered by the associated DRAGONS run.

        Returns
        -------
        `QuerySet`
            The filtered queryset.

        """
        queryset = super().get_queryset()

        # run query parameters through the serializer.
        filter_serializer = self.filter_serializer_class(data=self.request.query_params)

        # Check if any filters provided.
        filter_serializer.is_valid(raise_exception=True)

        dragons_run_pk = filter_serializer.validated_data.get("dragons_run")

        if dragons_run_pk is not None:
            queryset = queryset.filter(dragons_run__pk=dragons_run_pk)

        # Apply select_related to optimize related object retrieval.
        queryset = queryset.select_related(
            "data_product__observation_record",
        )

        return queryset

    def list(self, request: HttpRequest, *args, **kwargs) -> Response:
        """List or group DRAGONS file records based on the provided query parameters.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request object, containing query parameters.

        Returns
        -------
        `Response`
            The paginated list of DRAGONS file records, optionally grouped by file type.

        """
        # Validates the provided query parameters.
        filter_serializer = self.filter_serializer_class(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        # Extract validated data.
        group_by = filter_serializer.validated_data.get("group_by", [])
        filter_expression = filter_serializer.validated_data.get(
            "filter_expression", ""
        )
        filter_strict = filter_serializer.validated_data.get("filter_strict", False)

        astrodata_filter = AstrodataFilter(strict=filter_strict)
        query_filter = astrodata_filter.parse_expression_to_query(filter_expression)

        # Gets the query.
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(query_filter)

        # Group by dynamic fields if specified

        if group_by:
            queryset = queryset.annotate(
                **{
                    f"group_{i}": KeyTransform(key, "astrodata_descriptors")
                    for i, key in enumerate(group_by)
                }
            ).values(
                "id",
                "object_name",
                "observation_type",
                "observation_class",
                "product_id",
                "url",
                *[f"group_{i}" for i in range(len(group_by))],
            )

            grouped_data = {}
            for item in queryset:
                # Dynamic nested grouping using nested dictionaries
                pointer = grouped_data
                for i, key in enumerate(group_by):
                    group_key = f"group_{i}"
                    if key not in pointer:
                        pointer[key] = {}
                    if item[group_key] not in pointer[key]:
                        pointer[key][item[group_key]] = (
                            {} if i < len(group_by) - 1 else []
                        )
                    pointer = pointer[key][item[group_key]]

                # Append file info at the deepest level
                pointer.append(
                    {
                        "file_id": item["id"],
                        "file_name": item["product_id"],
                        "url": item["url"],
                        "object_name": item["object_name"],
                        "observation_type": item["observation_type"],
                        "observation_class": item["observation_class"],
                    }
                )
            return Response(grouped_data)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # No grouping specified; serialize and return all records.
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request: HttpRequest, *args, **kwargs) -> Response:
        """Retrieve a DRAGONS file instance along with optional included data based on
        query parameters.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request object, containing query parameters.

        Returns
        -------
        `Response`
            Contains serialized DRAGONS file data with optional information.

        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Validate the query parameters.
        filter_serializer = self.filter_serializer_class(data=request.query_params)
        # If valid, attach the additional information.
        if filter_serializer.is_valid(raise_exception=False):
            include = filter_serializer.validated_data.get("include", [])

            if "header" in include:
                header = get_astrodata_header(instance.data_product)
                data["header"] = header

            if "groups" in include:
                data["groups"] = instance.list_groups()

        return Response(data)
