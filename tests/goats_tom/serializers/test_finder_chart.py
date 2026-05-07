import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from goats_tom.serializers.gpp.finder_chart import (
    FinderChartFileSerializer,
    FinderChartsSerializer,
)


def make_file(name="test.png", content=b"abc", content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


#
# FinderChartFileSerializer
#


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("chart.png", "image/png"),
        ("chart.jpg", "image/jpeg"),
        ("chart.jpeg", "image/jpeg"),
    ],
)
def test_file_serializer_accepts_valid_extensions(filename, content_type):
    serializer = FinderChartFileSerializer(
        data={"file": make_file(filename, content_type=content_type)}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["description"] == ""


@pytest.mark.parametrize(
    "filename,content_type,expected_fragment",
    [
        ("chart.txt", "text/plain", "Invalid file type"),
        ("chart.pdf", "application/pdf", "Invalid file type"),
        ("chart", "application/octet-stream", ".unknown"),
    ],
)
def test_file_serializer_rejects_invalid_extensions(
    filename,
    content_type,
    expected_fragment,
):
    serializer = FinderChartFileSerializer(
        data={"file": make_file(filename, content_type=content_type)}
    )

    assert not serializer.is_valid()
    assert "file" in serializer.errors
    assert expected_fragment in str(serializer.errors["file"][0])


@pytest.mark.parametrize(
    "size,valid",
    [
        (1, True),
        (FinderChartFileSerializer.MAX_BYTES, True),
        (FinderChartFileSerializer.MAX_BYTES + 1, False),
    ],
)
def test_file_serializer_validates_size(size, valid):
    serializer = FinderChartFileSerializer(
        data={"file": make_file("chart.png", content=b"x" * size)}
    )

    assert serializer.is_valid() is valid
    if not valid:
        assert "file" in serializer.errors
        assert "File too large" in str(serializer.errors["file"][0])


@pytest.mark.parametrize(
    "description",
    [
        "",
        "finder chart",
    ],
)
def test_file_serializer_accepts_description(description):
    serializer = FinderChartFileSerializer(
        data={
            "description": description,
            "file": make_file("chart.png"),
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["description"] == description


#
# FinderChartsSerializer
#


@pytest.mark.parametrize(
    "payload,expected_to_add_len,expected_to_delete",
    [
        ({}, 0, []),
        ({"toAdd": []}, 0, []),
        ({"toDelete": []}, 0, []),
        ({"toAdd": [], "toDelete": []}, 0, []),
        (
            {
                "toAdd": [
                    {
                        "description": "chart 1",
                        "file": make_file("chart1.png"),
                    }
                ]
            },
            1,
            [],
        ),
        (
            {"toDelete": ["a1", "a2"]},
            0,
            ["a1", "a2"],
        ),
    ],
)
def test_finder_charts_serializer_accepts_valid_payloads(
    payload,
    expected_to_add_len,
    expected_to_delete,
):
    serializer = FinderChartsSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    assert len(serializer.validated_data["toAdd"]) == expected_to_add_len
    assert serializer.validated_data["toDelete"] == expected_to_delete


@pytest.mark.parametrize(
    "payload,expected_to_add_len,expected_to_delete",
    [
        (
            {
                "finderCharts": {
                    "toAdd": [
                        {
                            "description": "chart 1",
                            "file": make_file("chart1.png"),
                        }
                    ],
                    "toDelete": ["a1"],
                }
            },
            1,
            ["a1"],
        ),
        (
            {"finderCharts": None},
            0,
            [],
        ),
        (
            {"finderCharts": {}},
            0,
            [],
        ),
    ],
)
def test_finder_charts_serializer_accepts_nested_findercharts_object(
    payload,
    expected_to_add_len,
    expected_to_delete,
):
    serializer = FinderChartsSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    assert len(serializer.validated_data["toAdd"]) == expected_to_add_len
    assert serializer.validated_data["toDelete"] == expected_to_delete


@pytest.mark.parametrize(
    "filename,valid",
    [
        ("chart1.png", True),
        ("chart1.jpg", True),
        ("chart1.jpeg", True),
        ("chart1.txt", False),
    ],
)
def test_finder_charts_serializer_validates_files_inside_to_add(filename, valid):
    serializer = FinderChartsSerializer(
        data={
            "toAdd": [
                {
                    "description": "chart 1",
                    "file": make_file(filename),
                }
            ]
        }
    )

    assert serializer.is_valid() is valid
    if not valid:
        assert "toAdd" in serializer.errors


@pytest.mark.parametrize(
    "to_delete,valid",
    [
        ([], True),
        (["a1"], True),
        (["a1", "a2"], True),
        ([123, 1235], True),
    ],
)
def test_finder_charts_serializer_validates_to_delete_items(to_delete, valid):
    serializer = FinderChartsSerializer(data={"toDelete": to_delete})
    assert serializer.is_valid() is valid
    if not valid:
        assert "toDelete" in serializer.errors
