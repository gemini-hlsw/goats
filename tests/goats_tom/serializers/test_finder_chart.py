import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from goats_tom.serializers.gpp import FinderChartUploadSerializer


def make_file(name="test.png", size=100):
    return SimpleUploadedFile(name, b"x" * size, content_type="image/png")


def test_serializer_valid_file():
    serializer = FinderChartUploadSerializer(
        data={
            "programId": "p1",
            "observationId": "o1",
            "description": "test",
            "file": make_file(),
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_serializer_rejects_large_file():
    large_size = FinderChartUploadSerializer.MAX_BYTES + 1

    serializer = FinderChartUploadSerializer(
        data={
            "programId": "p1",
            "observationId": "o1",
            "file": make_file(size=large_size),
        }
    )

    assert not serializer.is_valid()
    assert "file" in serializer.errors


def test_serializer_rejects_invalid_extension():
    file = SimpleUploadedFile("bad.txt", b"x", content_type="text/plain")

    serializer = FinderChartUploadSerializer(
        data={
            "programId": "p1",
            "observationId": "o1",
            "file": file,
        }
    )

    assert not serializer.is_valid()
    assert "file" in serializer.errors
