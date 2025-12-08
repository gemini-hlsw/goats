import pytest
from unittest.mock import Mock
from rest_framework import serializers

from goats_tom.serializers.gpp.instruments.gmos._base_gmos import _BaseGMOSSerializer


def test_base_gmos_serializer_calls_nested_serializer(mocker):
    """
    Test that _BaseGMOSSerializer correctly instantiates, validates, and stores
    the ExposureModeSerializer when to_internal_value is called.
    """
    mock_exposure_cls = mocker.patch(
        "goats_tom.serializers.gpp.instruments.gmos._base_gmos.ExposureModeSerializer"
    )

    mock_instance = Mock()
    mock_exposure_cls.return_value = mock_instance
    mock_instance.is_valid.return_value = True

    data = {"foo": "bar"}

    s = _BaseGMOSSerializer()
    result = s.to_internal_value(data)

    assert result == {}, "Expected empty dict from base deserialization."

    mock_exposure_cls.assert_called_once_with(data=data)

    mock_instance.is_valid.assert_called_once_with(raise_exception=True)

    assert s._exposure_mode_serializer is mock_instance, "Expected exposure mode serializer to be stored."
