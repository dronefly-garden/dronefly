"""Test inatcog.api."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from aiohttp import ClientSession

from inatcog.api import INatAPI


class ResponseMock:
    def __init__(self, expected_result):
        self.status = 200
        self.expected_result = expected_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error_info):
        return self

    async def json(self):
        return self.expected_result


@pytest_asyncio.fixture
async def mock_api(loop_scope="session"):
    """Fixture providing an INatAPI instance with patched ClientSession."""
    with patch("aiohttp_retry.ClientSession", return_value=AsyncMock(ClientSession)):
        yield INatAPI()


@pytest.fixture
def mock_get():
    """Fixture patching RetryClient.get."""
    with patch("aiohttp_retry.RetryClient.get") as mock:
        yield mock


@pytest.fixture
def mock_sleep():
    """Fixture patching asyncio.sleep to eliminate real delays in tests."""
    with patch("asyncio.sleep", new_callable=MagicMock) as mock:
        yield mock


# TODO: mock ctx
# async def test_get_taxa_by_id(mock_api, mock_get):
#     """Test get_taxa by id."""
#     expected_result = {"results": [{"name": "Animalia"}]}
#     mock_get.return_value = ResponseMock(expected_result)
#     taxon = await mock_api.get_taxa(ctx, 1)
#     assert taxon["results"][0]["name"] == "Animalia"


# async def test_get_taxa_by_query(mock_api, mock_get):
#     """Test get_taxa with query terms."""
#     expected_result = {"results": [{"name": "Animalia"}]}
#     mock_get.return_value = ResponseMock(expected_result)
#     taxon = await mock_api.get_taxa(ctx, q="animals")
#     assert taxon["results"][0]["name"] == "Animalia"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_observation_bounds(mock_api, mock_get):
    """Test get_observation_bounds."""
    expected_result_1 = {}
    expected_result_2 = {
        "total_bounds": {"swlat": 1, "swlng": 2, "nelat": 3, "nelng": 4}
    }

    mock_get.return_value = ResponseMock(expected_result_1)
    assert await mock_api.get_observation_bounds([]) is None
    assert await mock_api.get_observation_bounds(["1"]) is None

    mock_get.return_value = ResponseMock(expected_result_2)
    assert (
        await mock_api.get_observation_bounds(["1"])
        == expected_result_2["total_bounds"]
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_get_users_by_id(mock_api, mock_get):
    """Test get_users by id."""
    expected_result = {"results": [{"id": 545640, "login": "benarmstrong"}]}

    mock_get.return_value = ResponseMock(expected_result)
    users = await mock_api.get_users(545640, refresh_cache=True)
    assert users["results"][0]["login"] == "benarmstrong"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_users_by_login(mock_api, mock_get):
    """Test get_users by login."""
    expected_result = {"results": [{"id": 545640, "login": "benarmstrong"}]}

    mock_get.return_value = ResponseMock(expected_result)
    users = await mock_api.get_users("benarmstrong", refresh_cache=True)
    assert users["results"][0]["login"] == "benarmstrong"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_users_by_name(mock_api, mock_get):
    """Test get_users by name."""
    expected_result = {
        "results": [
            {"id": 545640, "login": "benarmstrong"},
            {"id": 2, "login": "bensomebodyelse"},
        ]
    }

    mock_get.return_value = ResponseMock(expected_result)
    users = await mock_api.get_users("Ben Armstrong", refresh_cache=True)
    assert users["results"][1]["login"] == "bensomebodyelse"
