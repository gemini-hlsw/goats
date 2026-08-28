"""Module to handle all data needed after a run is selected."""

__all__ = ["DRAGONSDataViewSet"]

from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from goats_tom.scoping import ScopedQuerySetMixin
from goats_tom.models import DRAGONSFile, DRAGONSRecipe, DRAGONSRun
from goats_tom.serializers import (
    DRAGONSFileSerializer,
    DRAGONSRecipeSerializer,
    DRAGONSRunSerializer,
)


class DRAGONSDataViewSet(ScopedQuerySetMixin, mixins.RetrieveModelMixin, GenericViewSet):
    # Scoped by the data products being reduced, not by the target.
    # Observation records are shared with collaborators on a target so
    # everyone can see what was triggered; the files stay private to
    # whoever triggered them, and a reduction belongs with its files.
    # See `goats_tom.scoping`.
    dataproduct_path = "observation_record__dataproduct"
    queryset = DRAGONSRun.objects.all()
    serializer_class = DRAGONSRunSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a `DRAGONSRun` instance along with grouped data of related recipes
        and files.

        Parameters
        ----------
        request : `HttpRequest`
            The request object containing any additional parameters.

        Returns
        -------
        `Response`
            The response object containing grouped recipes and files.
        """
        data = {}

        instance = self.get_object()
        # Get the groups that users can group by.
        data["groups"] = instance.list_groups()

        # Fetching recipes and files and serializing them.
        recipes = DRAGONSRecipe.objects.filter(dragons_run=instance).select_related(
            "recipe"
        )
        files = DRAGONSFile.objects.filter(dragons_run=instance).select_related(
            "data_product"
        )

        recipes_data = DRAGONSRecipeSerializer(recipes, many=True).data
        files_data = DRAGONSFileSerializer(files, many=True).data

        # Combining and grouping recipe and file data by observation type, class, and
        # object.
        recipes_and_files_data = {"observation_type": {}}
        all_data = recipes_data + files_data
        for item in all_data:
            obs_type = item["observation_type"]
            obs_class = item["observation_class"]
            obj_name = item["object_name"]
            entry_type = "recipes" if "recipes_module_name" in item else "files"

            if obs_type not in recipes_and_files_data["observation_type"]:
                recipes_and_files_data["observation_type"][obs_type] = {}
            if obs_class not in recipes_and_files_data["observation_type"][obs_type]:
                recipes_and_files_data["observation_type"][obs_type][obs_class] = {}
            if (
                obj_name
                not in recipes_and_files_data["observation_type"][obs_type][obs_class]
            ):
                recipes_and_files_data["observation_type"][obs_type][obs_class][
                    obj_name
                ] = {"recipes": [], "files": {"All": {"count": 0, "files": []}}}

            if entry_type == "files":
                # Append the file and update the count.
                recipes_and_files_data["observation_type"][obs_type][obs_class][
                    obj_name
                ]["files"]["All"]["files"].append(item)
                recipes_and_files_data["observation_type"][obs_type][obs_class][
                    obj_name
                ]["files"]["All"]["count"] += 1
            else:
                # Append the recipe.
                recipes_and_files_data["observation_type"][obs_type][obs_class][
                    obj_name
                ][entry_type].append(item)

        data["recipes_and_files"] = recipes_and_files_data
        return Response(data)
