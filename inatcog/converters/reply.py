"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter

# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981


class EmptyArgument(BadArgument):
    """Argument to a command is empty."""


class TaxonReplyConverter:
    """Use replied to bot message as query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = ""):
        """Default to taxon from replied to bot message."""
        query_str = argument
        ref = ctx.message.reference
        if ref:
            msg = ref.cached_message or await ctx.channel.fetch_message(ref.message_id)
            if msg and msg.embeds:
                inat_embed = INatEmbed.from_discord_embed(msg.embeds[0])
                if query_str:
                    reply_query = await NaturalQueryConverter.convert(ctx, query_str)
                    query_str = str(inat_embed.query(reply_query))
                else:
                    query_str = str(inat_embed.query())

        # We might want to change this at some point in future to make it consistent,
        # i.e. the messages will be shown when the user replied with no arguments
        # but we couldn't fetch the message or find useful content, but not if
        # arguments were supplied. This is because BadArgument always triggers
        # help when the converter is used in the command definition, but we catch
        # and display the message when used in the body of the command (i.e. the
        # "no arguments" case).
        if not query_str:
            if ref:
                if not msg:
                    raise BadArgument("I couldn't fetch the message for that reply.")
                raise BadArgument(
                    "I couldn't recognize the message content for that reply."
                )
            raise EmptyArgument("This command requires an argument.")

        return await NaturalQueryConverter.convert(ctx, query_str)
