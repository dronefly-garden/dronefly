"""Module to query iNat."""
import re
from redbot.core.commands import BadArgument
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


class INatQuery:
    """Query iNat for all requested entities."""

    def __init__(self, cog):
        self.cog = cog

    async def get(self, ctx, query: Query, scientific_name=False, locale=None):
        """Get all requested iNat entities."""
        taxon = None
        place = None
        user = None
        unobserved_by = None
        id_by = None
        project = None
        controlled_term = None
        options = {}
        preferred_place_id = await self.cog.get_home(ctx)
        if query.project:
            project = await self.cog.project_table.get_project(ctx.guild, query.project)
        if query.place:
            place = await self.cog.place_table.get_place(
                ctx.guild, query.place, ctx.author
            )
        if place:
            preferred_place_id = place.place_id
        if query.main:
            taxon = await self.cog.taxon_query.maybe_match_taxon_compound(
                query,
                preferred_place_id=preferred_place_id,
                scientific_name=scientific_name,
                locale=locale,
            )
        if query.user:
            try:
                who = await MemberConverter.convert(
                    ctx, re.sub(DEQUOTE, r"\1", query.user)
                )
            except BadArgument as err:
                raise LookupError(str(err)) from err
            user = await self.cog.user_table.get_user(who.member)
        if query.unobserved_by:
            try:
                who = await MemberConverter.convert(
                    ctx, re.sub(DEQUOTE, r"\1", query.unobserved_by)
                )
            except BadArgument as err:
                raise LookupError(str(err)) from err
            unobserved_by = await self.cog.user_table.get_user(who.member)
        if query.id_by:
            try:
                who = await MemberConverter.convert(
                    ctx, re.sub(DEQUOTE, r"\1", query.id_by)
                )
            except BadArgument as err:
                raise LookupError(str(err)) from err
            id_by = await self.cog.user_table.get_user(who.member)
        if query.controlled_term:
            (query_term, query_term_value) = query.controlled_term
            controlled_terms_dict = await self.cog.api.get_controlled_terms()
            controlled_terms = [
                ControlledTerm.from_dict(term, infer_missing=True)
                for term in controlled_terms_dict["results"]
            ]
            controlled_term = match_controlled_term(
                controlled_terms, query_term, query_term_value
            )
        if query.options:
            # Accept a limited selection of options:
            # - all of these to date apply only to observations, though others could
            #   be added later
            # - all options and values are lowercased
            for (key, *val) in map(lambda opt: opt.lower().split("="), query.options):
                val = val[0] if val else "true"
                # - conservatively, only alphanumeric, comma, dash or
                #   underscore characters accepted in values so far
                # - TODO: proper validation per field type
                if key in VALID_OBS_OPTS and re.match(r"^[a-z0-9,_-]*$", val):
                    options[key] = val

        return QueryResponse(
            taxon=taxon,
            user=user,
            place=place,
            unobserved_by=unobserved_by,
            id_by=id_by,
            project=project,
            options=options,
            controlled_term=controlled_term,
        )
