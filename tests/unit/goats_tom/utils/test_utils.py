import os
import unittest
from unittest.mock import Mock

import pytest
from astropy.table import Table
from django.test import TestCase
from goats_tom.tests.factories import (
    DataProductFactory,
    ReducedDatumFactory,
)
from goats_tom.utils import (
    build_json_response,
    create_name_reduction_map,
    custom_data_product_path,
    delete_associated_data_products,
)
from rest_framework import status
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


class DeleteAssociatedDataProductsTest(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
        )
        self.data_products = DataProductFactory.create_batch(
            3, observation_record=self.observation_record,
        )
        for data_product in self.data_products:
            ReducedDatumFactory.create(data_product=data_product)

    def test_delete_data_products_for_observation_record(self):
        delete_associated_data_products(self.observation_record)

        self.assertEqual(
            DataProduct.objects.filter(
                observation_record=self.observation_record,
            ).count(),
            0,
        )
        for data_product in self.data_products:
            self.assertEqual(
                ReducedDatum.objects.filter(data_product=data_product).count(), 0,
            )

    def test_delete_single_data_product(self):
        single_data_product = self.data_products[0]
        delete_associated_data_products(single_data_product)

        self.assertFalse(DataProduct.objects.filter(pk=single_data_product.pk).exists())
        self.assertEqual(
            ReducedDatum.objects.filter(data_product=single_data_product).count(), 0,
        )

    def test_delete_file_and_thumbnail(self):
        # Store file paths before deletion
        file_paths = [
            (dp.data.path, dp.thumbnail.path)
            for dp in self.data_products
            if dp.data and dp.thumbnail
        ]

        delete_associated_data_products(self.observation_record)

        # Check if files and thumbnails are deleted from the disk.
        for data_path, thumbnail_path in file_paths:
            self.assertFalse(
                os.path.exists(data_path), f"Data file {data_path} should be deleted.",
            )
            self.assertFalse(
                os.path.exists(thumbnail_path),
                f"Thumbnail file {thumbnail_path} should be deleted.",
            )

    def test_invalid_argument_type(self):
        with self.assertRaises(ValueError):
            delete_associated_data_products("invalid_argument")


class BuildJsonResponseTests(unittest.TestCase):
    """Test cases for 'build_json_response'."""

    def test_success_response(self):
        """Test building a successful JSON response."""
        response = build_json_response()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.content.decode(), '{"status": "success", "message": ""}',
        )

    def test_error_response_with_custom_message(self):
        """Test building an error JSON response with a custom message."""
        error_message = "An error occurred"
        response = build_json_response(error_message=error_message)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.content.decode(),
            f'{{"status": "error", "message": "{error_message}"}}',
        )

    def test_error_response_with_custom_status(self):
        """Test building an error JSON response with a custom status."""
        error_message = "Not found"
        error_status = status.HTTP_404_NOT_FOUND
        response = build_json_response(
            error_message=error_message, error_status=error_status,
        )
        self.assertEqual(response.status_code, error_status)
        self.assertEqual(
            response.content.decode(),
            f'{{"status": "error", "message": "{error_message}"}}',
        )

    def test_error_response_with_custom_message_and_status(self):
        """Test building an error JSON response with a custom message and
        status.
        """
        error_message = "Unauthorized access"
        error_status = status.HTTP_401_UNAUTHORIZED
        response = build_json_response(
            error_message=error_message, error_status=error_status,
        )
        self.assertEqual(response.status_code, error_status)
        self.assertEqual(
            response.content.decode(),
            f'{{"status": "error", "message": "{error_message}"}}',
        )


@pytest.fixture()
def non_empty_file_list():
    return Table(
        rows=[("file1", "red1"), ("file2", "red2")], names=("name", "reduction"),
    )


class TestCreateNameReductionMap:
    def test_empty_file_list(self):
        """Test with an empty file list."""
        file_list = Table(names=("name", "reduction"), dtype=("str", "str"))
        result = create_name_reduction_map(file_list)
        assert result == {}

    def test_non_empty_file_list(self, non_empty_file_list):
        """Test with a non-empty file list."""
        expected_map = {"file1": "fits_file", "file2": "fits_file"}
        result = create_name_reduction_map(non_empty_file_list)
        assert result == expected_map


@pytest.fixture()
def mock_data_product():
    data_product = Mock()
    data_product.target.name = "target_name"
    return data_product


class TestCustomDataProductPath:
    def test_with_observation_record(self, mock_data_product):
        """Test path generation when an observation record is present."""
        mock_data_product.observation_record = Mock()
        mock_data_product.observation_record.facility = "LCO"
        mock_data_product.observation_record.observation_id = "12345"
        filename = "image.fits"
        expected_path = "target_name/LCO/12345/image.fits"
        result = custom_data_product_path(mock_data_product, filename)
        assert result == expected_path

    def test_without_observation_record(self, mock_data_product):
        """Test path generation when no observation record is present."""
        mock_data_product.observation_record = None
        filename = "image.fits"
        expected_path = "target_name/none/none/image.fits"
        result = custom_data_product_path(mock_data_product, filename)
        assert result == expected_path
