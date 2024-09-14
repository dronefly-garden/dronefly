"""Module to query iNat taxa."""
from redbot.core.commands import BadArgument, Context
from dronefly.core.constants import RANK_EQUIVALENTS, RANK_LEVELS
from dronefly.core.formatters.generic import format_taxon_name
from dronefly.core.query.query import Query, TaxonQuery
from pyinaturalist.models import Taxon

from .converters.base import NaturalQueryConverter
from .taxa import get_taxon, match_taxon


class INatTaxonQuery:
    """Query iNat for one or more taxa."""

    def __init__(self, cog):
        self.cog = cog

    async def get_taxon_ancestor(self, ctx: Context, taxon, rank):
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

        def taxon_ancestor_ranks(taxon: Taxon):
            return (
                ["stateofmatter"] + [ancestor.rank for ancestor in taxon.ancestors]
                if taxon.ancestors
                else []
            )

        rank = RANK_EQUIVALENTS.get(rank) or rank
        ranks = taxon_ancestor_ranks(taxon)
        if rank in ranks:
            rank_index = ranks.index(rank)
            ancestor = await get_taxon(ctx, taxon.ancestor_ids[rank_index])
            return ancestor
        return None

    async def maybe_match_taxon(
        self,
        ctx: Context,
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
            kwargs["locale"] = locale
        if preferred_place_id:
            kwargs["preferred_place_id"] = int(preferred_place_id)
        if taxon_query.taxon_id:
            taxon = await get_taxon(ctx, taxon_query.taxon_id)
        else:
            if taxon_query.terms:
                kwargs["q"] = " ".join(taxon_query.terms)
            if taxon_query.ranks:
                kwargs["rank"] = ",".join(taxon_query.ranks)
            if ancestor_id:
                kwargs["taxon_id"] = ancestor_id
            for page in range(11):
                if page == 0:
                    per_page = 30
                    endpoint = ctx.inat_client.taxa.autocomplete
                else:
                    # restart numbering, as we are using a different endpoint
                    # now with different page size:
                    if page == 1:
                        records_read = 0
                    kwargs["page"] = page
                    per_page = 200
                    endpoint = ctx.inat_client.taxa.search
                kwargs["per_page"] = per_page
                paginator = endpoint(limit=per_page, **kwargs)
                if paginator:
                    records = await paginator.async_all()
                    total_records = paginator.count()
                if not records:
                    break
                records_read += len(records)
                taxon = match_taxon(
                    taxon_query,
                    records,
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
        ctx: Context,
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
            ancestor = None
            try:
                ancestor = await self.maybe_match_taxon(
                    ctx,
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
                        ctx,
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
                if ancestor:
                    reason = (
                        f"{reason}\n\n"
                        f"Ancestor taxon: {format_taxon_name(ancestor, with_term=True)}"
                    )
                else:
                    reason = f"{reason}\n\nAncestor taxon not found."
                raise LookupError(reason) from err
        else:
            taxon = await self.maybe_match_taxon(
                ctx,
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
        missing_taxa = []
        for query_str in queries:
            try:
                query = await NaturalQueryConverter.convert(ctx, query_str)
                query_response = await self.cog.query.get(ctx, query)
                if query_response.taxon:
                    taxon = query_response.taxon
                    taxa[str(taxon.id)] = taxon
            except (BadArgument, LookupError):
                missing_taxa.append(query_str)
                pass

        result = taxa.values()
        if not result:
            raise LookupError("No taxon found")

        return (result, missing_taxa)

    async def query_paginated_taxa(self, ctx, query):
        """Query for one or more taxa and return paginator for matching taxa, if any.

        Notes:

        - In its original conception, this was used only for comma-delimited
          lists of taxon queries for map & related, or a list of taxon ancestor
          IDs. These had a small, definite number of elements (whatever the user
          typed, or all the ancestors of a taxon), were de-duplicated, and
          didn't need to be paginated.

        - We want to go one step further here and return multiple taxa, whether or
          not multiple were given as input:

            - The return is then a paginator for all matching taxa.
            - Which may be filtered in some fashion, e.g.
                - All taxa matching the supplied name(s).
                - For a given rank keyword.
            - And if there are no filters, then just all results matching the
              query.

        - The "rank" filter is baked into maybe_match_taxon_compound (I think)
          and needs to be pulled out of that.

            - In fact, most of that relates to selecting "one best" match,
              so really isn't needed here.
        """
        queries = query.split(",")

        async def _get_taxon(query):
            # TODO: extract from the following whatever logic applies
            # to our taxon search and redo in a more modular way:
            # - components:
            #   - matchers (phrases, AOU codes, etc.)
            #   - scorers (point values for exact / inexact, etc.)
            #   - a filter (the `in` clause for parent taxon)
            # - reassemble those components to implement the logic described
            #   above, and especially the scorer has to be abandoned unless
            #   the whole result set is fully enumerated (can't be done
            #   efficiently with an arbitrary result set! might work for
            #   single "root" taxon for `in` though)
            return await self.cog.taxon_query.maybe_match_taxon_compound(ctx, query)

        # De-duplicate the query via dict:
        taxa = {}
        for query_str in queries:
            try:
                _query = await NaturalQueryConverter.convert(ctx, query_str)
                taxon = await _get_taxon(_query)
                if taxon:
                    taxa[str(taxon.id)] = taxon
            except (BadArgument, LookupError):
                pass

        result = taxa.values()
        if not result:
            raise LookupError("No taxon found")

        return result
