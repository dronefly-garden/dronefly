"""Module for taxon command group."""

import contextlib
from contextlib import asynccontextmanager
import re
import textwrap
from typing import List, Optional

import discord
from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.formatters.generic import (
    format_taxon_name,
    format_taxon_establishment_means,
)
from dronefly.core.constants import RANKS_FOR_LEVEL, RANK_KEYWORDS, TRACHEOPHYTA_ID
from dronefly.core.formatters.generic import TaxonListFormatter
from dronefly.core.query import QueryResponse, prepare_query_for_taxon
from dronefly.core.query.formatters import get_query_taxon_formatter
from dronefly.discord.embeds import make_embed, MAX_EMBED_DESCRIPTION_LEN
from dronefly.discord.menus import (
    TaxonListMenu,
    TaxonListSource,
    TaxonMenu,
    TaxonSource,
)
from pyinaturalist import RANK_EQUIVALENTS, RANK_LEVELS
from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from ..converters.reply import EmptyArgument, TaxonReplyConverter
from ..embeds.common import (
    add_reactions_with_cancel,
    apologize,
)
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..taxa import get_taxon
from ..utils import get_lang, use_client

BOLD_BASE_URL = "http://www.boldsystems.org/index.php"


class CommandsTaxon(INatEmbeds, MixinMeta):
    """Mixin providing taxon command group."""

    @asynccontextmanager
    async def _get_taxon_response(
        self, ctx, query: Optional[str], ranks: Optional[List[str]] = None, **kwargs
    ):
        """Yield a query_response for one or more taxa and related info."""
        query_response = None
        _query = None
        try:
            _query = await TaxonReplyConverter.convert(ctx, query)
            if ranks:
                _ranks = _query.main.ranks or []
                _ranks.extend(ranks)
                _query.main.ranks = _ranks
            self.check_taxon_query(ctx, _query)
            query_response = await prepare_query_for_taxon(
                ctx.inat_client, _query, **kwargs
            )
            if not query_response.per:
                if query_response.user:
                    query_response.per = "obs"
                elif query_response.place:
                    query_response.per = "place"
                else:
                    query_response.per = "obs"
        except EmptyArgument:
            await ctx.send_help()
        except (BadArgument, LookupError, ValueError) as err:
            await apologize(ctx, str(err))

        yield query_response, _query

    async def _start_taxon_menu(
        self,
        ctx,
        query_response,
        image_number: int = None,
        related_embed: discord.Embed = None,
    ):
        async def get_taxon_formatter():
            """Populate taxon formatter with iNat entities supplying additional details."""
            formatter_params = {
                "lang": ctx.inat_client.ctx.get_inat_user_default("inat_lang"),
                "max_len": MAX_EMBED_DESCRIPTION_LEN,
                "with_url": False,
            }
            if image_number is not None:
                formatter_params["image_number"] = image_number
                formatter_params["image_description"] = ""
            return await get_query_taxon_formatter(
                ctx.inat_client,
                query_response,
                **formatter_params,
            )

        taxon_formatter = await get_taxon_formatter()
        for_place = query_response.per == "place"
        await TaxonMenu(
            source=TaxonSource(taxon_formatter),
            inat_client=ctx.inat_client,
            for_place=for_place,
            related_embed=related_embed,
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=0,
            cog=self,
        ).start(ctx=ctx)

    @commands.hybrid_group(aliases=["t"], fallback="show")
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def taxon(self, ctx, *, query: Optional[str]):
        """Taxon information.

        - *Taxon query terms* match a single taxon to display.
        - *Observation query terms* match observation filters.
        - *Reply* to another display to display its taxon.
        - The *query* is optional when that display contains a taxon.
        **Related help topics:**
        - `[p]taxon_query` for *taxon query* terms
        - `[p]query` for help with other *query* terms
        - `[p]reactions` describes the *reaction buttons*
        - `[p]help s taxa` to search and browse matching taxa
        """

        error_msg = None
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if not query_response:
                return
            try:
                await self._start_taxon_menu(ctx, query_response)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)

    @taxon.command(name="list")
    @use_client
    async def taxon_list(self, ctx, *, query: Optional[str]):
        """List a taxon's children.

        • *Taxon query terms* match a single taxon to display.
        • Use `per <rank>` to show descendant taxon at that rank's level; `per child` is the default.
        • *Reply* to another display to display its taxon.
        • The *query* is optional when that display contains a taxon.
        **Related help topics:**
        • `[p]taxon_query` for *taxon query* terms
        • `[p]help s taxa` to search and browse matching taxa
        """  # noqa: E501
        error_msg = None
        msg = None
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if not query_response:
                return
            try:
                per_rank = _query.per or "child"
                if per_rank not in [*RANK_KEYWORDS, "child"]:
                    raise BadArgument(
                        "Specify `per <rank-or-keyword>`. "
                        f"See `{ctx.clean_prefix}help taxon list` for details."
                    )
                taxon = query_response.taxon
                if not taxon.children:
                    taxon = await ctx.inat_client.taxa.populate(taxon, refresh=True)
                if not taxon.children:
                    raise LookupError(f"{taxon.name} has no child taxa")
                taxon_list = [
                    taxon,
                    *[_taxon for _taxon in taxon.children if _taxon.is_active],
                ]
                per_page = 10
                sort_by = _query.sort_by or None
                _per_rank = per_rank
                if per_rank != "child":
                    _per_rank = RANK_EQUIVALENTS.get(per_rank) or per_rank
                    rank_level = RANK_LEVELS[_per_rank]
                    if rank_level >= taxon.rank_level:
                        raise BadArgument(
                            f"The rank `{per_rank}` is not lower than "
                            f"the taxon rank: `{taxon.rank}`."
                        )
                    _children = [
                        child for child in taxon_list if child.rank_level == rank_level
                    ]
                    _without_rank_ids = [
                        child.id for child in taxon_list if child not in _children
                    ]
                    if len(_without_rank_ids) > 0:
                        # One chance at retrieving the remaining children, i.e. if the
                        # remainder (direct children - those at the specified rank level)
                        # don't constitute a single page of results, then show children
                        # instead.
                        async with ctx.typing():
                            _descendants = await ctx.inat_client.taxa.search(
                                taxon_id=_without_rank_ids,
                                rank_level=rank_level,
                                is_active=True,
                                per_page=500,
                            )
                            # The choice of 2500 as our limit is arbitrary:
                            # - will take 5 more API calls to satisfy
                            # - encompasses the largest genera (e.g. Astragalus)
                            # - meant to limit unreasonable sized queries so they don't make
                            #   excessive API demands
                            # - TODO: switch to using a local DB built from full taxonomy dump
                            #   so we can lift this restriction
                            if _descendants.count() > 2500:
                                short_description = "Children"
                                await ctx.send(
                                    f"Too many {self.p.plural(_per_rank)}. "
                                    "Listing children instead."
                                )
                                _per_rank = "child"
                            else:
                                taxon_list = [
                                    taxon,
                                    *_children,
                                    *(await _descendants.async_all()),
                                ]
                if _per_rank == "child":
                    short_description = "Children"
                else:
                    short_description = self.p.plural(_per_rank).capitalize()
                    # List all ranks at the same level, not just the specified rank
                    _per_rank = RANKS_FOR_LEVEL[rank_level]
                order = _query.order or None
                taxon_list_formatter = TaxonListFormatter(
                    with_taxa=True,
                    short_description=short_description,
                )
                source = TaxonListSource(
                    entries=taxon_list,
                    query_response=query_response,
                    formatter=taxon_list_formatter,
                    per_page=per_page,
                    per_rank=_per_rank,
                    sort_by=sort_by,
                    order=order,
                )
                await TaxonListMenu(
                    source=source,
                    delete_message_after=False,
                    clear_reactions_after=True,
                    timeout=60,
                    cog=self,
                    page_start=0,
                ).start(ctx=ctx)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)
        else:
            if msg:
                await add_reactions_with_cancel(ctx, msg, [])

    @taxon.command(name="map")
    async def taxon_map(self, ctx, *, taxa_list):
        """Show range map for one or more taxa."""
        await (self.bot.get_command("map")(ctx, taxa_list=taxa_list))

    @taxon.command(name="search")
    async def taxon_search(self, ctx, *, query):
        """Search for matching taxa."""
        await (self.bot.get_command("search taxa")(ctx, query=query))

    @taxon.command()
    @use_client
    async def bonap(self, ctx, *, query: Optional[str]):
        """North American flora info from bonap.net."""
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                base_taxon_map_url = "https://bonap.net/MapGallery/County/"
                base_species_maps_url = "https://bonap.net/NAPA/TaxonMaps/Genus/County/"
                taxon = ctx.inat_client.taxa(
                    query_response.taxon.id, refresh=True, all_names=True
                )
                name = taxon.name
                lang = await get_lang(ctx)
                full_name = format_taxon_name(taxon, lang=lang)
                if TRACHEOPHYTA_ID not in taxon.ancestor_ids:
                    msg = await ctx.send(
                        f"{full_name} is not in Tracheophyta (Vascular Plants)"
                    )
                    await add_reactions_with_cancel(ctx, msg, [])
                    return

                if taxon.rank not in ("genus", "species"):
                    msg = await ctx.send(
                        f"{full_name} must be a genus or species, not: {taxon.rank}"
                    )
                    await add_reactions_with_cancel(ctx, msg, [])
                    return

                # Find first map at bonap.net for current valid name, or if not
                # found, then any invalid name for the same taxon.
                taxon_map_url = None
                taxon_names = [
                    name,
                    *(
                        name["name"]
                        for name in taxon.names
                        if name.get("lexicon") == "scientific-names"
                        and not name.get("is_valid")
                    ),
                ]
                _name = name
                _full_name = full_name
                found = False
                while not found and taxon_names:
                    name = taxon_names.pop(0)
                    _rank = "Genus/" if taxon.rank == "genus" else ""
                    taxon_map_url = (
                        f"{base_taxon_map_url}{_rank}{re.sub(r' ', '%20', name)}.png"
                    )
                    resp = await self.api.session.head(
                        taxon_map_url, raise_for_status=False
                    )
                    if resp.status == 200:
                        if name != _name:
                            full_name = (
                                f"{_full_name} replaces *{name}* (no longer valid)"
                            )
                        found = True
                    elif resp.status == 404:
                        # i.e. valid name not found, but bonap may know it by an invalid name
                        if taxon_names:
                            continue
                    else:
                        await apologize(
                            ctx, f"bonap.net not responding (Error {resp.status})"
                        )
                        return
                if not found:
                    await apologize(ctx, f"{_full_name} not found at bonap.net")
                    return

                if taxon.rank == "genus":
                    species_maps_url = base_species_maps_url + name
                    msg = await ctx.send(
                        (
                            f"{full_name} species maps: {species_maps_url}\n"
                            f"Map for: {full_name}\n{taxon_map_url}"
                        )
                    )
                else:  # i.e. species
                    msg = await ctx.send(f"Map for: {full_name}\n{taxon_map_url}")
                cancelled = await (self.bot.get_command("tabulate")(ctx, query=_query))
                if cancelled and msg:
                    with contextlib.suppress(discord.HTTPException):
                        await msg.delete()

    async def _bold4(self, ctx, query):
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                taxon = query_response.taxon
                taxon_name = taxon.name.replace(" ", "+")
                name = format_taxon_name(taxon, with_common=False)
                common = (
                    f" ({taxon.preferred_common_name})"
                    if taxon.preferred_common_name
                    else ""
                )
                taxon_id = taxon.id
                taxon_url = f"{WWW_BASE_URL}/taxa/{taxon_id}"
                embed = make_embed(
                    title=f"BOLD v4: {name}",
                    url=f"{BOLD_BASE_URL}/Taxbrowser_Taxonpage?taxon={taxon_name}",
                    description=(f"iNat Taxon: [{name}]({taxon_url}){common}\n"),
                )
                await ctx.send(embed=embed)

    @taxon.command(name="bold4")
    @use_client
    async def taxon_bold4(self, ctx, *, query: Optional[str]):
        """Barcode records from BOLD v4 (alias `[p]bold4`)."""
        await self._bold4(ctx, query)

    @commands.command(hidden="true")
    @use_client
    async def bold4(self, ctx, *, query: Optional[str]):
        """Barcode records from BOLD v4 (alias `[p]t bold4`)."""
        await self._bold4(ctx, query)

    @taxon.command(name="means")
    @use_client
    async def taxon_means(self, ctx, place_query: str, *, query: Optional[str]):
        """Show establishment means for taxon from the specified place."""
        try:
            place = await self.place_table.get_place(ctx.guild, place_query, ctx.author)
        except LookupError as err:
            await ctx.send(err)
            return
        place_id = place.id

        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                taxon = query_response.taxon
                lang = await get_lang(ctx)
                title = format_taxon_name(taxon, with_term=True, lang=lang)
                url = f"{WWW_BASE_URL}/taxa/{taxon.id}"
                full_taxon = await get_taxon(ctx, taxon.id, preferred_place_id=place_id)
                description = f"Establishment means unknown in: {place.display_name}"
                try:
                    place_id = full_taxon.establishment_means.place.id
                    find_means = (
                        means
                        for means in full_taxon.listed_taxa
                        if means.place.id == place_id
                    )
                    means = next(find_means, full_taxon.establishment_means)
                    if means:
                        if means:
                            description = format_taxon_establishment_means(
                                means, all_means=True, list_title=True
                            )
                except AttributeError:
                    pass
                await ctx.send(
                    embed=make_embed(title=title, url=url, description=description)
                )

    @taxon.command(name="sci")
    @use_client
    async def taxon_sci(self, ctx, *, query: Optional[str]):
        """Search for taxon matching the scientific name."""
        error_msg = None
        async with self._get_taxon_response(ctx, query, scientific_name=True) as (
            query_response,
            _query,
        ):
            if not query_response:
                return
            try:
                await self._start_taxon_menu(ctx, query_response)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)

    @taxon.command(name="lang")
    @use_client
    async def taxon_loc(self, ctx, locale: str, *, query: Optional[str]):
        """Search for taxon matching specific locale/language."""
        error_msg = None
        async with self._get_taxon_response(ctx, query, locale=locale) as (
            query_response,
            _query,
        ):
            if not query_response:
                return
            try:
                await self._start_taxon_menu(ctx, query_response)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)

    @use_client
    @commands.command(hidden=True)
    @use_client
    async def ttest(self, ctx, *, query: Optional[str]):
        """Taxon via pyinaturalist (test)."""
        paginator = ctx.inat_client.taxa.autocomplete(q=query, limit=1)
        taxa = await paginator.async_all() if paginator else None
        taxon = taxa[0] if taxa else None
        if taxon:
            embed = make_embed()
            # Show enough of the record for a satisfying test.
            embed.title = taxon.name
            embed.url = f"{WWW_BASE_URL}/taxa/{taxon.id}"
            default_photo = taxon.default_photo
            if default_photo:
                medium_url = default_photo.medium_url
                if medium_url:
                    embed.set_image(url=medium_url)
                    embed.set_footer(text=default_photo.attribution)
            embed.description = (
                "```py\n"
                + textwrap.shorten(
                    f"{repr(taxon)}",
                    width=MAX_EMBED_DESCRIPTION_LEN
                    - 10,  # i.e. minus the code block markup
                    placeholder="…",
                )
                + "\n```"
            )
            await ctx.send(embed=embed)

    @commands.command(hidden=True)
    @use_client
    async def tname(self, ctx, *, query: Optional[str]):
        """Taxon name only.

        See `[p]taxon_query` for help with the query.
        ```
        """
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                await ctx.send(query_response.taxon.name)

    @commands.command(aliases=["sp"], hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def species(self, ctx, *, query: Optional[str]):
        """Species information. (alias `[p]t` *query* `rank sp`)

        See `[p]taxon_query` for query help."""

        error_msg = None
        async with self._get_taxon_response(ctx, query, ranks=["species"]) as (
            query_response,
            _query,
        ):
            if not query_response:
                return
            try:
                await self._start_taxon_menu(ctx, query_response)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)

    @taxon.command(name="related")
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def taxon_related(self, ctx, *, taxa_list: str):
        """Relatedness of a list of taxa.

        **Examples:**
        ```
        [p]related 24255,24267
        [p]related boreal chorus frog,western chorus frog
        ```
        See `[p]taxon_query` for help specifying taxa.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        query_response = None
        try:
            _query = await TaxonReplyConverter.convert(ctx, "", allow_empty=True)
            query_response = await prepare_query_for_taxon(ctx.inat_client, _query)
            if query_response and query_response.taxon:
                _taxa_list = f"{query_response.taxon.id},{taxa_list}"
            else:
                _taxa_list = taxa_list
            (taxa, missing_taxa) = await self.taxon_query.query_taxa(ctx, _taxa_list)
            (related_taxon, related_embed) = await self.make_related_embed(
                ctx, taxa, missing_taxa
            )
            related_query_response = QueryResponse(taxon=related_taxon)
            await self._start_taxon_menu(
                ctx, related_query_response, related_embed=related_embed
            )
        except (BadArgument, LookupError, ValueError) as err:
            await apologize(ctx, err)

    @commands.command(hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def related(self, ctx, *, taxa_list: str):
        await (self.bot.get_command("taxon related")(ctx, taxa_list=taxa_list))

    @taxon.command(name="image", aliases=["img", "photo"])
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def taxon_image(
        self, ctx, number: Optional[int] = 1, *, query: Optional[str]
    ):
        """Default image for a taxon.

        See `[p]taxon_query` for *query* help."""
        error_msg = None
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if not query_response:
                return
            try:
                await self._start_taxon_menu(ctx, query_response, image_number=number)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)

    @commands.command(aliases=["img", "photo"], hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def image_alias(
        self, ctx, number: Optional[int] = 1, *, query: Optional[str] = ""
    ):
        await (self.bot.get_command("taxon image")(ctx, number, query=query))
