"""Module that handles the DRAGONS files API."""

from django.db.models import CharField, F, QuerySet, Value
from django.db.models.fields.json import KeyTransform
from django.db.models.functions import Concat
from django.http import HttpRequest
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from goats_tom.scoping import ScopedQuerySetMixin
from goats_tom.filters import AstrodataFilter
from goats_tom.models import DRAGONSFile
from goats_tom.serializers import (
    DRAGONSFileFilterSerializer,
    DRAGONSFileSerializer,
)


class DRAGONSFilesViewSet(
    ScopedQuerySetMixin,
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
    # Scoped by the data products being reduced, not by the target.
    # Observation records are shared with collaborators on a target so
    # everyone can see what was triggered; the files stay private to
    # whoever triggered them, and a reduction belongs with its files.
    # See `goats_tom.scoping`.
    dataproduct_path = "data_product"
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
        query_filter = AstrodataFilter.parse(filter_expression, strict=filter_strict)
        if query_filter is None:
            return Response({"Invalid Filter": {"count": 0, "files": []}})
        # Gets the query.
        try:
            queryset = self.filter_queryset(self.get_queryset())
            queryset = queryset.filter(query_filter)
        except Exception:
            return Response({"Invalid Filter": {"count": 0, "files": []}})

        # Group by dynamic fields if specified.
        if group_by:
            if "all" in group_by:
                # Return all files under the "All" key with a count
                files_data = list(
                    queryset.values(
                        "id",
                        "product_id",
                        "url",
                        "observation_type",
                        "object_name",
                        "observation_class",
                    )
                )
                grouped_data = {"All": {"count": len(files_data), "files": files_data}}
                return Response(grouped_data)

            annotations = {
                f"group_value_{i}": KeyTransform(key, "astrodata_descriptors")
                for i, key in enumerate(group_by)
            }
            queryset = queryset.annotate(**annotations)

            concat_args = []
            for i, _ in enumerate(group_by):
                if i > 0:
                    concat_args.append(Value(" | "))
                concat_args.append(F(f"group_value_{i}"))

            if len(concat_args) > 1:
                queryset = queryset.annotate(
                    composite_group_value=Concat(*concat_args, output_field=CharField())
                )
                group_field = "composite_group_value"
            else:
                group_field = "group_value_0"

            # Fetch and group data based on the composite or single group key.
            queryset = queryset.values(
                "id",
                "object_name",
                "observation_type",
                "observation_class",
                "product_id",
                "url",
                group_field,
            ).order_by(group_field)

            # Manually aggregate grouped data.
            grouped_data = {}
            for item in queryset:
                group_key = item[group_field]
                if group_key not in grouped_data:
                    grouped_data[group_key] = {
                        "count": 0,  # Initialize count
                        "files": [],
                    }
                grouped_data[group_key]["files"].append(
                    {
                        "id": item["id"],
                        "product_id": item["product_id"],
                        "url": item["url"],
                        "object_name": item["object_name"],
                        "observation_type": item["observation_type"],
                        "observation_class": item["observation_class"],
                    }
                )
                grouped_data[group_key]["count"] += 1

            # Ensure response consistency by checking if grouped_data is empty.
            if not grouped_data:
                grouped_data = {"N/A": {"count": 0, "files": []}}

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

            if "astrodata_descriptors" in include:
                data["astrodata_descriptors"] = instance.astrodata_descriptors

            if "groups" in include:
                data["groups"] = instance.list_groups()

        return Response(data)
