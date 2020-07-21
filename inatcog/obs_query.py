"""Module to query iNat observations."""
from typing import Union
from .base_classes import CompoundQuery
from .controlled_terms import ControlledTerm, match_controlled_term
from .obs import get_obs_fields


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def get_query_args(self, ctx, query: Union[CompoundQuery, str]):
        """Get arguments for observation query from query string."""
        kwargs = {}
        filtered_taxon = await self.cog.taxon_query.query_taxon(ctx, query)
        if filtered_taxon:
            if filtered_taxon.taxon:
                kwargs["taxon_id"] = filtered_taxon.taxon.taxon_id
            if filtered_taxon.user:
                kwargs["user_id"] = filtered_taxon.user.user_id
            if filtered_taxon.place:
                kwargs["place_id"] = filtered_taxon.place.place_id
        if query.controlled_term:
            query_term, query_value = query.controlled_term
            controlled_terms_dict = await self.cog.api.get_controlled_terms()
            controlled_terms = [
                ControlledTerm.from_dict(term, infer_missing=True)
                for term in controlled_terms_dict["results"]
            ]
            (term, value) = match_controlled_term(
                controlled_terms, query_term, query_value
            )
            kwargs["term_id"] = term.id
            kwargs["term_value_id"] = value.id
        kwargs["verifiable"] = "any"
        kwargs["include_new_projects"] = 1
        return kwargs, filtered_taxon

    async def query_single_obs(self, ctx, query: Union[CompoundQuery, str]):
        """Query observations and return first if found."""

        kwargs, _taxon = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 1
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError("No observation found")

        return get_obs_fields(response["results"][0])

    async def query_observations(self, ctx, query: Union[CompoundQuery, str]):
        """Query observations and return iterator for any found."""

        kwargs, _taxon = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 200
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError("No observations found")

        return (
            [get_obs_fields(result) for result in response["results"]],
            response["total_results"],
            response["per_page"],
        )
