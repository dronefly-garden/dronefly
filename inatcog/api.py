"""Module to access iNaturalist API."""
from typing import Union
import asyncio
import aiohttp

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        self.users_cache = {}
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

        if query not in self.users_cache:
            async with self.session.get(f"{API_BASE_URL}{request}") as response:
                # TODO: replace quick-and-dirty rate limit with something reasonable.
                self.users_cache[query] = await response.json()
                # - This delays each response 2/3 of a second to stay within
                #   100 requests per minute (see iNat API v1 docs).
                await asyncio.sleep(0.66)

        return self.users_cache[query]
