"""Module to access iNaturalist API."""
from time import time
from types import SimpleNamespace
from typing import Union
from aiohttp import (
    ClientConnectorError,
    ClientSession,
    ContentTypeError,
    ServerDisconnectedError,
    TraceConfig,
    TraceRequestStartParams,
)
from aiohttp_retry import RetryClient, ExponentialRetry
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
import html2markdown
from .common import LOG
from .base_classes import API_BASE_URL

RETRY_EXCEPTIONS = [
    ServerDisconnectedError,
    ConnectionResetError,
    ClientConnectorError,
    TimeoutError,
]


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        # pylint: disable=unused-argument
        async def on_request_start(
            session: ClientSession,
            trace_config_ctx: SimpleNamespace,
            params: TraceRequestStartParams,
        ) -> None:
            current_attempt = trace_config_ctx.trace_request_ctx["current_attempt"]
            if current_attempt > 1:
                LOG.info("iNat request attempt #%d: %s", current_attempt, repr(params))

        trace_config = TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        self.session = RetryClient(
            raise_for_status=False, trace_configs=[trace_config],
        )
        self.request_time = time()
        self.places_cache = {}
        self.projects_cache = {}
        self.users_cache = {}
        self.users_login_cache = {}
        self.taxa_cache = {}
        # api_v1_limiter:
        # ---------------
        # - Allow a burst of 60 requests (i.e. equal to max_rate) in the initial
        #   seconds of the 60 second time_period before enforcing a rate limit of
        #   60 requests per minute (max_rate).
        # - This honours "try to keep it to 60 requests per minute or lower":
        #   - https://api.inaturalist.org/v1/docs/
        # - Since the iNat API doesn't throttle until 100 requests per minute,
        #   this should ensure we never get throttled.
        self.api_v1_limiter = AsyncLimiter(60, 60)

    async def _get_rate_limited(self, full_url, **kwargs):
        """Query API, respecting 60 requests per minute rate limit."""
        LOG.info('_get_rate_limited("%s", %s)', full_url, repr(kwargs))
        async with self.api_v1_limiter:
            # i.e. wait 0.1s, 0.2s, 0.4s, 0.8s, and finally give up
            retry_options = ExponentialRetry(attempts=4, exceptions=RETRY_EXCEPTIONS,)
            try:
                async with self.session.get(
                    full_url, params=kwargs, retry_options=retry_options
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        try:
                            json = await response.json()
                            msg = f"{json.get('error')} ({json.get('status')})"
                        except ContentTypeError:
                            data = await response.text()
                            document = BeautifulSoup(data, "html.parser")
                            # Only use the body, if present
                            if document.body:
                                text = document.body.find().text
                            else:
                                text = document
                            # Treat as much as we can as markdown
                            markdown = html2markdown.convert(text)
                            # Punt the rest back to bs4 to drop unhandled tags
                            msg = BeautifulSoup(markdown, "html.parser").text
                        lookup_failed_msg = f"Lookup failed: {msg}"
                        LOG.error(lookup_failed_msg)
                        raise LookupError(lookup_failed_msg)
            except Exception as e:  # pylint: disable=broad-except,invalid-name
                if any(isinstance(e, exc) for exc in retry_options.exceptions):
                    attempts = retry_options.attempts
                    msg = f"iNat not responding after {attempts} attempts. Please try again later."
                    LOG.error(msg)
                    raise LookupError(msg) from e
                raise e

        return None

    async def get_controlled_terms(self, *args, **kwargs):
        """Query API for controlled terms."""

        endpoint = "/".join(("/v1/controlled_terms", *args))
        full_url = f"{API_BASE_URL}{endpoint}"
        return await self._get_rate_limited(full_url, **kwargs)

    # refresh_cache: Boolean
    # - Unlike places and projects which change infrequently, we usually want the
    #   latest, uncached taxon record.
    async def get_taxa(self, *args, refresh_cache=True, **kwargs):
        """Query API for taxa matching parameters.

        Parameters
        ----------
        *args
            - If first positional argument is given, it is passed through
              as-is, appended to the /v1/taxa endpoint.
            - If it's a number, the resulting record will be cached.

        refresh_cache: bool
            - Unlike places and projects which change infrequently, we
              usually want the latest, uncached taxon record, as changes
              are frequently made at the website (e.g. observations count).
            - Specify refresh_cache=True when the latest data from the site
              is not needed, e.g. to show names of ancestors for an existing
              taxon display.

        **kwargs
            - All kwargs are passed as params on the API call.
            - If kwargs["q"] is present, the /v1/taxa/autocomplete endpoint
              is selected, as that gives the best results, most closely
              matching the iNat web taxon lookup experience.
        """

        # Select endpoint based on call signature:
        # - /v1/taxa is needed for id# lookup (i.e. no kwargs["q"])
        endpoint = (
            "/v1/taxa/autocomplete"
            if "q" in kwargs and "page" not in kwargs
            else "/v1/taxa"
        )
        id_arg = f"/{args[0]}" if args else ""
        full_url = f"{API_BASE_URL}{endpoint}{id_arg}"

        # Cache lookup by id#, as those should be stable.
        # - note: we could support splitting a list of id#s and caching each
        #   one, but currently we don't make use of that call, so only cache
        #   when a single ID is specified
        if args and (isinstance(args[0], int) or args[0].isnumeric()):
            taxon_id = int(args[0])
            if refresh_cache or taxon_id not in self.taxa_cache:
                taxon = await self._get_rate_limited(full_url, **kwargs)
                if taxon:
                    self.taxa_cache[taxon_id] = taxon
            return self.taxa_cache[taxon_id] if taxon_id in self.taxa_cache else None

        # Skip the cache for text queries which are not stable.
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_observations(self, *args, **kwargs):
        """Query API for observations.

        Parameters
        ----------
        *args
            - If first positional argument is given, it is passed through
              as-is, appended to the /v1/observations endpoint.

        **kwargs
            - All kwargs are passed as params on the API call.
        """

        endpoint = "/v1/observations"
        id_arg = f"/{args[0]}" if args else ""
        full_url = f"{API_BASE_URL}{endpoint}{id_arg}"
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_observation_bounds(self, taxon_ids):
        """Get the bounds for the specified observations."""
        kwargs = {
            "return_bounds": "true",
            "verifiable": "true",
            "taxon_id": ",".join(map(str, taxon_ids)),
            "per_page": 0,
        }

        result = await self.get_observations(**kwargs)
        if result and "total_bounds" in result:
            return result["total_bounds"]

        return None

    async def get_obs_taxon_summary(self, obs_id=int, **kwargs):
        """Get an observation's taxon summary."""

        endpoint = f"/v1/observations/{obs_id}/taxon_summary"
        full_url = f"{API_BASE_URL}{endpoint}"
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_places(
        self, query: Union[int, str, list], refresh_cache=False, **kwargs
    ):
        """Get places for the specified ids or text query."""

        first_place_id = None
        if isinstance(query, list):
            cached = set(query).issubset(set(self.places_cache))
            request = f"/v1/places/{','.join(map(str, query))}"
        elif isinstance(query, int):
            cached = query in self.places_cache
            if cached:
                first_place_id = query
            request = f"/v1/places/{query}"
        else:
            cached = False
            request = f"/v1/places/{query}"
        full_url = f"{API_BASE_URL}{request}"

        if refresh_cache or not cached:
            results = await self._get_rate_limited(full_url, **kwargs)
            if results:
                places = results.get("results") or []
                for place in places:
                    key = place.get("id")
                    if key:
                        if not first_place_id:
                            first_place_id = key
                        record = {
                            "total_results": 1,
                            "page": 1,
                            "per_page": 1,
                            "results": [place],
                        }
                        self.places_cache[key] = record

        if isinstance(query, list):
            return {
                place_id: self.places_cache[place_id]
                for place_id in query
                if self.places_cache[place_id]
            }
        if first_place_id in self.places_cache:
            return self.places_cache[first_place_id]
        return None

    async def get_projects(
        self, query: Union[str, int, list], refresh_cache=False, **kwargs
    ):
        """Get projects for the specified ids or text query."""

        first_project_id = None
        if isinstance(query, list):
            cached = set(query).issubset(set(self.projects_cache))
            request = f"/v1/projects/{','.join(map(str, query))}"
        elif isinstance(query, int):
            cached = query in self.projects_cache
            if cached:
                first_project_id = query
            request = f"/v1/projects/{query}"
        else:
            cached = False
            request = f"/v1/projects/{query}"
        full_url = f"{API_BASE_URL}{request}"

        if refresh_cache or not cached:
            results = await self._get_rate_limited(full_url, **kwargs)
            if results:
                projects = results.get("results") or []
                for project in projects:
                    key = project.get("id")
                    if key:
                        if not first_project_id:
                            first_project_id = key
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
        if first_project_id in self.projects_cache:
            return self.projects_cache[first_project_id]
        return None

    async def get_project_observers_stats(self, **kwargs):
        """Query API for user counts & rankings in a project."""
        request = "/v1/observations/observers"
        # TODO: validate kwargs includes project_id
        # TODO: support projects with > 500 observers (one page, default)
        full_url = f"{API_BASE_URL}{request}"
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_search_results(self, **kwargs):
        """Get site search results."""
        if "is_active" in kwargs and kwargs["is_active"] == "any":
            full_url = f"{API_BASE_URL}/v1/taxa"
        else:
            full_url = f"{API_BASE_URL}/v1/search"
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_users(self, query: Union[int, str], refresh_cache=False, **kwargs):
        """Get the users for the specified login, user_id, or query."""
        if isinstance(query, int) or query.isnumeric():
            user_id = int(query)
            request = f"/v1/users/{query}"
            key = user_id
        else:
            user_id = None
            request = f"/v1/users/autocomplete?q={query}"
            key = query
        full_url = f"{API_BASE_URL}{request}"

        if refresh_cache or (
            key not in self.users_cache and key not in self.users_login_cache
        ):
            # TODO: provide means to expire the cache (other than reloading the cog).
            json_data = await self._get_rate_limited(full_url, **kwargs)

            if json_data:
                results = json_data.get("results")
                if not results:
                    return None
                if user_id is None:
                    if len(results) == 1:
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
                    # i.e. lookup by user_id only returns one match
                    user = results[0]
                    if user:
                        self.users_cache[key] = json_data
                        self.users_login_cache[user["login"]] = key
                    self.request_time = time()

        if key in self.users_cache:
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
            user_id = self.users_login_cache[key]
            return self.users_cache[user_id]
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
