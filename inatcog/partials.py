from typing import Optional, Union
from attr import define
import discord
from pyinaturalist import iNatClient
from redbot.core.bot import Red
from redbot.core.commands import Cog


@define
class PartialMessage:
    """Partial Message to satisfy bot & guild checks."""

    author: discord.User
    guild: discord.Guild


@define
class PartialContext:
    "Partial Context synthesized from objects available in an interaction or listener."

    bot: Red
    guild: discord.Guild
    channel: discord.ChannelType
    author: discord.User
    message: Optional[Union[discord.Message, PartialMessage]]
    command: Optional[str] = ""
    assume_yes: bool = True
    interaction: Optional[discord.Interaction] = None
    cog: Cog = None
    inat_client: iNatClient = None

    async def send(self, *args, **kwargs):
        if self.interaction:
            # Strip kwargs unsupported by interaction webhooks if passed by legacy paths
            kwargs.pop("reference", None)
            kwargs.pop("mention_author", None)

            if self.interaction.response.is_done():
                return await self.interaction.followup.send(*args, **kwargs)

            await self.interaction.response.send_message(*args, **kwargs)
            return await self.interaction.original_response()

        return await self.channel.send(*args, **kwargs)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = True):
        if self.interaction and not self.interaction.response.is_done():
            return await self.interaction.response.defer(
                ephemeral=ephemeral, thinking=thinking
            )
