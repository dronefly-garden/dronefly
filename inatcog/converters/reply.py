"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter


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

        if not query_str:
            if ref:
                if not msg:
                    raise LookupError("Message replied to could not be retrieved.")
                raise LookupError("I don't know how to reply to that kind of message.")
            raise BadArgument("Your request is empty.")

        return await NaturalQueryConverter.convert(ctx, query_str)
