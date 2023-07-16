"""Module for map command group."""

from typing import Optional
import urllib.parse

from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.formatters.generic import format_taxon_name
from dronefly.discord.embeds import make_embed
from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from inatcog.converters.base import NaturalQueryConverter
from inatcog.converters.reply import TaxonReplyConverter
from inatcog.embeds.common import apologize
from inatcog.embeds.inat import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.utils import use_client


class CommandsMap(INatEmbeds, MixinMeta):
    """Mixin providing taxon command group."""

    @commands.group(invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def map(self, ctx, *, taxa_list: Optional[str] = ""):
        """Show range map for a list of one or more taxa.

        **Examples:**
        ```
        [p]map polar bear
        [p]map 24255,24267
        [p]map boreal chorus frog,western chorus frog
        ```
        See `[p]taxon_query` for help specifying taxa.
        """

        query_response = None
        _taxa_list = ""
        try:
            _query = await TaxonReplyConverter.convert(ctx, "", allow_empty=True)
            query_response = await self.query.get(ctx, _query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return
        if query_response and query_response.taxon:
            _taxa_list = str(query_response.taxon.id)
            if taxa_list:
                _taxa_list = [_taxa_list, taxa_list]
                _taxa_list = ",".join(_taxa_list)
        else:
            _taxa_list = taxa_list

        if not _taxa_list:
            await ctx.send_help()
            return

        (taxa, missing_taxa) = await self.taxon_query.query_taxa(ctx, _taxa_list)
        embed = await self.make_map_embed(ctx, taxa, missing_taxa)
        await ctx.send(embed=embed)

    @map.command(name="obs")
    @use_client
    async def map_obs(self, ctx, *, query: NaturalQueryConverter):
        """Show map of observations."""

        try:
            query_response = await self.query.get(ctx, query)
            kwargs = query_response.obs_args()
            # TODO: determine why we don't just use QueryResponse.obs_query_description
            # and either use it directly or otherwise share code instead of duplicating
            # most of it here.
            if query_response.taxon:
                query_title = "Map of " + format_taxon_name(
                    query_response.taxon, with_term=True
                )
            else:
                query_title = "Map of observations"
            if query_response.user:
                query_title += f" by {query_response.user.login}"
            if query_response.unobserved_by:
                query_title += f" unobserved by {query_response.unobserved_by.login}"
            if query_response.id_by:
                query_title += f" identified by {query_response.id_by.login}"
            if query_response.except_by:
                query_title += f" except by {query_response.except_by.login}"
            if query_response.project:
                query_title += f" in {query_response.project.title}"
            if query_response.place:
                query_title += f" from {query_response.place.display_name}"
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        url = f"{WWW_BASE_URL}/observations/map?{urllib.parse.urlencode(kwargs)}"
        await ctx.send(embed=make_embed(url=url, title=query_title))
