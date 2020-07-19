"""Module to query iNat observations."""
from typing import Union
from .base_classes import CompoundQuery
from .controlled_terms import ControlledTerm, match_controlled_term
from .obs import get_obs_fields


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    async def query_single_obs(self, ctx, query: Union[CompoundQuery, str]):
        """Query observations and return best matching (usually most recent) if found."""
        kwargs = {}
        filtered_taxon = await self.cog.taxon_query.query_taxon(ctx, query)
        ctx.send(repr(query))
        ctx.send(repr(filtered_taxon))
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

        observations_results = await self.cog.api.get_observations(**kwargs)
        if not observations_results["results"]:
            raise LookupError("Nothing found")

        return get_obs_fields(observations_results["results"][0])
