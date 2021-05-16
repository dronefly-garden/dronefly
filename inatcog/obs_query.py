"""Module to query iNat observations."""
import re

from .base_classes import Query
from .obs import get_obs_fields
from .taxa import format_taxon_name

VALID_OBS_OPTS = [
    "captive",
    "endemic",
    "iconic_taxa",
    "identified",
    "introduced",
    "native",
    "out_of_range",
    "pcid",
    "photos",
    "popular",
    "sounds",
    "threatened",
    "verifiable",
    "id",
    "not_id",
    "quality_grade",
    "reviewed",
    "page",
    "order",
    "order_by",
    "without_taxon_id",
]


class INatObsQuery:
    """Query iNat for one or more observation."""

    def __init__(self, cog):
        self.cog = cog

    def format_query_args(self, query_response):
        """Format query into a human-readable string"""
        message = ""
        if query_response.taxon:
            message += " of " + format_taxon_name(query_response.taxon, with_term=True)
        if query_response.project:
            message += " in " + query_response.project.title
        if query_response.place:
            message += " from " + query_response.place.display_name
        if query_response.user:
            message += " by " + query_response.user.display_name()
        if query_response.unobserved_by:
            message += " unobserved by " + query_response.unobserved_by.display_name()
        if query_response.id_by:
            message += " identified by " + query_response.id_by.display_name()
        if query_response.controlled_term:
            (term, term_value) = query_response.controlled_term
            desc = f" with {term.label}"
            desc += f" {term_value.label}"
            message += desc
        return message

    async def get_query_args(self, ctx, query: Query):
        """Get arguments for observation query from query string."""
        kwargs = {}
        term = None
        term_value = None
        query_response = await self.cog.taxon_query.query_taxon(ctx, query)
        if query_response:
            if query_response.taxon:
                kwargs["taxon_id"] = query_response.taxon.taxon_id
            if query_response.user:
                kwargs["user_id"] = query_response.user.user_id
            if query_response.project:
                kwargs["project_id"] = query_response.project.project_id
            if query_response.place:
                kwargs["place_id"] = query_response.place.place_id
            if query_response.unobserved_by:
                kwargs["unobserved_by_user_id"] = query_response.unobserved_by.user_id
                kwargs["lrank"] = "species"
            if query_response.id_by:
                kwargs["ident_user_id"] = query_response.id_by.user_id
            if query_response.controlled_term:
                (term, term_value) = query_response.controlled_term
                kwargs["term_id"] = term.id
                kwargs["term_value_id"] = term_value.id
        kwargs["verifiable"] = "any"
        if query.options:
            # Accept a limited selection of observation options:
            # - all options and values are lowercased
            for (key, *val) in map(lambda opt: opt.lower().split("="), query.options):
                val = val[0] if val else "true"
                # - conservatively, only alphanumeric, comma, dash or
                #   underscore characters accepted in values so far
                # - TODO: proper validation per field type
                if key in VALID_OBS_OPTS and re.match(r"^[a-z0-9,_-]*$", val):
                    kwargs[key] = val

        return kwargs, query_response

    async def query_single_obs(self, ctx, query: Query):
        """Query observations and return first if found."""

        kwargs, query_response = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 1
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observation found {self.format_query_args(query_response)}"
            )

        return get_obs_fields(response["results"][0])

    async def query_observations(self, ctx, query: Query):
        """Query observations and return iterator for any found."""

        kwargs, query_response = await self.get_query_args(ctx, query)
        kwargs["per_page"] = 200
        home = await self.cog.get_home(ctx)
        kwargs["preferred_place_id"] = home
        response = await self.cog.api.get_observations(**kwargs)
        if not response["results"]:
            raise LookupError(
                f"No observations found {self.format_query_args(query_response)}"
            )

        return (
            [get_obs_fields(result) for result in response["results"]],
            response["total_results"],
            response["per_page"],
        )
