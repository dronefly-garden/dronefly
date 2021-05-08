"""Module to query iNat observations."""
from .base_classes import CompoundQuery
from .controlled_terms import ControlledTerm, match_controlled_term
from .obs import get_obs_fields
from .taxa import format_taxon_name


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    def format_query_args(self, filtered_taxon, term=None, value=None):
        """Format query into a human-readable string"""
        message = ""
        if filtered_taxon.taxon:
            message += " of " + format_taxon_name(filtered_taxon.taxon, with_term=True)
        if filtered_taxon.project:
            message += " in " + filtered_taxon.project.title
        if filtered_taxon.place:
            message += " from " + filtered_taxon.place.display_name
        if filtered_taxon.user:
            message += " by " + filtered_taxon.user.display_name()
        if filtered_taxon.unobserved_by:
            message += " unobserved by " + filtered_taxon.unobserved_by.display_name()
        if filtered_taxon.id_by:
            message += " identified by " + filtered_taxon.id_by.display_name()
        if term:
            if value:
                message += f" with {term.label} {value.label}"
            else:
                message += f" with {term.label}"
        return message

    async def get_query_args(self, ctx, query: CompoundQuery):
        """Get arguments for observation query from query string."""
        kwargs = {}
        term = None
        value = None
        filtered_taxon = await self.cog.taxon_query.query_taxon(ctx, query)
        if filtered_taxon:
            if filtered_taxon.taxon:
                kwargs["taxon_id"] = filtered_taxon.taxon.taxon_id
            if filtered_taxon.user:
                kwargs["user_id"] = filtered_taxon.user.user_id
            if filtered_taxon.project:
                kwargs["project_id"] = filtered_taxon.project.project_id
            if filtered_taxon.place:
                kwargs["place_id"] = filtered_taxon.place.place_id
            if filtered_taxon.unobserved_by:
                kwargs["unobserved_by_user_id"] = filtered_taxon.unobserved_by.user_id
                kwargs["lrank"] = "species"
            if filtered_taxon.id_by:
                kwargs["ident_user_id"] = filtered_taxon.id_by.user_id
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
        return kwargs, filtered_taxon, term, value

    async def query_single_obs(self, ctx, query: CompoundQuery):
        """Query observations and return first if found."""

        kwargs, filtered_taxon, term, value = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 1
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observation found {self.format_query_args(filtered_taxon, term, value)}"
            )

        return get_obs_fields(response["results"][0])

    async def query_observations(self, ctx, query: CompoundQuery):
        """Query observations and return iterator for any found."""

        kwargs, filtered_taxon, term, value = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 200
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observations found {self.format_query_args(filtered_taxon, term, value)}"
            )

        return (
            [get_obs_fields(result) for result in response["results"]],
            response["total_results"],
            response["per_page"],
        )
