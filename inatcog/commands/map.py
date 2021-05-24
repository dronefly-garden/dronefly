"""Module for map command group."""

import urllib.parse
from redbot.core import checks, commands

from inatcog.base_classes import WWW_BASE_URL
from inatcog.converters.base import NaturalQueryConverter
from inatcog.embeds.common import apologize, make_embed
from inatcog.embeds.inat import INatEmbeds
from inatcog.interfaces import MixinMeta


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
    async def map_obs(self, ctx, *, query: NaturalQueryConverter):
        """Show map of observations."""

        try:
            query_response = await self.query.get(ctx, query)
            kwargs = query_response.obs_args()
            if query_response.taxon:
                query_title = "Map of " + query_response.taxon.format_name(
                    with_term=True
                )
            else:
                query_title = "Map of observations"
            if query_response.user:
                query_title += f" by {query_response.user.login}"
            if query_response.unobserved_by:
                query_title += f" unobserved by {query_response.unobserved_by.login}"
            if query_response.id_by:
                query_title += f" identified by {query_response.id_by.login}"
            if query_response.project:
                query_title += f" in {query_response.project.title}"
            if query_response.place:
                query_title += f" from {query_response.place.display_name}"
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        url = f"{WWW_BASE_URL}/observations/map?{urllib.parse.urlencode(kwargs)}"
        await ctx.send(embed=make_embed(url=url, title=query_title))
