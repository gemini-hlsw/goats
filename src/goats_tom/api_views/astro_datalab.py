"""Handles adding a file to Astro Datalab"""

__all__ = ["AstroDatalabViewSet"]

from django.contrib.auth.models import User
from django.http import HttpRequest
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins
from tom_dataproducts.models import DataProduct

from goats_tom.astro_data_lab import AstroDataLabClient
from goats_tom.serializers import AstroDatalabSerializer

ASTRO_DATALAB_DIR = "vos://goats_data"


class AstroDatalabViewSet(GenericViewSet, mixins.CreateModelMixin):
    serializer_class = AstroDatalabSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = None

    def create(self, request: HttpRequest, *args, **kwargs) -> Response:
        """Handle the request to upload a file to Astro Data Lab.

        This method validates the provided `data_product` and triggers the upload
        process.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request containing the `data_product` ID to be uploaded.

        Returns
        -------
        `Response`
            - 201: If the file was successfully uploaded.
            - 400: If an error occurred during the upload process.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data_product = serializer.validated_data["data_product"]

        try:
            self.send_to_astro_datalab(request.user, data_product)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": f"File {data_product.data.name} successfully sent to "
                f"'{ASTRO_DATALAB_DIR}' on Astro Datalab.",
                "data_product": data_product.id,
            },
            status.HTTP_201_CREATED,
        )

    def send_to_astro_datalab(self, user: User, data_product: DataProduct) -> None:
        """Handles authentication and file upload to Astro Data Lab.

        Parameters
        ----------
        user : `User`
            The authenticated user making the request.
        data_product : `DataProduct`
            The data product to be uploaded.
        """
        credentials = user.astrodatalablogin

        with AstroDataLabClient(
            username=credentials.username, password=credentials.password
        ) as client:
            client.login()
            if not client.is_logged_in():
                raise ValueError("Credentials/token are not valid.")

            try:
                # Create the directory, ignore issue if the directory already exists.
                client.mkdir()
            except FileExistsError:
                pass

            client.upload_file(data_product.data.path, overwrite=True)
