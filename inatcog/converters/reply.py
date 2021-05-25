"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter


class TaxonReplyConverter:
    """Use replied to bot message as query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = ""):
        """Default to taxon from replied to bot message."""
        ref = ctx.message.reference
        msg = ref.cached_message or await ctx.channel.fetch_message(ref.message_id)
        if msg and msg.embeds:
            inat_embed = INatEmbed.from_discord_embed(msg.embeds[0])
            taxon_id = inat_embed.taxon_id()
            if taxon_id:
                argument += f" of {taxon_id}"
        if not argument:
            raise BadArgument()
        return await NaturalQueryConverter.convert(ctx, argument)
