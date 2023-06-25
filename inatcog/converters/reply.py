"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from dronefly.core.query.query import EMPTY_QUERY
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter

# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981


class EmptyArgument(BadArgument):
    """Argument to a command is empty."""


class TaxonReplyConverter:
    """Use replied to bot message as a part of the query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = "", allow_empty: bool = False):
        """Default to taxon from replied to bot message."""

        async def get_query_from_ref_msg(ref, query_str: str):
            """Return a query string from the referenced embed."""
            msg = ref.cached_message
            _query_str = query_str
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
                        raise BadArgument(
                            "I couldn't fetch the message for that reply."
                        )
                    raise BadArgument(
                        "I couldn't recognize the message content for that reply."
                    )
            return _query_str

        ref = ctx.message.reference
        if ref:
            query_str = await get_query_from_ref_msg(ref, argument)
        else:
            query_str = argument
        if not query_str:
            if allow_empty:
                return EMPTY_QUERY
            else:
                raise EmptyArgument("This command requires an argument.")

        return await NaturalQueryConverter.convert(ctx, query_str)
