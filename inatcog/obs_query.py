"""Module to query iNat observations."""
from dronefly.core.query.query import Query, QueryResponse
from dronefly.core.parsers.constants import VALID_OBS_SORT_BY
from pyinaturalist.models import Observation, Observations
from redbot.core.commands import BadArgument

from .utils import get_home


def _check_obs_query_fields(query_response: QueryResponse):
    sort_by = query_response.sort_by
    if sort_by is not None and sort_by not in VALID_OBS_SORT_BY:
        raise BadArgument(
            f"Invalid `sort by`. Must be one of: `{', '.join(VALID_OBS_SORT_BY.keys())}`"
        )


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def query_single_obs(self, ctx, query: Query):
        """Query observations and return first if found."""

        query_response = await self.cog.query.get(ctx, query)
        _check_obs_query_fields(query_response)
        kwargs = query_response.obs_args()
        kwargs["per_page"] = 1
        home = await get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observation found {query_response.obs_query_description()}"
            )

        return Observation.from_json(response["results"][0])

    async def query_observations(self, ctx, query: Query, page=1):
        """Query observations and return iterator for any found."""

        query_response = await self.cog.query.get(ctx, query)
        _check_obs_query_fields(query_response)
        kwargs = query_response.obs_args()
        kwargs["per_page"] = 200
        kwargs["page"] = page
        home = await get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observations found {query_response.obs_query_description()}"
            )

        return (
            Observations.from_json(response),
            response["total_results"],
            response["per_page"],
        )
