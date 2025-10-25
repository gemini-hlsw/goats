import pytest
from gpp_client.api.input_types import (
    DeclinationInput,
    RightAscensionInput,
    SiderealInput,
    SourceProfileInput,
    TargetPropertiesInput,
)

from goats_tom.serializers.gpp import TargetSerializer


@pytest.fixture
def dummy_input() -> dict:
    """
    Provides a minimal valid target input dictionary for serializer tests.
    """
    return {
        "hiddenGoatsTargetIdInput": 1,
        "radialVelocityInput": 42.0,
        "parallaxInput": 3.3,
        "uRaInput": -0.1,
        "uDecInput": 0.05,
        "sourceTypeSelect": "POINT",
        "spectralDistributionSelect": "blackBody",
        "blackBodyTempKInput": 7500,
        "brightnesses": [{"band": "r", "value": 15.0}],
    }


class TestTargetSerializer:
    """Tests for the TargetSerializer behavior with nested serializers and output formats."""

    def test_combines_subserializers(self, mocker, dummy_input):
        """
        Ensure TargetSerializer merges outputs from Sidereal and SourceProfile serializers.
        """
        sidereal_mock = mocker.MagicMock()
        sidereal_mock.is_valid.return_value = True
        sidereal_mock.format_gpp.return_value = {
            "ra": {"degrees": 100},
            "dec": {"degrees": -30},
        }

        source_mock = mocker.MagicMock()
        source_mock.is_valid.return_value = True
        source_mock.format_gpp.return_value = {"profile": "POINT"}

        mocker.patch(
            "goats_tom.serializers.gpp.target.SiderealSerializer",
            return_value=sidereal_mock,
        )
        mocker.patch(
            "goats_tom.serializers.gpp.target.SourceProfileSerializer",
            return_value=source_mock,
        )

        serializer = TargetSerializer(data=dummy_input)
        assert serializer.is_valid(), (
            "Expected serializer to be valid with mocked subserializers."
        )

        assert serializer.to_gpp() == {
            "sidereal": {"ra": {"degrees": 100}, "dec": {"degrees": -30}},
            "sourceProfile": {"profile": "POINT"},
        }, "Expected combined GPP output from both mocked serializers."

    @pytest.mark.parametrize(
        "sidereal_data, source_data, expected",
        [
            (None, {"profile": "POINT"}, {"sourceProfile": {"profile": "POINT"}}),
            ({"ra": {"degrees": 100}}, None, {"sidereal": {"ra": {"degrees": 100}}}),
            (None, None, None),
        ],
    )
    def test_partial_or_none_results(
        self, mocker, dummy_input, sidereal_data, source_data, expected
    ):
        """
        Verify correct output when either or both subserializers return None.
        """
        sidereal_mock = mocker.MagicMock()
        sidereal_mock.is_valid.return_value = True
        sidereal_mock.format_gpp.return_value = sidereal_data

        source_mock = mocker.MagicMock()
        source_mock.is_valid.return_value = True
        source_mock.format_gpp.return_value = source_data

        mocker.patch(
            "goats_tom.serializers.gpp.target.SiderealSerializer",
            return_value=sidereal_mock,
        )
        mocker.patch(
            "goats_tom.serializers.gpp.target.SourceProfileSerializer",
            return_value=source_mock,
        )

        serializer = TargetSerializer(data=dummy_input)
        assert serializer.is_valid(), (
            "Expected serializer to be valid for partial data."
        )
        assert serializer.to_gpp() == expected, f"Expected output: {expected}"

    def test_raises_on_sidereal_failure(self, mocker, dummy_input):
        """
        Ensure that exceptions from the SiderealSerializer are propagated.
        """
        sidereal_mock = mocker.MagicMock()
        sidereal_mock.is_valid.side_effect = Exception("sidereal failed")

        source_mock = mocker.MagicMock()
        source_mock.is_valid.return_value = True

        mocker.patch(
            "goats_tom.serializers.gpp.target.SiderealSerializer",
            return_value=sidereal_mock,
        )
        mocker.patch(
            "goats_tom.serializers.gpp.target.SourceProfileSerializer",
            return_value=source_mock,
        )

        with pytest.raises(Exception, match="sidereal failed"):
            TargetSerializer(data=dummy_input).is_valid(raise_exception=True)

    def test_raises_on_source_failure(self, mocker, dummy_input):
        """
        Ensure that exceptions from the SourceProfileSerializer are propagated.
        """
        sidereal_mock = mocker.MagicMock()
        sidereal_mock.is_valid.return_value = True

        source_mock = mocker.MagicMock()
        source_mock.is_valid.side_effect = Exception("source profile failed")

        mocker.patch(
            "goats_tom.serializers.gpp.target.SiderealSerializer",
            return_value=sidereal_mock,
        )
        mocker.patch(
            "goats_tom.serializers.gpp.target.SourceProfileSerializer",
            return_value=source_mock,
        )

        with pytest.raises(Exception, match="source profile failed"):
            TargetSerializer(data=dummy_input).is_valid(raise_exception=True)

    def test_to_pydantic_returns_valid_model(self, mocker):
        """
        Verify that to_pydantic produces a valid TargetPropertiesInput instance from subserializer output.
        """

        class DummySidereal:
            def is_valid(self, raise_exception=False):
                return True

            def format_gpp(self):
                return {
                    "ra": {"degrees": 1.23},
                    "dec": {"degrees": 4.56},
                    "epoch": "J2000.000",
                }

        class DummySource:
            def is_valid(self, raise_exception=False):
                return True

            def format_gpp(self):
                return {
                    "profileType": "POINT",
                    "spectralDistribution": {"blackBodyTempK": 7500},
                    "brightnesses": [{"band": "r", "value": 15.0}],
                }

        mocker.patch(
            "goats_tom.serializers.gpp.target.SiderealSerializer",
            return_value=DummySidereal(),
        )
        mocker.patch(
            "goats_tom.serializers.gpp.target.SourceProfileSerializer",
            return_value=DummySource(),
        )

        serializer = TargetSerializer(data={"mock": "data"})
        assert serializer.is_valid(), (
            "Expected serializer to be valid with dummy inputs."
        )

        model = serializer.to_pydantic()
        assert isinstance(model, TargetPropertiesInput), (
            "Expected model to be of type TargetPropertiesInput."
        )

        assert model.sidereal == SiderealInput(
            ra=RightAscensionInput(degrees=1.23),
            dec=DeclinationInput(degrees=4.56),
            epoch="J2000.000",
        ), "Expected correct SiderealInput construction."

        assert model.source_profile == SourceProfileInput(
            profile_type="POINT",
            spectral_distribution={"blackBodyTempK": 7500},
            brightnesses=[{"band": "r", "value": 15.0}],
        ), "Expected correct SourceProfileInput construction."
