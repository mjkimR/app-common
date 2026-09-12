"""Unit tests verifying pytest-mock integration."""

from unittest.mock import MagicMock

from pytest_mock import MockerFixture


class ExternalServiceClient:
    def fetch_data(self) -> str:
        return "real_data"


def test_mocker_fixture(mocker: MockerFixture):
    client = ExternalServiceClient()
    mocker.patch.object(client, "fetch_data", return_value="mocked_data")

    assert client.fetch_data() == "mocked_data"
    assert isinstance(client.fetch_data, MagicMock)
