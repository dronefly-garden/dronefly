"""Module to query iNat taxa."""
import re
from redbot.core.commands import BadArgument
from .common import DEQUOTE
from .controlled_terms import ControlledTerm, match_controlled_term
from .converters import MemberConverter, NaturalQueryConverter
from .taxa import get_taxon, get_taxon_fields, match_taxon
from .base_classes import Query, QueryResponse, RANK_EQUIVALENTS, RANK_LEVELS

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


class INatTaxonQuery:
    """Query iNat for one or more taxa."""

    def __init__(self, cog):
        self.cog = cog

    async def get_taxon_ancestor(self, taxon, rank):
        """Get Taxon ancestor for specified rank from a Taxon object.

        Parameters
        ----------
        taxon: Taxon
            The taxon for which the ancestor at the specified rank is requested.
        rank: str
            The rank of the ancestor to return.

        Returns
        -------
        Taxon
            A Taxon object for the matching ancestor, if any, else None.
        """
        rank = RANK_EQUIVALENTS.get(rank) or rank
        if rank in taxon.ancestor_ranks:
            rank_index = taxon.ancestor_ranks.index(rank)
            ancestor = await get_taxon(self.cog, taxon.ancestor_ids[rank_index])
            return ancestor
        return None

    async def maybe_match_taxon(
        self,
        query,
        ancestor_id=None,
        preferred_place_id=None,
        scientific_name=False,
        locale=None,
    ):
        """Get taxon and return a match, if any."""
        kwargs = {}
        taxon = None
        records_read = 0
        total_records = 0

        if locale:
            kwargs["all_names"] = "true"
            kwargs["locale"] = locale
        if preferred_place_id:
            kwargs["preferred_place_id"] = int(preferred_place_id)
        if query.taxon_id:
            response = await self.cog.api.get_taxa(query.taxon_id, **kwargs)
            if response:
                records = response.get("results")
            if records:
                taxon = match_taxon(query, list(map(get_taxon_fields, records)))
        else:
            kwargs["q"] = " ".join(query.terms)
            if query.ranks:
                kwargs["rank"] = ",".join(query.ranks)
            if ancestor_id:
                kwargs["taxon_id"] = ancestor_id
            for page in range(11):
                if page == 0:
                    kwargs["per_page"] = 30
                else:
                    # restart numbering, as we are using a different endpoint
                    # now with different page size:
                    if page == 1:
                        records_read = 0
                    kwargs["page"] = page
                    kwargs["per_page"] = 200
                response = await self.cog.api.get_taxa(**kwargs)
                if response:
                    total_records = response.get("total_results") or 0
                    records = response.get("results")
                if not records:
                    break
                records_read += len(records)
                taxon = match_taxon(
                    query,
                    list(map(get_taxon_fields, records)),
                    scientific_name=scientific_name,
                    locale=locale,
                )
                if taxon:
                    break
                if records_read >= total_records:
                    break

        if not taxon:
            if records_read >= total_records:
                raise LookupError("No matching taxon found")

            raise LookupError(
                f"No {'exact ' if query.phrases else ''}match "
                f"found in {'scientific name of ' if scientific_name else ''}{records_read}"
                f" of {total_records} total records containing those terms."
            )

        return taxon

    async def maybe_match_taxon_compound(
        self, query: Query, preferred_place_id=None, scientific_name=False, locale=None,
    ):
        """Get one or more taxa and return a match, if any.

        Currently the grammar supports only one ancestor taxon
        and one child taxon.
        """
        if query.ancestor:
            ancestor = await self.maybe_match_taxon(
                query.ancestor,
                preferred_place_id=preferred_place_id,
                scientific_name=scientific_name,
                locale=locale,
            )
            if ancestor:
                if query.main.ranks:
                    max_query_rank_level = max(
                        [RANK_LEVELS[rank] for rank in query.main.ranks]
                    )
                    ancestor_rank_level = RANK_LEVELS[ancestor.rank]
                    if max_query_rank_level >= ancestor_rank_level:
                        raise LookupError(
                            "Child rank%s: `%s` must be below ancestor rank: `%s`"
                            % (
                                "s" if len(query.main.ranks) > 1 else "",
                                ",".join(query.main.ranks),
                                ancestor.rank,
                            )
                        )
                taxon = await self.maybe_match_taxon(
                    query.main,
                    ancestor_id=ancestor.taxon_id,
                    preferred_place_id=preferred_place_id,
                    scientific_name=scientific_name,
                    locale=locale,
                )
        else:
            taxon = await self.maybe_match_taxon(
                query.main,
                preferred_place_id=preferred_place_id,
                scientific_name=scientific_name,
                locale=locale,
            )

        return taxon

    async def query_taxon(self, ctx, query: Query, scientific_name=False, locale=None):
        """Query for taxon and return single taxon if found."""
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
            taxon = await self.maybe_match_taxon_compound(
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

    async def query_taxa(self, ctx, query):
        """Query for one or more taxa and return list of matching taxa, if any."""
        queries = query.split(",")

        # De-duplicate the query via dict:
        taxa = {}
        for query_str in queries:
            try:
                query = await NaturalQueryConverter.convert(ctx, query_str)
                query_response = await self.cog.taxon_query.query_taxon(ctx, query)
                if query_response.taxon:
                    taxon = query_response.taxon
                    taxa[str(taxon.taxon_id)] = taxon
            except (BadArgument, LookupError):
                pass

        result = taxa.values()
        if not result:
            raise LookupError("No taxon found")

        return result
