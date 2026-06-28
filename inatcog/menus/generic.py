from typing import Any

import discord
from discord.ext import commands
from dronefly.core.menus import (
    BaseMenu as CoreBaseMenu,
)
from dronefly.discord.menus import DiscordBaseMenu, StopButton


class EmbedSource(list[discord.Embed]):
    def __init__(self, iterable=()):
        super().__init__()
        self.extend(iterable)

    def _coerce(self, v):
        if isinstance(v, discord.Embed):
            return v
        return discord.Embed(v)

    def append(self, v):
        super().append(self._coerce(v))

    def extend(self, it):
        super().extend(self._coerce(v) for v in it)


class EmbedMenu(DiscordBaseMenu, CoreBaseMenu):
    """Generic single page view of embed(s) with stop button."""

    ctx: commands.Context = None
    author: discord.Member = None
    message: discord.Message = None
    stop_button: discord.Button = None

    def __init__(
        self,
        source: EmbedSource,
        **kwargs: Any,
    ) -> None:
        self.source = source
        super().__init__()
        self.stop_button = StopButton(discord.ButtonStyle.red, 0)

    async def on_timeout(self):
        await self.message.edit(view=None)

    async def send_initial_message(self, ctx: commands.Context, **params):
        self.ctx = ctx
        self.message = await ctx.send(view=self, **params)
        return self.message

    async def start(self, ctx: commands.Context, **initial_message_params):
        self.ctx = ctx
        self.author = ctx.author
        self.add_item(self.stop_button)
        await self.send_initial_message(ctx, **initial_message_params)

    async def interaction_check(self, interaction: discord.Interaction):
        """Allow only owner to use interactions."""
        if interaction.user.id not in (
            *interaction.client.owner_ids,
            getattr(self.author, "id", None),
        ):
            await interaction.response.send_message(
                content="Only the command owner can do this.", ephemeral=True
            )
            return False
        return True


"""
class EmbedPagesMenu(EmbedMenu):
    ctx: commands.Context = None
    author: discord.Member = None
    message: discord.Message = None
    stop_button: discord.Button = None

    # Generic view with a list of pages, page nav, & stop buttons.
    def __init__(
        self,
        source: EmbedPagesSource,
        **kwargs: Any,
    ) -> None:
        self.source = source
        super().__init__()
        # TODO: add nav buttons and pagination implementation
"""
