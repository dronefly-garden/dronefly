"""Module to access iNaturalist API."""
from time import time
from typing import Union
import asyncio
import aiohttp
from .common import LOG

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"
# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
WWW_URL_PAT = (
    r"https?://("
    r"((www|colombia|panama|ecuador|israel)\.)?inaturalist\.org"
    r"|inaturalist\.ala\.org\.au"
    r"|(www\.)?("
    r"inaturalist\.(ca|nz)"
    r"|naturalista\.mx"
    r"|biodiversity4all\.org"
    r"|argentinat\.org"
    r"|inaturalist\.laji\.fi"
    r")"
    r")"
)


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        self.request_time = time()
        self.places_cache = {}
        self.projects_cache = {}
        self.users_cache = {}
        self.users_login_cache = {}
        self.session = aiohttp.ClientSession()

    async def get_controlled_terms(self, *args, **kwargs):
        """Query API for controlled terms."""

        # Select endpoint based on call signature:
        # - /v1/taxa is needed for id# lookup (i.e. no kwargs["q"])
        endpoint = "/".join(("/v1/controlled_terms", *args))

        async with self.session.get(
            f"{API_BASE_URL}{endpoint}", params=kwargs
        ) as response:
            if response.status == 200:
                return await response.json()

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

    async def get_projects(
        self, query: Union[str, int, list], refresh_cache=False, **kwargs
    ):
        """Get the project for the specified id."""

        last_project_id = None
        if isinstance(query, list):
            cached = set(query).issubset(set(self.projects_cache))
            request = f"/v1/projects/{','.join(map(str, query))}"
        elif isinstance(query, int):
            cached = query in self.projects_cache
            if cached:
                last_project_id = query
            request = f"/v1/projects/{query}"
        else:
            cached = False
            request = f"/v1/projects/{query}"

        if refresh_cache or not cached:
            async with self.session.get(
                f"{API_BASE_URL}{request}", params=kwargs
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    projects = results.get("results") or []
                    for project in projects:
                        key = project.get("id")
                        if key:
                            last_project_id = key
                            record = {
                                "total_results": 1,
                                "page": 1,
                                "per_page": 1,
                                "results": [project],
                            }
                            self.projects_cache[key] = record

        if isinstance(query, list):
            return {
                project_id: self.projects_cache[project_id]
                for project_id in query
                if self.projects_cache[project_id]
            }
        if last_project_id in self.projects_cache:
            return self.projects_cache[last_project_id]
        return None

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

    async def get_search_results(self, **kwargs):
        """Get site search results."""
        if "is_active" in kwargs and kwargs["is_active"] == "any":
            url = f"{API_BASE_URL}/v1/taxa"
        else:
            url = f"{API_BASE_URL}/v1/search"
        async with self.session.get(url, params=kwargs) as response:
            if response.status == 200:
                return await response.json()

    async def get_users(self, query: Union[int, str], refresh_cache=False):
        """Get the users for the specified login, user_id, or query."""
        if isinstance(query, int) or query.isnumeric():
            user_id = int(query)
            request = f"/v1/users/{query}"
            key = user_id
        else:
            user_id = None
            request = f"/v1/users/autocomplete?q={query}"
            key = query
        LOG.info(repr(key))

        if refresh_cache or (
            key not in self.users_cache and key not in self.users_login_cache
        ):
            LOG.info("cache miss")
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
                    json_data = await response.json()
                    results = json_data.get("results")
                    if not results:
                        return None
                    LOG.info("found")
                    if user_id is None:
                        if len(results) == 1:
                            LOG.info("unique text")
                            # String query matched exactly one result; cache it:
                            user = results[0]
                            # The entry itself is put in the main cache, indexed by user_id.
                            self.users_cache[user["id"]] = json_data
                            # Lookaside by login stores only linkage to the
                            # entry just stored in the main cache.
                            self.users_login_cache[user["login"]] = user["id"]
                            # Additionally add an entry to the main cache for
                            # the query string, but only for other than an
                            # exact login id match as that would serve no
                            # purpose. This is slightly wasteful, but makes for
                            # simpler code.
                            if user["login"] != key:
                                self.users_cache[key] = json_data
                        else:
                            LOG.info("non-unique text")
                            # Cache multiple results matched by string.
                            self.users_cache[key] = json_data
                            # Additional synthesized cache results per matched user, as
                            # if they were queried individually.
                            for user in results:
                                user_json = {}
                                user_json["results"] = [user]
                                self.users_cache[user["id"]] = user_json
                                # Only index the login in the lookaside cache if it
                                # isn't the query string itself, already indexed above
                                # in the main cache.
                                # - i.e. it's possible a search for a login matches
                                #   more than one entry (e.g. david, david99, etc.)
                                #   so retrieving it from cache must always return
                                #   all matching results, not just one for the login
                                #   itself
                                if user["login"] != key:
                                    self.users_login_cache[user["login"]] = user["id"]
                    else:
                        LOG.info("numeric")
                        LOG.info(repr(results))
                        # i.e. lookup by user_id only returns one match
                        user = results[0]
                        if user:
                            LOG.info("caching numeric")
                            self.users_cache[key] = json_data
                            self.users_login_cache[user["login"]] = key
                    self.request_time = time()

        if key in self.users_cache:
            LOG.info("cache hit")
            return self.users_cache[key]
        # - Lookaside for login is only consulted if not found in the main
        #   users_cache.
        # - This is important, since a lookup by user_id could prime the
        #   lookaside cache with the single login entry, and then a subsequent
        #   search by login could return multiple results into the main cache.
        #   From then on, searching for the login should return the cached
        #   multiple results from the main cache, not the single result that the
        #   lookaside users_login_cache supports.
        # - This shortcut seems like it would return incomplete results depending
        #   on the order in which lookups are performed. However, since the login
        #   lookaside is primarily in support of iNat login lookups from already
        #   cached project members, this is OK. The load of the whole project
        #   membership at once (get_observers_from_projects) for that use case
        #   ensures all relevant matches are already individually cached.
        if key in self.users_login_cache:
            LOG.info("login cache hit")
            user_id = self.users_login_cache[key]
            return self.users_cache[user_id]
        LOG.info("cache miss")
        return None

    async def get_observers_from_projects(self, project_ids: list):
        """Get observers for a list of project ids.

        Since the cache is filled as a side effect, this method can be
        used to prime the cache prior to fetching multiple users at once
        by id.
        """
        if not project_ids:
            return

        response = await self.get_observations(
            "observers", project_id=",".join(map(str, project_ids))
        )
        users = []
        results = response.get("results") or []
        for observer in results:
            user = observer.get("user")
            if user:
                user_id = user.get("id")
                if user_id:
                    # Synthesize a single result as if returned by a get_users
                    # lookup of a single user_id, and cache it:
                    user_json = {}
                    user_json["results"] = [user]
                    self.users_cache[user_id] = user_json
                    self.users_login_cache[user["login"]] = user_id

        return users
