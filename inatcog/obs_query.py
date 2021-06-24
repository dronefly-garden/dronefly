"""Module to query iNat observations."""
from .core.query.query import Query
from .obs import get_obs_fields


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def query_single_obs(self, ctx, query: Query):
        """Query observations and return first if found."""

        query_response = await self.cog.query.get(ctx, query)
        kwargs = query_response.obs_args()
        kwargs["per_page"] = 1
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observation found {query_response.obs_query_description()}"
            )

        return get_obs_fields(response["results"][0])

    async def query_observations(self, ctx, query: Query):
        """Query observations and return iterator for any found."""

        query_response = await self.cog.query.get(ctx, query)
        kwargs = query_response.obs_args()
        kwargs["per_page"] = 200
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observations found {query_response.obs_query_description()}"
            )

        return (
            [get_obs_fields(result) for result in response["results"]],
            response["total_results"],
            response["per_page"],
        )
