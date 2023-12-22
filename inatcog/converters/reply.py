"""Reply converters."""
import re

import discord
from discord import Message, MessageReference
from redbot.core.commands import BadArgument, Context
from dronefly.core.query.query import EMPTY_QUERY
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter

DISCORD_MSG_PAT = re.compile(
    r"(https://discord\.com/channels/((?P<me>@me)|(?P<guildid>\d{18}))"
    r"/(?P<channelid>\d{18})/(?P<messageid>\d{19}))"
)


# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981
class EmptyArgument(BadArgument):
    """Argument to a command is empty."""


class TaxonReplyConverter:
    """Use replied to bot message as a part of the query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = "", allow_empty: bool = False):
        """Default to taxon from replied to bot message."""

        async def get_query_from_link(link: re.Match, query_str: str):
            channel_id = int(link["channelid"])
            message_id = int(link["messageid"])
            msg = next((m for m in ctx.bot.cached_messages if m.id == message_id), "")
            if link["guildid"]:
                guild_id = int(link["guildid"])
                guild = ctx.bot.get_guild(guild_id)
                if not guild.get_member(guild.me.id) or not guild.get_member(
                    ctx.author.id
                ):
                    raise BadArgument("I couldn't access that channel")
                channel = guild.get_channel(channel_id)
                if not msg:
                    if ctx.guild:
                        if not channel.permissions_for(
                            ctx.guild.me
                        ).read_message_history:
                            raise BadArgument(
                                "I need Read Message History permission to read that message"
                            )
                        if not channel.permissions_for(ctx.author).read_message_history:
                            raise BadArgument(
                                "You need Read Message History permission to read that message"
                            )
            else:
                channel = next(
                    (c for c in ctx.bot.private_channels if c.id == channel_id), None
                )
                if not channel:
                    try:
                        channel = await ctx.bot.fetch_channel(channel_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        channel = None
                if (
                    not channel
                    or channel.recipient != ctx.author
                    or channel.me != ctx.bot.user
                ):
                    raise BadArgument("I couldn't access that private channel")
            if not msg:
                try:
                    msg = await channel.fetch_message(message_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    raise BadArgument("I couldn't retrieve that message")
            _query_str = query_str.replace(link[0], "")
            return await get_query_from_msg(msg, _query_str)

        async def get_query_from_msg(msg: Message, query_str: str):
            _query_str = query_str
            if msg and msg.author.bot and msg.embeds:
                embed = next(
                    (embed for embed in msg.embeds if embed.type == "rich"), None
                )
                if embed:
                    inat_embed = INatEmbed.from_discord_embed(embed)
                    if query_str:
                        reply_query = await NaturalQueryConverter.convert(
                            ctx, _query_str
                        )
                        _query_str = str(inat_embed.query(reply_query))
                    else:
                        _query_str = str(inat_embed.query())

            # We might want to change this at some point in future to make it consistent,
            # i.e. the messages will be shown when the user replied with no arguments
            # but we couldn't fetch the message or find useful content, but not if
            # arguments were supplied. This is because BadArgument always triggers
            # help when the converter is used in the command definition, but we catch
            # and display the message when used in the body of the command (i.e. the
            # "no arguments" case).
            if not _query_str:
                if ref:
                    if not msg:
                        raise BadArgument("I couldn't fetch that message.")
                    raise BadArgument(
                        "I couldn't recognize the content in that message."
                    )
            return _query_str

        async def get_query_from_ref_msg(ref: MessageReference, query_str: str):
            """Return a query string from the referenced embed."""
            msg = ref.cached_message
            if not msg:
                # See comment below for why the user won't see this message with
                # our current approach:
                if (
                    ctx.guild
                    and not ctx.channel.permissions_for(
                        ctx.guild.me
                    ).read_message_history
                ):
                    raise BadArgument(
                        "I need Read Message History permission to read that message."
                    )
                msg = await ctx.channel.fetch_message(ref.message_id)
            return await get_query_from_msg(msg, query_str)

        ref = ctx.message.reference
        if ref:
            query_str = await get_query_from_ref_msg(ref, argument)
        else:
            link = DISCORD_MSG_PAT.search(argument)
            if link:
                query_str = await get_query_from_link(link, argument)
            else:
                query_str = argument
        if not query_str:
            if allow_empty:
                return EMPTY_QUERY
            else:
                raise EmptyArgument("This command requires an argument.")

        return await NaturalQueryConverter.convert(ctx, query_str)
