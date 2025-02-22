"""Handles adding a file to Astro Datalab"""

__all__ = ["AstroDatalabViewSet"]

from django.contrib.auth.models import User
from django.http import HttpRequest
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins
from tom_dataproducts.models import DataProduct

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

        Raises
        ------
        ValueError
            Raised if authentication fails or an error occurs during file upload.
        """
        # Lazy import to avoid creating .datalab dir collision.
        from dl import authClient as ac
        from dl import storeClient as sc

        astro_datalab_login = user.astrodatalablogin
        token = ac.login(astro_datalab_login.username, astro_datalab_login.password)
        if not ac.isValidToken(token):
            raise ValueError("Astro Datalab credentials are not valid.")
        try:
            # Create the directory, better to try then check and try as less API calls.
            sc.mkdir(token, ASTRO_DATALAB_DIR)
            # Put the file on Astro Datalab.
            sc.put(token, to=ASTRO_DATALAB_DIR, fr=data_product.data.path)
        finally:
            try:
                ac.logout(token)
            except Exception:
                pass
