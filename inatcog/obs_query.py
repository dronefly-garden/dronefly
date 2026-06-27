"""Module to query iNat observations."""
from dronefly.core.query.query import (
    Query,
    prepare_query_for_single_obs,
    prepare_query_for_search_obs,
)
from pyinaturalist.models import Observation, Observations
from redbot.core.commands import BadArgument

from .utils import get_home


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def query_single_obs(self, ctx, query: Query):
        """Query observations and return first if found."""

        try:
            query_response = await prepare_query_for_single_obs(ctx.inat_client, query)
        except ValueError as err:
            raise BadArgument(str(err)) from err
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

        try:
            query_response = await prepare_query_for_search_obs(ctx.inat_client, query)
        except ValueError as err:
            raise BadArgument(str(err)) from err
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
