"""Module that handles the DRAGONS run API."""

import datetime

import astrodata
from django.db.models import QuerySet
from django.http import HttpRequest
from recipe_system import cal_service
from rest_framework import mixins, permissions
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from tom_dataproducts.models import DataProduct

from goats_tom.models import (
    BaseRecipe,
    DRAGONSFile,
    DRAGONSRecipe,
    DRAGONSRun,
    RecipesModule,
)
from goats_tom.serializers import DRAGONSRunFilterSerializer, DRAGONSRunSerializer
from goats_tom.utils import get_recipes_and_primitives


class DRAGONSRunsViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    """A viewset that provides `create`, `retrieve`, `list`, and `delete` actions for a
    reduction run.
    """

    queryset = DRAGONSRun.objects.all()
    serializer_class = DRAGONSRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_serializer_class = DRAGONSRunFilterSerializer

    def get_queryset(self) -> QuerySet:
        """Retrieves the queryset filtered by different options.

        Returns
        -------
        QuerySet
            The filtered queryset.

        """
        queryset = super().get_queryset()

        # Run query parameters through the serializer.
        filter_serializer = self.filter_serializer_class(data=self.request.query_params)

        # Check if any filters provided.
        if filter_serializer.is_valid(raise_exception=False):
            observation_record_pk = filter_serializer.validated_data.get(
                "observation_record",
            )
            if observation_record_pk is not None:
                queryset = queryset.filter(observation_record__pk=observation_record_pk)

        return queryset

    def perform_create(self, serializer: DRAGONSRunSerializer) -> None:
        """Perform the creation of a `DRAGONSRun` instance using the provided
        serializer, initialize its directory, and link related DataProducts.

        Parameters
        ----------
        serializer : `DRAGONSRunSerializer`
            The serializer containing the validated data for creating a `DRAGONSRun`.

        """
        dragons_run = serializer.save()

        self._initialize(dragons_run)

    def _initialize(self, dragons_run: DRAGONSRun) -> None:
        """Initializes everything.

        This method sets up the output directory, creates a calibration manager
        database, and writes the configuration file necessary for the run. The
        directory structure and files created are essential for the operation of
        DRAGONS data processing.

        This method processes each data product linked to the run, using its tags and
        instrument data to fetch applicable recipes and create or update corresponding
        `DRAGONSRecipe` instances. If a file matches the conditions (unprepared and not
        processed or is a BPM file), it initializes recipes, updates the database, and
        creates a DRAGONSFile record.

        Parameters
        ----------
        dragons_run : `DRAGONSRun`
            The DRAGONS run instance for which recipes are being initialized.

        """
        # Create the output directory.
        output_dir = dragons_run.get_output_dir()
        output_dir.mkdir(parents=True)

        cal_manager_db_file = dragons_run.get_cal_manager_db_file()
        config_file = dragons_run.get_config_file()

        # Write the DRAGONS config file.
        with config_file.open("w") as f:
            f.write(f"[calibs]\ndatabases = \"{cal_manager_db_file}\" get store")

        # Create the calibration manager for DRAGONS.
        cal_db = cal_service.LocalDB(cal_manager_db_file, force_init=True)

        # TODO: Make this more intelligent.
        # Link DataProducts for the run to enable/disable.
        data_products = DataProduct.objects.filter(
            observation_record=dragons_run.observation_record,
        )

        for data_product in data_products:
            # Get the tags and instrument.
            ad = astrodata.open(data_product.data.path)
            tags = ad.tags
            # TODO: Should we store lowercase for instrument and observation_type?
            instrument = ad.instrument(generic=True)
            # TODO: Is there a better place for this?
            descriptors = ad.descriptors

            # Skip if file is prepared or processed, unless it's a BPM file.
            if "BPM" in tags:
                print("Adding BPM to calibration database.")
                cal_db.add_cal(data_product.data.path)
                continue
            if data_product.metadata.processed:
                print("Skipping prepared or processed file.")
                continue

            # Get the file type and the object name if applicable.
            observation_type = ad.observation_type()
            object_name = ad.object()
            observation_class = ad.observation_class()

            # if observation_type not in processed_base_recipe_observation_types:
            recipes_and_primitives = get_recipes_and_primitives(
                tags, instrument.lower()
            )

            # Create or update recipes in the database.
            for recipe_name, details in recipes_and_primitives["recipes"].items():
                recipes_module, _ = RecipesModule.objects.get_or_create(
                    name=details["recipes_module"],
                    instrument=instrument,
                    version=dragons_run.version,
                )

                # Create or fetch the base recipe.
                base_recipe, _ = BaseRecipe.objects.get_or_create(
                    name=recipe_name,
                    recipes_module=recipes_module,
                    defaults={"function_definition": details["function_definition"]},
                )

                DRAGONSRecipe.objects.get_or_create(
                    dragons_run=dragons_run,
                    recipe=base_recipe,
                    object_name=object_name,
                    observation_type=observation_type,
                    observation_class=observation_class,
                    defaults={
                        "is_default": details["is_default"],
                    },
                )

            # Build the astrodata descriptors to save.
            astrodata_descriptors = {}
            for descriptor in descriptors:
                if hasattr(ad, descriptor):
                    try:
                        value = getattr(ad, descriptor)()
                        # Check for unsupported types and convert them.
                        if isinstance(value, (datetime.date, datetime.datetime)):
                            # Convert datetime or date to ISO formatted string.
                            value = value.isoformat()
                        elif not isinstance(value, (str, int, float, bool, type(None))):
                            # Convert any other unsupported types to string.
                            value = str(value)
                        astrodata_descriptors[descriptor] = value
                    except Exception as e:
                        print(f"Error accessing descriptor {descriptor}: {str(e)}")

            # Create a file for this run using the recipes module last retrieved.
            DRAGONSFile.objects.create(
                dragons_run=dragons_run,
                data_product=data_product,
                recipes_module=recipes_module,
                observation_type=observation_type,
                object_name=object_name,
                observation_class=observation_class,
                astrodata_descriptors=astrodata_descriptors,
                product_id=data_product.get_file_name(),
                url=data_product.data.url,
            )

    def retrieve(self, request: HttpRequest, *args, **kwargs) -> Response:
        """Retrieve a DRAGONS run instance along with optional included data based on
        query parameters.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request object, containing query parameters.

        Returns
        -------
        `Response`
            Contains serialized DRAGONS run data with optional information.

        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Validate the query parameters.
        filter_serializer = self.filter_serializer_class(data=request.query_params)
        # If valid, attach the additional information.
        if filter_serializer.is_valid(raise_exception=False):
            include = filter_serializer.validated_data.get("include", [])

            if "groups" in include:
                data["groups"] = instance.list_groups()

        return Response(data)
