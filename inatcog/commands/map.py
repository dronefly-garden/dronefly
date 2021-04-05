"""Module for map command group."""

import urllib.parse
from redbot.core import checks, commands

from inatcog.base_classes import WWW_BASE_URL
from inatcog.converters import NaturalCompoundQueryConverter
from inatcog.embeds import apologize, make_embed
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.taxa import format_taxon_name


class CommandsMap(INatEmbeds, MixinMeta):
    """Mixin providing taxon command group."""

    @commands.group(invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    async def map(self, ctx, *, taxa_list):
        """Show range map for a list of one or more taxa.

        **Examples:**
        ```
        [p]map polar bear
        [p]map 24255,24267
        [p]map boreal chorus frog,western chorus frog
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

        await ctx.send(embed=await self.make_map_embed(taxa))

    @map.command(name="obs")
    async def map_obs(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Show map of observations."""

        try:
            (
                kwargs,
                filtered_taxon,
                _term,
                _value,
            ) = await self.obs_query.get_query_args(ctx, query)
            if filtered_taxon.taxon:
                query_title = "Map of " + format_taxon_name(
                    filtered_taxon.taxon, with_term=True
                )
            else:
                query_title = "Map of observations"
            if filtered_taxon.user:
                query_title += f" by {filtered_taxon.user.login}"
            if filtered_taxon.unobserved_by:
                query_title += f" unobserved by {filtered_taxon.unobserved_by.login}"
            if filtered_taxon.id_by:
                query_title += f" identified by {filtered_taxon.id_by.login}"
            if filtered_taxon.project:
                query_title += f" in {filtered_taxon.project.title}"
            if filtered_taxon.place:
                query_title += f" from {filtered_taxon.place.display_name}"
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        url = f"{WWW_BASE_URL}/observations/map?{urllib.parse.urlencode(kwargs)}"
        await ctx.send(embed=make_embed(url=url, title=query_title))
