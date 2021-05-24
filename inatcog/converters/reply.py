"""Reply converters."""

from redbot.core.commands import BadArgument, Context
from inatcog.embeds.inat import INatEmbed
from .base import NaturalQueryConverter


class TaxonReplyConverter:
    """Use replied to bot message as query."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str = ""):
        """Default to taxon from replied to bot message."""
        if ctx.message.reference:
            ref = ctx.message.reference.cached_message
            if not ref:
                ref = await ctx.channel.fetch_message(ref.message_id)
            if ref and ref.embeds:
                inat_embed = INatEmbed.from_discord_embed(ref.embeds[0])
                taxon_id = inat_embed.taxon_id()
                if taxon_id:
                    argument += f" of {taxon_id}"
        if not argument:
            raise BadArgument()
        return await NaturalQueryConverter.convert(ctx, argument)
