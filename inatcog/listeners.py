"""Listeners module for inatcog."""
import re
from typing import Union
import discord
from redbot.core import commands
from .inat_embeds import INatEmbeds
from .interfaces import MixinMeta
from .obs import maybe_match_obs
from .taxa import (
    get_taxon_fields,
    format_user_taxon_counts,
    PAT_TAXON_LINK,
    TAXON_COUNTS_HEADER,
    TAXON_COUNTS_HEADER_PAT,
)


class Listeners(INatEmbeds, MixinMeta):
    """Listeners mixin for inatcog."""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle links to iNat."""
        if message.author.bot or message.guild is None:
            return

        guild = message.guild
        channel = message.channel
        channel_autoobs = await self.config.channel(channel).autoobs()
        if channel_autoobs is None:
            autoobs = await self.config.guild(guild).autoobs()
        else:
            autoobs = channel_autoobs
        # FIXME: should ignore all bot prefixes of the server instead of hardwired list
        if autoobs and re.match(r"^[^;./,]", message.content):
            obs, url = await maybe_match_obs(self.api, message.content)
            # Only output if an observation is found
            if obs:
                await message.channel.send(
                    embed=await self.make_obs_embed(guild, obs, url, preview=False)
                )
                if obs and obs.sound:
                    await self.maybe_send_sound_url(channel, obs.sound)
        return

    async def handle_member_reaction(
        self, reaction: discord.Reaction, member: discord.Member, action: str
    ):
        """Central handler for member reactions."""
        # TODO: should be in taxa.py
        async def get_taxon(taxon_id):
            taxon_record = (await self.api.get_taxa(taxon_id))["results"][0]
            return get_taxon_fields(taxon_record)

        async def update_totals(cog, description, taxon, inat_user, action, counts_pat):
            # Add/remove always results in a change to totals, so remove:
            description = re.sub(
                r"\n\[[0-9 \(\)]+?\]\(.*?\) \*total\*", "", description
            )

            matches = re.findall(
                r"\n\[[0-9 \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
            )
            if action == "remove":
                # Remove the header if last one and the user's count:
                if len(matches) == 1:
                    description = re.sub(TAXON_COUNTS_HEADER_PAT, "", description)
                description = re.sub(counts_pat + r".*?((?=\n)|$)", "", description)
            else:
                # Add the header if first one and the user's count:
                if not matches:
                    description += "\n" + TAXON_COUNTS_HEADER
                formatted_counts = await format_user_taxon_counts(cog, inat_user, taxon)
                description += "\n" + formatted_counts

            matches = re.findall(
                r"\n\[[0-9 \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
            )
            # Total added only if more than one user:
            if len(matches) > 1:
                formatted_counts = await format_user_taxon_counts(
                    cog, ",".join(matches), taxon
                )
                description += f"\n{formatted_counts}"
                return description
            return description

        msg = reaction.message
        embeds = msg.embeds
        if not embeds:
            return

        if reaction.emoji == "#️⃣":  # Add/remove counts
            try:
                inat_user = await self.user_table.get_user(member)
                counts_pat = r"(\n|^)\[[0-9 \(\)]+\]\(.*?\) " + inat_user.login
            except LookupError:
                return
            embed = embeds[0]
            url = embed.url
            if not url:
                return
            mat = re.match(PAT_TAXON_LINK, url)
            if not mat:
                return
            taxon_id = mat["taxon_id"]
            if not taxon_id:
                return

            # Observed by count add/remove for taxon:
            description = embed.description or ""
            mat = re.search(counts_pat, description)

            if (mat and (action == "remove")) or (not mat and (action == "add")):
                taxon = await get_taxon(taxon_id)
                embed.description = await update_totals(
                    self, description, taxon, inat_user, action, counts_pat
                )
                await msg.edit(embed=embed)

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ) -> None:
        """Central handler for reactions added to embeds."""
        if (
            user.bot
            or isinstance(user, discord.User)
            or reaction.message.author != self.bot.user
        ):
            return
        await self.handle_member_reaction(reaction, user, "add")

    @commands.Cog.listener()
    async def on_reaction_remove(
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ) -> None:
        """Central handler for reactions removed from embeds."""
        if (
            user.bot
            or isinstance(user, discord.User)
            or reaction.message.author != self.bot.user
        ):
            return
        await self.handle_member_reaction(reaction, user, "remove")
