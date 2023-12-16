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
from dronefly.core.constants import TRACHEOPHYTA_ID
from dronefly.discord.embeds import make_embed, MAX_EMBED_DESCRIPTION_LEN
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
            query_response = await self.query.get(ctx, _query, **kwargs)
        except EmptyArgument:
            await ctx.send_help()
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))

        yield query_response, _query

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
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                await self.send_embed_for_taxon(ctx, query_response)

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
                base_url = "http://bonap.net/MapGallery/County/"
                maps_url = "http://bonap.net/NAPA/TaxonMaps/Genus/County/"
                taxon = query_response.taxon
                name = re.sub(r" ", "%20", taxon.name)
                lang = await get_lang(ctx)
                full_name = format_taxon_name(taxon, lang=lang)
                if TRACHEOPHYTA_ID not in taxon.ancestor_ids:
                    msg = await ctx.send(
                        f"{full_name} is not in Tracheophyta (Vascular Plants)"
                    )
                    await add_reactions_with_cancel(ctx, msg, [])
                    return
                if taxon.rank == "genus":
                    msg = await ctx.send(
                        (
                            f"{full_name} species maps: {maps_url}{name}\n"
                            f"Genus map: {base_url}Genus/{name}.png"
                        )
                    )
                elif taxon.rank == "species":
                    msg = await ctx.send(f"{full_name} map:\n{base_url}{name}.png")
                else:
                    msg = await ctx.send(
                        f"{full_name} must be a genus or species, not: {taxon.rank}"
                    )
                    await add_reactions_with_cancel(ctx, msg, [])
                    return
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
        async with self._get_taxon_response(ctx, query, scientific_name=True) as (
            query_response,
            _query,
        ):
            if query_response:
                await self.send_embed_for_taxon(ctx, query_response)

    @taxon.command(name="lang")
    @use_client
    async def taxon_loc(self, ctx, locale: str, *, query: Optional[str]):
        """Search for taxon matching specific locale/language."""
        async with self._get_taxon_response(ctx, query, locale=locale) as (
            query_response,
            _query,
        ):
            if query_response:
                await self.send_embed_for_taxon(ctx, query_response)

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
        async with self._get_taxon_response(ctx, query, ranks=["species"]) as (
            query_response,
            _query,
        ):
            if query_response:
                await self.send_embed_for_taxon(ctx, query_response)

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
            query_response = await self.query.get(ctx, _query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return
        if query_response and query_response.taxon:
            _taxa_list = f"{query_response.taxon.id},{taxa_list}"
        else:
            _taxa_list = taxa_list
        (taxa, missing_taxa) = await self.taxon_query.query_taxa(ctx, _taxa_list)
        (taxon, related_embed) = await self.make_related_embed(ctx, taxa, missing_taxa)
        await self.send_embed_for_taxon(ctx, taxon, related_embed=related_embed)

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
        async with self._get_taxon_response(ctx, query) as (query_response, _query):
            if query_response:
                await self.send_embed_for_taxon_image(ctx, query_response.taxon, number)

    @commands.command(aliases=["img", "photo"], hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def image_alias(
        self, ctx, number: Optional[int] = 1, *, query: Optional[str] = ""
    ):
        await (self.bot.get_command("taxon image")(ctx, number, query=query))
