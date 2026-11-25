"""Reply converters."""

import re
from typing import Union

import discord
from discord import Message, MessageReference
from redbot.core.commands import BadArgument, Context
from dronefly.core.query import EMPTY_QUERY, Query

from .base import NaturalQueryConverter
from ..embeds.inat import INatEmbed

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
                    if not inat_embed.obs_url or inat_embed.taxon_url:
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
        query_str = ""
        if ref:
            query_str = await get_query_from_ref_msg(ref, argument)
        elif argument:
            link = DISCORD_MSG_PAT.search(argument)
            if link:
                query_str = await get_query_from_link(link, argument)
            else:
                query_str = argument
        if not query_str:
            if allow_empty or ref:
                return EMPTY_QUERY
            else:
                raise EmptyArgument("This command requires a taxon argument.")

        return await NaturalQueryConverter.convert(ctx, query_str)


async def parse_combined_query(
    ctx: Context, taxon_name: str, query: str, with_number=False, require_taxon=True
) -> Query:
    async def parse_query(ctx, query_str):
        return await TaxonReplyConverter.convert(ctx, query_str)

    async def combine_query(ctx, taxon_query_str, query_str, require_taxon):
        if ctx.interaction:
            # Application commands can have an autocompleted taxon as the initial parameter.
            # The arguments cannot be simply joined together, as that might result in out-of-order
            # parsing in the following corner case:
            # - When the taxon_query_str is a group macro, the current Dronefly
            #   query syntax disallows any other macro keywords from the query_str
            #   from appearing *after* the taxon, so they cannot be joined
            #   together on a blank. Doing so would cause such macros to be
            #   ignored, e.g. "my herps" is valid, but "herps my" is not, so
            #   the `my` would not be expanded, and instead would be consumed
            #   as an ordinary keyword.
            # - Therefore, two queries are parsed, first for the taxon argument and then
            #   for the query argument. The results are combined together, giving the
            #   taxon parts of the query precedence over any that might have been
            #   specified in the query. Note: since the replacements occur on a property
            #   by property basis, this strategy may yield some rather odd
            #   results if different taxa *are* specified in the two parts, as some
            #   are defined in terms of `query.main`, whereas others use
            #   `opt taxon_ids=#,#...` so don't rely on it producing good results!
            _taxon_query_str = (
                taxon_query_str or "any"
                if ctx.interaction and not require_taxon
                else taxon_query_str
            )
            parsed_taxon_query = (
                EMPTY_QUERY
                if _taxon_query_str == "any"
                else await parse_query(ctx, _taxon_query_str)
            )
            parsed_query = None if not query_str else await parse_query(ctx, query_str)
            if parsed_query:
                if parsed_taxon_query:
                    if parsed_taxon_query.main:
                        parsed_query.main = parsed_taxon_query.main
                    if parsed_taxon_query.ancestor:
                        parsed_query.ancestor = parsed_taxon_query.ancestor
                    if parsed_taxon_query.options:
                        parsed_query.options = parsed_taxon_query.options + (
                            parsed_query.options or []
                        )
            else:
                parsed_query = parsed_taxon_query
        else:
            # Message-based command argument combine strategy simply joins the
            # taxon query str and query str as if they had been globbed together
            # as a single query parameter.
            parsed_query = await parse_query(
                ctx, " ".join([taxon_query_str, query_str]).strip()
            )
        return parsed_query

    def parse_number(query_str: Union[int, str]) -> tuple[int, str]:
        if isinstance(query_str, int):
            return (query_str, "")
        number = 1
        _query_str = query_str
        parts = [w.strip() for w in _query_str.split(" ", 1)]
        if parts[0].isdigit():
            _query_str = parts[1] if len(parts) == 2 else ""
            number = int(parts[0])
        return (number, _query_str)

    number = 1
    autocompleted = False
    if taxon_name.startswith("id:"):
        autocompleted = True
        taxon_query_str = taxon_name.split(":")[1]
    else:
        taxon_query_str = taxon_name
    if with_number:
        if not autocompleted:
            # Handle number in taxon_query_str from message-based `,img` command
            # or else first word is a number in non-autocompleted taxon argument
            # from `/taxon image`
            if taxon_query_str:
                number, taxon_query_str = parse_number(taxon_query_str)
        combined_query = await combine_query(
            ctx, taxon_query_str, query, require_taxon=require_taxon
        )
        return (number, combined_query)

    combined_query = await combine_query(
        ctx, taxon_query_str, query, require_taxon=require_taxon
    )
    return combined_query
