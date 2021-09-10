"""Module to query iNat taxa."""
from redbot.core.commands import BadArgument

from .converters.base import NaturalQueryConverter
from .taxa import get_taxon, get_taxon_fields, match_taxon
from .core.models.taxon import RANK_EQUIVALENTS, RANK_LEVELS
from .core.query.query import Query, TaxonQuery


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
        taxon_query: TaxonQuery,
        ancestor_id: int = None,
        preferred_place_id: int = None,
        scientific_name: bool = False,
        locale: str = None,
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
        if taxon_query.taxon_id:
            response = await self.cog.api.get_taxa(taxon_query.taxon_id, **kwargs)
            if response:
                records = response.get("results")
            if records:
                taxon = match_taxon(taxon_query, list(map(get_taxon_fields, records)))
        else:
            kwargs["q"] = " ".join(taxon_query.terms)
            if taxon_query.ranks:
                kwargs["rank"] = ",".join(taxon_query.ranks)
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
                    taxon_query,
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
                raise LookupError("No matching taxon found.")

            raise LookupError(
                f"No {'exact ' if taxon_query.phrases else ''}match "
                f"found in {'scientific name of ' if scientific_name else ''}{records_read}"
                f" of {total_records} total records containing those terms."
            )

        return taxon

    async def maybe_match_taxon_compound(
        self,
        query: Query,
        preferred_place_id=None,
        scientific_name=False,
        locale=None,
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
                try:
                    taxon = await self.maybe_match_taxon(
                        query.main,
                        ancestor_id=ancestor.id,
                        preferred_place_id=preferred_place_id,
                        scientific_name=scientific_name,
                        locale=locale,
                    )
                except LookupError as err:
                    reason = (
                        str(err) + "\nPerhaps instead of `in` (ancestor), you meant\n"
                        "`from` (place) or `in prj` (project)?"
                    )
                    raise LookupError(reason) from err
        else:
            taxon = await self.maybe_match_taxon(
                query.main,
                preferred_place_id=preferred_place_id,
                scientific_name=scientific_name,
                locale=locale,
            )

        return taxon

    async def query_taxa(self, ctx, query):
        """Query for one or more taxa and return list of matching taxa, if any."""
        queries = query.split(",")

        # De-duplicate the query via dict:
        taxa = {}
        for query_str in queries:
            try:
                query = await NaturalQueryConverter.convert(ctx, query_str)
                query_response = await self.cog.query.get(ctx, query)
                if query_response.taxon:
                    taxon = query_response.taxon
                    taxa[str(taxon.id)] = taxon
            except (BadArgument, LookupError):
                pass

        result = taxa.values()
        if not result:
            raise LookupError("No taxon found")

        return result
