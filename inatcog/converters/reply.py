"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter

# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981


class EmptyArgument(BadArgument):
    """Argument to a command is empty."""


class TaxonReplyConverter:
    """Use replied to bot message as a part of the query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = ""):
        """Default to taxon from replied to bot message."""
        async def get_query_from_ref_msg(ref, query_str: str):
            """Return a query string from the referenced embed."""
            msg = ref.cached_message
            if not msg:
                # See comment below for why the user won't see this message with our current approach:
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
            if msg and msg.embeds:
                inat_embed = INatEmbed.from_discord_embed(msg.embeds[0])
                if query_str:
                    # Fully parse the user's parameters to check validity, then
                    # combine it with the parameters from the embed back into a
                    # new query_str.
                    reply_query = await NaturalQueryConverter.convert(ctx, query_str)
                    query_str = str(inat_embed.query(reply_query))
                else:
                    # Otherwise, just derive a query_str from the embed.
                    query_str = str(inat_embed.query())
            if not query_str:
                if not msg:
                    raise BadArgument("I couldn't fetch the message for that reply.")
                raise BadArgument(
                    "I couldn't recognize the message content for that reply."
                )
            return query_str

        ref = ctx.message.reference
        query_str = argument
        if ref:
            query_str = await get_query_from_ref_msg(ref, query_str)
        if not query_str:
            raise EmptyArgument("This command requires an argument.")

        return await NaturalQueryConverter.convert(ctx, query_str)
