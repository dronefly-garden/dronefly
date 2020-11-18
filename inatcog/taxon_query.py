"""Module to query iNat taxa."""
import re
from redbot.core.commands import BadArgument
from .common import DEQUOTE
from .converters import ContextMemberConverter, NaturalCompoundQueryConverter
from .taxa import get_taxon, get_taxon_fields, match_taxon
from .base_classes import CompoundQuery, FilteredTaxon, RANK_EQUIVALENTS, RANK_LEVELS


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

    async def maybe_match_taxon(self, query, ancestor_id=None, preferred_place_id=None):
        """Get taxon and return a match, if any."""
        kwargs = {}
        if preferred_place_id:
            kwargs["preferred_place_id"] = int(preferred_place_id)
        if query.taxon_id:
            records = (await self.cog.api.get_taxa(query.taxon_id, **kwargs))["results"]
        else:
            kwargs["q"] = " ".join(query.terms)
            if query.ranks:
                kwargs["rank"] = ",".join(query.ranks)
            if ancestor_id:
                kwargs["taxon_id"] = ancestor_id
            records = (await self.cog.api.get_taxa(**kwargs))["results"]

        if not records:
            raise LookupError("No matching taxon found")

        taxon = match_taxon(query, list(map(get_taxon_fields, records)))

        if not taxon:
            raise LookupError("No exact match")

        return taxon

    async def maybe_match_taxon_compound(self, compound_query, preferred_place_id=None):
        """Get one or more taxa and return a match, if any.

        Currently the grammar supports only one ancestor taxon
        and one child taxon.
        """
        query_main = compound_query.main
        query_ancestor = compound_query.ancestor
        if query_ancestor:
            ancestor = await self.maybe_match_taxon(
                query_ancestor, preferred_place_id=preferred_place_id
            )
            if ancestor:
                if query_main.ranks:
                    max_query_rank_level = max(
                        [RANK_LEVELS[rank] for rank in query_main.ranks]
                    )
                    ancestor_rank_level = RANK_LEVELS[ancestor.rank]
                    if max_query_rank_level >= ancestor_rank_level:
                        raise LookupError(
                            "Child rank%s: `%s` must be below ancestor rank: `%s`"
                            % (
                                "s" if len(query_main.ranks) > 1 else "",
                                ",".join(query_main.ranks),
                                ancestor.rank,
                            )
                        )
                taxon = await self.maybe_match_taxon(
                    query_main,
                    ancestor_id=ancestor.taxon_id,
                    preferred_place_id=preferred_place_id,
                )
        else:
            taxon = await self.maybe_match_taxon(
                query_main, preferred_place_id=preferred_place_id
            )

        return taxon

    async def query_taxon(self, ctx, query: CompoundQuery):
        """Query for taxon and return single taxon if found."""
        taxon = None
        place = None
        user = None
        unobserved_by = None
        preferred_place_id = await self.cog.get_home(ctx)
        if query.place:
            place = await self.cog.place_table.get_place(
                ctx.guild, query.place, ctx.author
            )
        if place:
            preferred_place_id = place.place_id
        if query.main:
            taxon = await self.maybe_match_taxon_compound(
                query, preferred_place_id=preferred_place_id
            )
        if query.user:
            try:
                who = await ContextMemberConverter.convert(
                    ctx, re.sub(DEQUOTE, r"\1", query.user)
                )
            except BadArgument as err:
                raise LookupError(str(err))
            user = await self.cog.user_table.get_user(who.member)
        if query.unobserved_by:
            try:
                who = await ContextMemberConverter.convert(
                    ctx, re.sub(DEQUOTE, r"\1", query.unobserved_by)
                )
            except BadArgument as err:
                raise LookupError(str(err))
            unobserved_by = await self.cog.user_table.get_user(who.member)
        return FilteredTaxon(taxon, user, place, unobserved_by)

    async def query_taxa(self, ctx, query):
        """Query for one or more taxa and return list of matching taxa, if any."""
        queries = query.split(",")

        # De-duplicate the query via dict:
        taxa = {}
        for query_str in queries:
            try:
                query = await NaturalCompoundQueryConverter.convert(ctx, query_str)
                filtered_taxon = await self.cog.taxon_query.query_taxon(ctx, query)
                if filtered_taxon.taxon:
                    taxon = filtered_taxon.taxon
                    taxa[str(taxon.taxon_id)] = taxon
            except (BadArgument, LookupError):
                pass

        result = taxa.values()
        if not result:
            raise LookupError("No taxon found")

        return result
