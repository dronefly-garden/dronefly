"""Module to query iNat."""
import re
from redbot.core.commands import BadArgument, Context
from .common import DEQUOTE
from .controlled_terms import ControlledTerm, match_controlled_term
from .converters import MemberConverter
from .base_classes import Query, QueryResponse

VALID_OBS_OPTS = [
    "captive",
    "created_d1",
    "created_d2",
    "created_on",
    "day",
    "d1",
    "d2",
    "endemic",
    "iconic_taxa",
    "id",
    "identified",
    "introduced",
    "month",
    "native",
    "not_id",
    "observed_on",
    "order",
    "order_by",
    "out_of_range",
    "page",
    "pcid",
    "photos",
    "popular",
    "quality_grade",
    "reviewed",
    "sounds",
    "threatened",
    "verifiable",
    "without_taxon_id",
    "year",
]


def _get_options(query_options: list):
    options = {}
    # Accept a limited selection of options:
    # - all of these to date apply only to observations, though others could
    #   be added later
    # - all options and values are lowercased
    for (key, *val) in map(lambda opt: opt.lower().split("="), query_options):
        val = val[0] if val else "true"
        # - conservatively, only alphanumeric, comma, dash or
        #   underscore characters accepted in values so far
        # - TODO: proper validation per field type
        if key in VALID_OBS_OPTS and re.match(r"^[a-z0-9,_-]*$", val):
            options[key] = val
    return options


class INatQuery:
    """Query iNat for all requested entities."""

    def __init__(self, cog):
        self.cog = cog

    async def _get_user(self, ctx: Context, user: str):
        try:
            who = await MemberConverter.convert(ctx, re.sub(DEQUOTE, r"\1", user))
        except BadArgument as err:
            raise LookupError(str(err)) from err
        user = await self.cog.user_table.get_user(who.member)
        return user

    async def _get_controlled_term(self, query_term: str, query_term_value: str):
        controlled_terms_dict = await self.cog.api.get_controlled_terms()
        controlled_terms = [
            ControlledTerm.from_dict(term, infer_missing=True)
            for term in controlled_terms_dict["results"]
        ]
        controlled_term = match_controlled_term(
            controlled_terms, query_term, query_term_value
        )
        return controlled_term

    async def get(self, ctx: Context, query: Query, scientific_name=False, locale=None):
        """Get all requested iNat entities."""
        args = {}

        preferred_place_id = await self.cog.get_home(ctx)
        args["project"] = (
            await self.cog.project_table.get_project(ctx.guild, query.project)
            if query.project
            else None
        )
        args["place"] = (
            await self.cog.place_table.get_place(ctx.guild, query.place, ctx.author)
            if query.place
            else None
        )
        if args["place"]:
            preferred_place_id = args["place"].place_id
        args["taxon"] = (
            await self.cog.taxon_query.maybe_match_taxon_compound(
                query,
                preferred_place_id=preferred_place_id,
                scientific_name=scientific_name,
                locale=locale,
            )
            if query.main
            else None
        )
        args["user"] = await self._get_user(ctx, query.user) if query.user else None
        args["unobserved_by"] = (
            await self._get_user(ctx, query.unobserved_by)
            if query.unobserved_by
            else None
        )
        args["id_by"] = await self._get_user(ctx, query.id_by) if query.id_by else None
        args["controlled_term"] = (
            await self._get_controlled_term(ctx, *query.controlled_term)
            if query.controlled_term
            else None
        )
        args["options"] = _get_options(query.options) if query.options else None

        return QueryResponse(**args)
