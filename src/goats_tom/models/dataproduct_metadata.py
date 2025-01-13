__all__ = ["DataProductMetadata"]

from django.db import models
from tom_dataproducts.models import DataProduct


class DataProductMetadata(models.Model):
    dataproduct = models.OneToOneField(
        DataProduct, on_delete=models.CASCADE, related_name="metadata"
    )
    processed = models.BooleanField(default=False)
