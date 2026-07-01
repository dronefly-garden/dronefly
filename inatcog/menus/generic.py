from typing import Any

import discord
from discord.ext import commands
from dronefly.core.menus import (
    BaseMenu as CoreBaseMenu,
    ListPageSource,
)
from dronefly.discord.menus import (
    DiscordBaseMenu,
    BackButton,
    ForwardButton,
    StopButton,
)


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


class EmbedListSource(ListPageSource):
    def __init__(self, entries: list[EmbedSource], per_page: int = 1):
        super().__init__(entries=entries, per_page=per_page)


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


class EmbedListMenu(EmbedMenu):
    """Generic paginated view of list of embed(s) with stop & nav buttons."""

    ctx: commands.Context = None
    author: discord.Member = None
    message: discord.Message = None
    back_button: discord.Button = None
    stop_button: discord.Button = None
    forward_button: discord.Button = None

    def __init__(
        self,
        source: EmbedListSource,
        current_page: int = 0,
        **kwargs: Any,
    ) -> None:
        self.source = source
        self.current_page = current_page
        super().__init__(source=source, **kwargs)
        self.back_button = BackButton(discord.ButtonStyle.grey, 0)
        self.stop_button = StopButton(discord.ButtonStyle.red, 0)
        self.forward_button = ForwardButton(discord.ButtonStyle.grey, 0)

    async def start(self, ctx: commands.Context, **initial_message_params):
        self.ctx = ctx
        self.author = ctx.author
        self.add_item(self.back_button)
        self.add_item(self.stop_button)
        self.add_item(self.forward_button)
        embed = await self.source.get_page(self.current_page)
        await self.send_initial_message(ctx, embed=embed, **initial_message_params)

    async def show_page(
        self, page_number: int, interaction: discord.Interaction, selected: int = 0
    ):
        embed = await self.source.get_page(page_number)
        self.current_page = page_number
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def show_checked_page(
        self, page_number: int, interaction: discord.Interaction
    ) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number, interaction)
            elif page_number >= max_pages:
                await self.show_page(0, interaction)
            elif page_number < 0:
                await self.show_page(max_pages - 1, interaction)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number, interaction)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to use owner_ids"""
        if interaction.user.id not in (
            *interaction.client.owner_ids,
            getattr(self.author, "id", None),
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        return True
