"""Module to access iNaturalist API."""
from typing import Union
import aiohttp

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def get_taxa(self, *args, **kwargs):
        """Query API for taxa matching parameters."""

        # Select endpoint based on call signature:
        # - /v1/taxa is needed for id# lookup (i.e. no kwargs["q"])
        endpoint = "/v1/taxa/autocomplete" if "q" in kwargs else "/v1/taxa"
        id_arg = f"/{args[0]}" if args else ""

        async with self.session.get(
            f"{API_BASE_URL}{endpoint}{id_arg}", params=kwargs
        ) as response:
            return await response.json()

    async def get_observations(self, *args, **kwargs):
        """Query API for observations matching parameters."""

        # Select endpoint based on call signature:
        endpoint = "/v1/observations"
        id_arg = f"/{args[0]}" if args else ""

        async with self.session.get(
            f"{API_BASE_URL}{endpoint}{id_arg}", params=kwargs
        ) as response:
            return await response.json()

    async def get_observation_bounds(self, taxon_ids):
        """Get the bounds for the specified observations."""
        kwargs = {
            "return_bounds": "true",
            "verifiable": "true",
            "taxon_id": ",".join(map(str, taxon_ids)),
            "per_page": 0,
        }

        result = await self.get_observations(**kwargs)
        if "total_bounds" in result:
            return result["total_bounds"]

        return None

    async def get_users(self, query: Union[int, str]):
        """Get the users for the specified login, user_id, or query."""
        if isinstance(query, int) or query.isnumeric():
            request = f"/v1/users/{query}"
        else:
            request = f"/v1/users/autocomplete?q={query}"

        async with self.session.get(f"{API_BASE_URL}{request}") as response:
            return await response.json()
