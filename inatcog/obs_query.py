"""Module to query iNat observations."""
from dronefly.core.query.query import Query
from pyinaturalist.models import Observation, Observations

from .utils import get_home


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def query_single_obs(self, ctx, query: Query):
        """Query observations and return first if found."""

        query_response = await self.cog.query.get(ctx, query)
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
