"""Module for taxon command group."""

import re
from typing import Optional

from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from inatcog.base_classes import PLANTAE_ID, WWW_BASE_URL
from inatcog.converters.base import NaturalQueryConverter
from inatcog.converters.reply import TaxonReplyConverter
from inatcog.embeds.common import apologize, make_embed
from inatcog.embeds.inat import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.taxa import get_taxon


class CommandsTaxon(INatEmbeds, MixinMeta):
    """Mixin providing taxon command group."""

    @commands.group(aliases=["t"], invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    async def taxon(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Show taxon best matching the query.

        `Aliases: [p]t`
        **query** may contain:
        - *id#* of the iNat taxon
        - *initial letters* of scientific or common names
        - *double-quotes* around exact words in the name
        - *rank keywords* filter by ranks (`sp`, `family`, etc.)
        - *4-letter AOU codes* for birds
        - *taxon* `in` *an ancestor taxon*
        **Examples:**
        ```
        [p]taxon family bear
           -> Ursidae (Bears)
        [p]taxon prunella
           -> Prunella (self-heals)
        [p]taxon prunella in animals
           -> Prunella (Accentors)
        [p]taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        """
        _query = query or await TaxonReplyConverter.convert(ctx, "")
        try:
            self.check_taxon_query(ctx, _query)
        except BadArgument as err:
            await apologize(ctx, err.args[0])
            return

        try:
            query_response = await self.query.get(ctx, _query)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @taxon.command()
    async def bonap(self, ctx, *, query: NaturalQueryConverter):
        """Show info from bonap.net for taxon."""
        try:
            self.check_taxon_query(ctx, query)
            query_response = await self.query.get(ctx, query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

        base_url = "http://bonap.net/MapGallery/County/"
        maps_url = "http://bonap.net/NAPA/TaxonMaps/Genus/County/"
        taxon = query_response.taxon
        name = re.sub(r" ", "%20", taxon.name)
        full_name = taxon.format_name()
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
            await apologize(ctx, err.args[0])
            return
        taxon = query_response.taxon
        title = taxon.format_name(with_term=True)
        url = f"{WWW_BASE_URL}/taxa/{taxon.taxon_id}"
        full_taxon = await get_taxon(self, taxon.taxon_id, preferred_place_id=place_id)
        description = f"Establishment means unknown in: {place.display_name}"
        try:
            place_id = full_taxon.establishment_means.place.id
            find_means = (
                means for means in full_taxon.listed_taxa if means.place.id == place_id
            )
            means = next(find_means, full_taxon.establishment_means)
            if means:
                description = (
                    f"{means.emoji()}{means.description()} ({means.list_link()})"
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
            await apologize(ctx, err.args[0])
            return

        try:
            query_response = await self.query.get(ctx, query, scientific_name=True)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @taxon.command(name="lang")
    async def taxon_loc(self, ctx, locale: str, *, query: NaturalQueryConverter):
        """Search for taxon matching specific locale/language."""
        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, err.args[0])
            return

        try:
            query_response = await self.query.get(ctx, query, locale=locale)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        await self.send_embed_for_taxon(ctx, query_response)

    @commands.command()
    async def tname(self, ctx, *, query: NaturalQueryConverter):
        """Show taxon name best matching the query.

        See `[p]help taxon` for help with the query.
        ```
        """

        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await apologize(ctx, err.args[0])
            return

        try:
            query_response = await self.query.get(ctx, query)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(reason)
            return

        await ctx.send(query_response.taxon.name)

    @commands.command(aliases=["sp"])
    @checks.bot_has_permissions(embed_links=True)
    async def species(self, ctx, *, query: NaturalQueryConverter):
        """Show species best matching the query.

        `Aliases: [p]sp, [p]t sp`

        See `[p]help taxon` for query help."""
        query_species = query
        query_species.main.ranks.append("species")
        await self.taxon(ctx, query=query_species)

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def related(self, ctx, *, taxa_list):
        """Relatedness of a list of taxa.

        **Examples:**
        ```
        [p]related 24255,24267
        [p]related boreal chorus frog,western chorus frog
        ```
        See `[p]help taxon` for help specifying taxa.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxon_query.query_taxa(ctx, taxa_list)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        await ctx.send(embed=await self.make_related_embed(ctx, taxa))

    @commands.command(aliases=["img", "photo"])
    @checks.bot_has_permissions(embed_links=True)
    async def image(self, ctx, *, taxon_query: NaturalQueryConverter):
        """Show default image for taxon query.

        `Aliases: [p]img`

        See `[p]help taxon` for `taxon_query` format."""
        try:
            self.check_taxon_query(ctx, taxon_query)
        except BadArgument as err:
            await apologize(ctx, err.args[0])
            return

        try:
            query_response = await self.query.get(ctx, taxon_query)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        await self.send_embed_for_taxon_image(ctx, query_response.taxon)
