"""Module to access iNaturalist API."""
from time import time
from typing import Union
import asyncio
import aiohttp
from .common import LOG

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        self.request_time = time()
        self.places_cache = {}
        self.projects_cache = {}
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
            if response.status == 200:
                return await response.json()

    async def get_observations(self, *args, **kwargs):
        """Query API for observations matching parameters."""

        # Select endpoint based on call signature:
        endpoint = "/v1/observations"
        id_arg = f"/{args[0]}" if args else ""

        async with self.session.get(
            f"{API_BASE_URL}{endpoint}{id_arg}", params=kwargs
        ) as response:
            if response.status == 200:
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

    async def get_places(self, query: Union[int, str], refresh_cache=False, **kwargs):
        """Query API for places matching place ID or params."""

        # Select endpoint based on call signature:
        request = f"/v1/places/{query}"

        # Cache lookup by id#, as those should be stable.
        if isinstance(query, int) or query.isnumeric():
            place_id = int(query)
            if refresh_cache or place_id not in self.places_cache:
                # Rate-limit these so they can be retrieved in a loop without tripping
                # iNat API's rate-limiting.
                time_since_request = time() - self.request_time
                if time_since_request < 1.0:
                    await asyncio.sleep(1.0 - time_since_request)
                async with self.session.get(f"{API_BASE_URL}{request}") as response:
                    if response.status == 200:
                        self.places_cache[place_id] = await response.json()
                        self.request_time = time()
            return (
                self.places_cache[place_id] if place_id in self.places_cache else None
            )

        # Skip the cache for text queries which are not stable.
        async with self.session.get(
            f"{API_BASE_URL}{request}", params=kwargs
        ) as response:
            if response.status == 200:
                return await response.json()

    async def get_projects(self, project_id: int, refresh_cache=False):
        """Get the project for the specified id."""
        request = f"/v1/projects/{project_id}"

        if refresh_cache or project_id not in self.projects_cache:
            async with self.session.get(f"{API_BASE_URL}{request}") as response:
                if response.status == 200:
                    self.projects_cache[project_id] = await response.json()

        return (
            self.projects_cache[project_id]
            if project_id in self.projects_cache
            else None
        )

    async def get_project_observers_stats(self, **kwargs):
        """Query API for user counts & rankings in a project."""
        request = "/v1/observations/observers"
        # TODO: validate kwargs includes project_id
        # TODO: support projects with > 500 observers (one page, default)
        async with self.session.get(
            f"{API_BASE_URL}{request}", params=kwargs
        ) as response:
            if response.status == 200:
                return await response.json()

    async def get_users(self, query: Union[int, str], refresh_cache=False):
        """Get the users for the specified login, user_id, or query."""
        if isinstance(query, int) or query.isnumeric():
            request = f"/v1/users/{query}"
        else:
            request = f"/v1/users/autocomplete?q={query}"

        if refresh_cache or query not in self.users_cache:
            time_since_request = time() - self.request_time
            # Limit to 60 requests every minute. Hard upper limit is 100 per minute
            # after which they rate-limit, but the API doc requests that we
            # limit it to 60.
            # TODO: generalize & apply to all requests.
            # TODO: provide means to expire the cache (other than reloading the cog).
            if time_since_request < 1.0:
                await asyncio.sleep(1.0 - time_since_request)
            async with self.session.get(f"{API_BASE_URL}{request}") as response:
                if response.status == 200:
                    self.users_cache[query] = await response.json()
                    self.request_time = time()

        return self.users_cache[query] if query in self.users_cache else None

    async def get_observers_from_projects(self, project_ids: list):
        """Get observers for a list of project ids.

        Since the cache is filled as a side effect, this method can be
        used to prime the cache prior to fetching multiple users at once
        by id.
        """
        if not project_ids:
            return

        response = await self.get_observations(
            "observers", project_id=",".join(project_ids)
        )
        users = []
        results = response.get("results") or []
        for observer in results:
            user = observer.get("user")
            LOG.info(user)
            if user:
                user_id = user.get("id")
                if user_id:
                    # Synthesize a single result as if returned by a get_users
                    # lookup of a single user_id, and cache it:
                    user_json = {}
                    user_json["results"] = [user]
                    self.users_cache[user_id] = user_json

        return users
