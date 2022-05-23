"""A cog for using the iNaturalist platform."""
import asyncio

import discord
from pyinaturalist import iNatClient
from redbot.core import commands, Config

from dronefly.core.formatters.discord import format_taxon_image_embed


class INat(commands.Cog, name="iNat"):
    """Commands provided by `inat`."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=6188)
        self.client = iNatClient(
            default_params={"locale": "en", "preferred_place_id": 1}
        )

        self._cleaned_up = False
        self._init_task: asyncio.Task = self.bot.loop.create_task(self.initialize())

    async def initialize(self) -> None:
        """Initialization after bot is ready."""
        await self.bot.wait_until_ready()

    def cog_unload(self):
        """Cleanup when the cog unloads."""
        if not self._cleaned_up:
            if self._init_task:
                self._init_task.cancel()
            self.bot.loop.create_task(self.client.session.close())
            self._cleaned_up = True

    @commands.command()
    async def ttest(self, ctx, *, query: str):
        """Taxon via pyinaturalist (test)."""
        async for taxon in self.client.taxa.autocomplete(q=query, limit=1):
            embed = discord.Embed.from_dict(format_taxon_image_embed(taxon))
            await ctx.send(embed=embed)
