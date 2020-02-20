"""Listeners module for inatcog."""
from collections import namedtuple
import asyncio
import contextlib
import re
from typing import Union
import discord
from redbot.core import commands
from redbot.core.utils.predicates import MessagePredicate
from .converters import ContextMemberConverter
from .embeds import make_embed
from .inat_embeds import INatEmbeds
from .interfaces import MixinMeta
from .obs import maybe_match_obs, PAT_OBS_TAXON_LINK
from .taxa import (
    get_taxon,
    format_place_taxon_counts,
    format_user_taxon_counts,
    PAT_TAXON_LINK,
    TAXON_COUNTS_HEADER,
    TAXON_COUNTS_HEADER_PAT,
)

MockContext = namedtuple("MockContext", "guild, author, channel, bot")


class Listeners(INatEmbeds, MixinMeta):
    """Listeners mixin for inatcog."""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle links to iNat."""
        await self._ready_event.wait()
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

        place_id = None
        user_id = None

        def get_ids(embed):
            url = embed.url
            if not url:
                return
            mat = re.match(PAT_TAXON_LINK, url)
            if not mat:
                mat = re.match(PAT_OBS_TAXON_LINK, url)
                if mat:
                    place_id = mat["place_id"]
                    user_id = mat["user_id"]
            if not mat:
                return
            return (mat["taxon_id"], place_id, user_id)

        async def maybe_update_member(
            msg: discord.Message,
            embed: discord.Embed,
            member: discord.Member,
            action: str,
        ):
            try:
                inat_user = await self.user_table.get_user(member)
                counts_pat = r"(\n|^)\[[0-9 \(\)]+\]\(.*?\) " + inat_user.login
            except LookupError:
                return

            # Observed by count add/remove for taxon:
            description = embed.description or ""
            mat = re.search(counts_pat, description)
            if action == "toggle":
                action = "remove" if mat else "add"

            if (mat and (action == "remove")) or (not mat and (action == "add")):
                taxon = await get_taxon(self, taxon_id)
                embed.description = await update_totals(
                    self, description, taxon, inat_user, action, counts_pat
                )
                await msg.edit(embed=embed)

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
                formatted_counts = await format_user_taxon_counts(
                    cog, inat_user, taxon, place_id
                )
                description += "\n" + formatted_counts

            matches = re.findall(
                r"\n\[[0-9 \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
            )
            # Total added only if more than one user:
            if len(matches) > 1:
                formatted_counts = await format_user_taxon_counts(
                    cog, ",".join(matches), taxon, place_id
                )
                description += f"\n{formatted_counts}"
                return description
            return description

        msg = reaction.message
        embeds = msg.embeds
        if not embeds:
            return
        embed = embeds[0]
        taxon_id, place_id, user_id = get_ids(embed)
        if not taxon_id:
            return

        if reaction.emoji == "#️⃣":  # Add/remove counts for self
            await maybe_update_member(msg, embed, member, action)
        elif reaction.emoji == "📝":  # Add/remove counts by name
            response = None
            query = await msg.channel.send(
                "Add or remove which member (you have 15 seconds to answer)?"
            )
            try:
                response = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(
                        channel=msg.channel, user=member
                    ),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
            else:
                try:
                    await msg.channel.delete_messages((query, response))
                except (discord.HTTPException, AttributeError):
                    # In case the bot can't delete other users' messages:
                    with contextlib.suppress(discord.HTTPException):
                        await query.delete()
            if response:
                ctx = MockContext(msg.guild, member, msg.channel, self.bot)
                try:
                    who = await ContextMemberConverter.convert(ctx, response.content)
                except discord.ext.commands.errors.BadArgument as error:
                    error_msg = await msg.channel.send(error)
                    await asyncio.sleep(15)
                    await error_msg.delete()
                    return

                await maybe_update_member(msg, embeds, who.member, "toggle")
        elif reaction.emoji == "📍":
            response = None
            query = await msg.channel.send(
                "Observation & species counts for which place (you have 15 seconds to answer)?"
            )
            try:
                response = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(
                        channel=msg.channel, user=member
                    ),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
            else:
                try:
                    await msg.channel.delete_messages((query, response))
                except (discord.HTTPException, AttributeError):
                    # In case the bot can't delete other users' messages:
                    with contextlib.suppress(discord.HTTPException):
                        await query.delete()
            if response:
                try:
                    place = await self.place_table.get_place(
                        msg.guild, response.content, member
                    )
                except LookupError as error:
                    error_msg = await msg.channel.send(error)
                    await asyncio.sleep(15)
                    await error_msg.delete()
                    return

                taxon = await get_taxon(self, taxon_id)
                formatted_counts = await format_place_taxon_counts(
                    self, place, taxon, user_id
                )
                place_embed = make_embed(
                    description=f"{taxon.name}: {formatted_counts}"
                )
                await msg.channel.send(embed=place_embed)

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ) -> None:
        """Central handler for reactions added to embeds."""
        await self._ready_event.wait()
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
        await self._ready_event.wait()
        if (
            user.bot
            or isinstance(user, discord.User)
            or reaction.message.author != self.bot.user
        ):
            return
        await self.handle_member_reaction(reaction, user, "remove")
