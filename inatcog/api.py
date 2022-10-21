"""Module to access iNaturalist API.

- Note: Most methods use aiohttp directly, whereas some now use pyinaturalist. Please note
  that for each of these we're working on moving from homegrown approaches to built-in
  capabilities in pyinaturalist for:
  - caching
  - rate-limiting
- Until migration to pyinaturalist is complete, mismatches between the two approaches might
  lead to:
  - any old code that depends on specific caching behaviours may not work correctly with
    new pyinaturalist-based replacements
  - there's an outside chance that rate limits may be exceeded, since neither rate-limiter
    is aware of the rate buckets collected by the other.
- Therefore, take care to add transitional code that mixes the two underlying libraries
  sparingly, and in particular:
  - prefer adding new methods over modifying existing ones to use pyinaturalist
  - focus on methods for commands that are infrequently called to reduce the
    probability of rate limits being exceeded
"""
from functools import partial
from json import JSONDecodeError
import logging
from time import time
from types import SimpleNamespace
from typing import List, Optional, Union

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
from pyinaturalist import (
    add_project_users,
    delete_project_users,
    get_taxa_autocomplete,
    get_projects_by_id,
)
from pyinaturalist import get_taxa_autocomplete, get_projects_by_id

logger = logging.getLogger("red.dronefly." + __name__)

API_BASE_URL = "https://api.inaturalist.org"
RETRY_EXCEPTIONS = [
    ServerDisconnectedError,
    ConnectionResetError,
    ClientConnectorError,
    JSONDecodeError,
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
                logger.info("iNat request attempt #%d: %s", current_attempt, repr(params))

        trace_config = TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        self.session = RetryClient(
            raise_for_status=False,
            trace_configs=[trace_config],
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
        logger.debug('_get_rate_limited("%s", %s)', full_url, repr(kwargs))
        async with self.api_v1_limiter:
            # i.e. wait 0.1s, 0.2s, 0.4s, 0.8s, 1.6s, 3.2s, and finally give up
            retry_options = ExponentialRetry(
                attempts=6,
                exceptions=RETRY_EXCEPTIONS,
            )
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
                        logger.error(lookup_failed_msg)
                        raise LookupError(lookup_failed_msg)
            except Exception as e:  # pylint: disable=broad-except,invalid-name
                if any(isinstance(e, exc) for exc in retry_options.exceptions):
                    attempts = retry_options.attempts
                    msg = f"iNat not responding after {attempts} attempts. Please try again later."
                    logger.error(msg)
                    raise LookupError(msg) from e
                raise e

        return None

    async def _pyinaturalist_endpoint(self, endpoint, ctx, *args, **kwargs):
        if "access_token" in kwargs:
            safe_kwargs = {**kwargs}
            safe_kwargs["access_token"] = "***REDACTED***"
        else:
            safe_kwargs = kwargs
        logger.debug(
            "_pyinaturalist_endpoint(%s, %s, %s)",
            endpoint.__name__,
            repr(args),
            repr(safe_kwargs),
        )

        return await ctx.bot.loop.run_in_executor(
            None, partial(endpoint, *args, **kwargs)
        )

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
        _kwargs = {
            "all_names": "true",
            **kwargs,
        }

        # Cache lookup by id#, as those should be stable.
        # - note: we could support splitting a list of id#s and caching each
        #   one, but currently we don't make use of that call, so only cache
        #   when a single ID is specified
        if args and (isinstance(args[0], int) or args[0].isnumeric()):
            taxon_id = int(args[0])
            if refresh_cache or taxon_id not in self.taxa_cache:
                taxon = await self._get_rate_limited(full_url, **_kwargs)
                if taxon:
                    self.taxa_cache[taxon_id] = taxon
            return self.taxa_cache[taxon_id] if taxon_id in self.taxa_cache else None

        # Skip the cache for text queries which are not stable.
        return await self._get_rate_limited(full_url, **_kwargs)

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

    async def get_observers_stats(self, **kwargs):
        """Query API for user counts & rankings."""
        request = "/v1/observations/observers"
        # TODO: validate kwargs includes project_id
        # TODO: support queries with > 500 observers (one page, default)
        full_url = f"{API_BASE_URL}{request}"
        return await self._get_rate_limited(full_url, **kwargs)

    async def get_search_results(self, **kwargs):
        """Get site search results."""
        if "is_active" in kwargs and kwargs["is_active"] == "any":
            full_url = f"{API_BASE_URL}/v1/taxa"
        else:
            full_url = f"{API_BASE_URL}/v1/search"
        return await self._get_rate_limited(full_url, **kwargs)

    # Some thin wrappers around pyinaturalist endpoints:
    async def add_project_users(self, ctx, project_id, user_ids, **kwargs):
        """Add users to a project's rules."""
        return await self._pyinaturalist_endpoint(
            add_project_users, ctx, project_id, user_ids, **kwargs
        )

    async def delete_project_users(self, ctx, project_id, user_ids, **kwargs):
        """Remove users from a project's rules."""
        return await self._pyinaturalist_endpoint(
            delete_project_users, ctx, project_id, user_ids, **kwargs
        )

    async def get_projects_by_id(self, ctx, project_id, **kwargs):
        """Get projects by id."""
        return await self._pyinaturalist_endpoint(
            get_projects_by_id, ctx, project_id, **kwargs
        )

    async def get_taxa_autocomplete(self, ctx, **kwargs):
        """Get taxa using autocomplete."""
        # - TODO: support user settings for home place, language
        return await self._pyinaturalist_endpoint(get_taxa_autocomplete, ctx, **kwargs)

    # end of pyinaturalist shims

    async def get_users(
        self, query: Union[int, str], refresh_cache=False, by_login_id=False, **kwargs
    ):
        """Get the users for the specified login, user_id, or query."""
        request = f"/v1/users/{query}"
        if isinstance(query, int) or query.isnumeric():
            user_id = int(query)
            key = user_id
        elif by_login_id:
            user_id = None
            key = query
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

    async def get_observers_from_projects(
        self, project_ids: Optional[List] = None, user_ids: Optional[List] = None
    ):
        """Get observers for a list of project ids.

        Since the cache is filled as a side effect, this method can be
        used to prime the cache prior to fetching multiple users at once
        by id.

        Users may also be specified, and in that case, project ids may be
        omitted. The cache will then be primed from a list of user ids.
        """
        if not (project_ids or user_ids):
            return

        page = 1
        more = True
        users = []
        # Note: This will only handle up to 10,000 users. Anything more
        # needs to set id_above and id_below. With luck, we won't ever
        # need to deal with projects this big!
        while more:
            params = {"page": page}
            if project_ids:
                params["project_id"] = ",".join(map(str, project_ids))
            if user_ids:
                params["user_id"] = ",".join(map(str, user_ids))
            response = await self.get_observations("observers", **params)
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
                        users.append(user)
                        self.users_cache[user_id] = user_json
                        self.users_login_cache[user["login"]] = user_id
            # default values provided defensively to exit loop if missing
            per_page = response.get("per_page") or len(results)
            total_results = response.get("total_results") or len(results)
            if results and (page * per_page < total_results):
                page += 1
            else:
                more = False

        # return all user results as a single page
        return {
            "total_results": len(users),
            "pages": 1,
            "per_page": len(users),
            "results": users,
        }
