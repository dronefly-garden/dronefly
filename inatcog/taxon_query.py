"""Module to work with iNat taxa."""
from typing import Union
from redbot.core.commands import BadArgument
from .converters import ContextMemberConverter
from .parsers import TaxonQueryParser
from .taxa import get_taxon, get_taxon_fields, match_taxon
from .base_classes import CompoundQuery, FilteredTaxon, RANK_EQUIVALENTS, RANK_LEVELS

TAXON_QUERY_PARSER = TaxonQueryParser()


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

    async def maybe_match_taxon(self, query, ancestor_id=None):
        """Get taxon and return a match, if any."""
        if query.taxon_id:
            records = (await self.cog.api.get_taxa(query.taxon_id))["results"]
        else:
            kwargs = {}
            kwargs["q"] = " ".join(query.terms)
            if query.ranks:
                kwargs["rank"] = ",".join(query.ranks)
            if ancestor_id:
                kwargs["taxon_id"] = ancestor_id
            records = (await self.cog.api.get_taxa(**kwargs))["results"]

        if not records:
            raise LookupError("Nothing found")

        taxon = match_taxon(query, list(map(get_taxon_fields, records)))

        if not taxon:
            raise LookupError("No exact match")

        return taxon

    async def maybe_match_taxon_compound(self, compound_query):
        """Get one or more taxa and return a match, if any.

        Currently the grammar supports only one ancestor taxon
        and one child taxon.
        """
        query_main = compound_query.main
        query_ancestor = compound_query.ancestor
        if query_ancestor:
            ancestor = await self.maybe_match_taxon(query_ancestor)
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
                    query_main, ancestor_id=ancestor.taxon_id
                )
        else:
            taxon = await self.maybe_match_taxon(query_main)

        return taxon

    async def query_taxon(self, ctx, query: Union[str, CompoundQuery]):
        """Query for taxon and return single taxon if found."""
        if isinstance(query, str):
            compound_query = TAXON_QUERY_PARSER.parse(query)
        else:
            compound_query = query
        taxon = await self.maybe_match_taxon_compound(compound_query)
        place = None
        user = None

        if compound_query.user:
            try:
                who = await ContextMemberConverter.convert(ctx, compound_query.user)
            except BadArgument as err:
                raise LookupError(str(err))
            user = await self.cog.user_table.get_user(who.member)

        if compound_query.place:
            place = await self.cog.place_table.get_place(
                ctx.guild, compound_query.place, ctx.author
            )

        return FilteredTaxon(taxon, user, place, compound_query.group_by)

    async def query_taxa(self, query):
        """Query for one or more taxa and return list of matching taxa, if any."""
        queries = list(map(TAXON_QUERY_PARSER.parse, query.split(",")))
        # De-duplicate the query via dict:
        taxa = {}
        for compound_query in queries:
            try:
                taxon = await self.maybe_match_taxon_compound(compound_query)
                taxa[str(taxon.taxon_id)] = taxon
            except LookupError:
                pass

        result = taxa.values()
        if not result:
            raise LookupError("Nothing found")

        return result
