"""Module for taxon command group."""

import re
import textwrap
from typing import Optional

from dronefly.core.formatters.generic import (
    format_taxon_name,
    format_taxon_establishment_means,
)
from dronefly.core.models.taxon import PLANTAE_ID
from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from ..base_classes import WWW_BASE_URL
from ..converters.base import NaturalQueryConverter
from ..converters.reply import TaxonReplyConverter
from ..embeds.common import apologize, make_embed, MAX_EMBED_DESCRIPTION_LEN
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..taxa import get_taxon

BOLD_BASE_URL = "http://www.boldsystems.org/index.php/Public_BINSearch"


class CommandsTaxon(INatEmbeds, MixinMeta):
    """Mixin providing taxon command group."""

    @commands.hybrid_group(aliases=["t"], fallback="show")
    @checks.bot_has_permissions(embed_links=True)
    async def taxon(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Taxon information.

        - *Taxon query terms* match a single taxon to display.
        - *Observation query terms* match observation filters.
        - *Reply* to another display to display its taxon.
        - The *query* is optional when that display contains a taxon.
        **Related help topics:**
        - `[p]help taxon_query` for *taxon query* terms
        - `[p]help query` for help with other *query* terms
        - `[p]help reactions` describes the *reaction buttons*
        - `[p]help s taxa` to search and browse matching taxa
        """
        _query = query or await TaxonReplyConverter.convert(ctx, "")
        try:
            self.check_taxon_query(ctx, _query)
        except BadArgument as err:
            await apologize(ctx, str(err))
            return

        try:
            query_response = await self.query.get(ctx, _query)
        except LookupError as err:
            await apologize(ctx, str(err))
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @taxon.command(name='map')
    async def taxon_map(self, ctx, *, taxa_list):
        """Show range map for one or more taxa."""
        await (self.bot.get_command("map")(ctx, taxa_list=taxa_list))

    @taxon.command(name='search')
    async def taxon_search(self, ctx, *, query):
        """Search for matching taxa."""
        await (self.bot.get_command("search taxa")(ctx, query=query))

    @taxon.command()
    async def bonap(self, ctx, *, query: NaturalQueryConverter):
        """North American flora info from bonap.net."""
        try:
            self.check_taxon_query(ctx, query)
            query_response = await self.query.get(ctx, query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

        base_url = "http://bonap.net/MapGallery/County/"
        maps_url = "http://bonap.net/NAPA/TaxonMaps/Genus/County/"
        taxon = query_response.taxon
        name = re.sub(r" ", "%20", taxon.name)
        lang = await self.get_lang(ctx)
        full_name = format_taxon_name(taxon, lang=lang)
        if PLANTAE_ID not in taxon.ancestor_ids:  # Plantae
            await ctx.send(f"{full_name} is not in Plantae")
            return
        if taxon.rank == "genus":
            await ctx.send(
                f"{full_name} species maps: {maps_url}{name}\nGenus map: {base_url}Genus/{name}.png"
            )
        elif taxon.rank == "species":
            await ctx.send(f"{full_name} map:\n{base_url}{name}.png")
        else:
            await ctx.send(f"{full_name} must be a genus or species, not: {taxon.rank}")
            return
        await (self.bot.get_command("tabulate")(ctx, query=query))

    async def _bold4(self, ctx, query):
        try:
            _query = query or await TaxonReplyConverter.convert(ctx, "")
            self.check_taxon_query(ctx, _query)
            query_response = await self.query.get(ctx, _query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

        taxon = query_response.taxon
        taxon_name = taxon.name.replace(" ", "+")
        name = format_taxon_name(taxon, with_common=False)
        common = (
            f" ({taxon.preferred_common_name})" if taxon.preferred_common_name else ""
        )
        taxon_id = taxon.id
        taxon_url = f"{WWW_BASE_URL}/taxa/{taxon_id}"
        embed = make_embed(
            title=f"BOLD v4: {name}",
            url=f"{BOLD_BASE_URL}?searchtype=records&query={taxon_name}",
            description=(f"iNat Taxon: [{name}]({taxon_url}){common}\n"),
        )
        await ctx.send(embed=embed)

    @taxon.command(name="bold4")
    async def taxon_bold4(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Barcode records from BOLD v4 (alias `[p]bold4`)."""
        await self._bold4(ctx, query)

    @commands.command(hidden="true")
    async def bold4(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Barcode records from BOLD v4 (alias `[p]t bold4`)."""
        await self._bold4(ctx, query)

    @taxon.command(name="means")
    async def taxon_means(self, ctx, place_query: str, *, query: NaturalQueryConverter):
        """Show establishment means for taxon from the specified place."""
        try:
            place = await self.place_table.get_place(ctx.guild, place_query, ctx.author)
        except LookupError as err:
            await ctx.send(err)
            return
        place_id = place.place_id

        try:
            self.check_taxon_query(ctx, query)
            query_response = await self.query.get(ctx, query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return
        taxon = query_response.taxon
        lang = await self.get_lang(ctx)
        title = format_taxon_name(taxon, with_term=True, lang=lang)
        url = f"{WWW_BASE_URL}/taxa/{taxon.id}"
        full_taxon = await get_taxon(self, taxon.id, preferred_place_id=place_id)
        description = f"Establishment means unknown in: {place.display_name}"
        try:
            place_id = full_taxon.establishment_means.place.id
            find_means = (
                means for means in full_taxon.listed_taxa if means.place.id == place_id
            )
            means = next(find_means, full_taxon.establishment_means)
            if means:
                if means:
                    description = format_taxon_establishment_means(
                        means, all_means=True, list_title=True
                    )
        except AttributeError:
            pass
        await ctx.send(embed=make_embed(title=title, url=url, description=description))

    @taxon.command(name="sci")
    async def taxon_sci(self, ctx, *, query: NaturalQueryConverter):
        """Search for taxon matching the scientific name."""
        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, str(err))
            return

        try:
            query_response = await self.query.get(ctx, query, scientific_name=True)
        except LookupError as err:
            await apologize(ctx, str(err))
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @taxon.command(name="lang")
    async def taxon_loc(self, ctx, locale: str, *, query: NaturalQueryConverter):
        """Search for taxon matching specific locale/language."""
        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, str(err))
            return

        try:
            query_response = await self.query.get(ctx, query, locale=locale)
        except LookupError as err:
            await apologize(ctx, str(err))
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @commands.command(hidden=True)
    async def ttest(self, ctx, *, query: str):
        """Taxon via pyinaturalist (test)."""
        response = await self.api.get_taxa_autocomplete(ctx, q=query)
        if response:
            results = response.get("results")
            if results:
                taxon = results[0]
                embed = make_embed()
                # Show enough of the record for a satisfying test.
                embed.title = taxon.get("name")
                embed.url = f"{WWW_BASE_URL}/taxa/{taxon.get('id')}"
                default_photo = taxon.get("default_photo")
                if default_photo:
                    medium_url = default_photo.get("medium_url")
                    if medium_url:
                        embed.set_image(url=medium_url)
                        embed.set_footer(text=default_photo.get("attribution"))
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
    async def tname(self, ctx, *, query: NaturalQueryConverter):
        """Taxon name only.

        See `[p]help taxon_query` for help with the query.
        ```
        """

        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, str(err))
            return

        try:
            query_response = await self.query.get(ctx, query)
        except LookupError as err:
            reason = str(err)
            await ctx.send(reason)
            return

        await ctx.send(query_response.taxon.name)

    @commands.command(aliases=["sp"], hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def species(self, ctx, *, query: NaturalQueryConverter):
        """Species information. (alias `[p]t` *query* `rank sp`)

        See `[p]help taxon_query` for query help."""
        query_species = query
        query_species.main.ranks.append("species")
        await self.taxon(ctx, query=query_species)

    @taxon.command(name="related")
    @checks.bot_has_permissions(embed_links=True)
    async def taxon_related(self, ctx, *, taxa_list: str):
        """Relatedness of a list of taxa.

        **Examples:**
        ```
        [p]related 24255,24267
        [p]related boreal chorus frog,western chorus frog
        ```
        See `[p]help taxon_query` for help specifying taxa.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxon_query.query_taxa(ctx, taxa_list)
        except LookupError as err:
            await apologize(ctx, str(err))
            return

        await ctx.send(embed=await self.make_related_embed(ctx, taxa))

    @commands.command(hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def related(self, ctx, *, taxa_list: str):
        await (self.bot.get_command('taxon related')(ctx, taxa_list=taxa_list))

    @taxon.command(name="image", aliases=["img", "photo"])
    @checks.bot_has_permissions(embed_links=True)
    async def taxon_image(self, ctx, *, query: NaturalQueryConverter):
        """Default image for a taxon.

        See `[p]help taxon_query` for *query* help."""
        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, str(err))
            return

        try:
            query_response = await self.query.get(ctx, query)
        except LookupError as err:
            await apologize(ctx, str(err))
            return

        await self.send_embed_for_taxon_image(ctx, query_response.taxon)

    @commands.command(aliases=["img", "photo"], hidden=True)
    @checks.bot_has_permissions(embed_links=True)
    async def image_alias(self, ctx, *, query: NaturalQueryConverter):
        await (self.bot.get_command("taxon image")(ctx, query=query))
