"""Listeners module for inatcog."""
from collections import namedtuple
import asyncio
import contextlib
import re
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
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Handle links to iNat."""
        await self._ready_event.wait()
        if message.author.bot or message.guild is None:
            return

        guild = message.guild
        channel = message.channel
        guild_config = self.config.guild(guild)

        # - on_message_without_command only ignores bot prefixes for this instance
        # - implementation as suggested by Trusty:
        #   - https://cogboard.red/t/approved-dronefly/541/5?u=syntheticbee
        bot_prefixes = await guild_config.bot_prefixes()

        if bot_prefixes:
            prefixes = r"|".join(re.escape(bot_prefix) for bot_prefix in bot_prefixes)
            prefix_pattern = re.compile(r"^({prefixes})".format(prefixes=prefixes))
            if re.match(prefix_pattern, message.content):
                return

        channel_autoobs = await self.config.channel(channel).autoobs()
        if channel_autoobs is None:
            autoobs = await guild_config.autoobs()
        else:
            autoobs = channel_autoobs

        if autoobs:
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
        self,
        emoji: discord.PartialEmoji,
        member: discord.Member,
        message: discord.Message,
        action: str,
    ):
        """Central handler for member reactions."""

        def get_ids(embed):
            """Match taxon_id & optional place_id/user_id."""
            taxon_id = None
            place_id = None
            user_id = None
            url = embed.url
            if url:
                mat = re.match(PAT_TAXON_LINK, url)
                if not mat:
                    mat = re.match(PAT_OBS_TAXON_LINK, url)
                    if mat:
                        place_id = mat["place_id"]
                        user_id = mat["user_id"]
                if mat:
                    taxon_id = mat["taxon_id"]
            return (taxon_id, place_id, user_id)

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
                if re.search(r"\*total\*", embed.description):
                    embed.set_footer(
                        text="User counts may not add up to "
                        "the total if they changed since they were added. "
                        "Remove, then add them again to update their counts."
                    )
                else:
                    embed.set_footer(text="")
                await msg.edit(embed=embed)

        async def maybe_update_member_by_name(
            msg: discord.Message, embed: discord.Embed, member: discord.Member
        ):
            """Prompt for a user by name and update the embed if provided & valid."""
            try:
                await self.user_table.get_user(member)
            except LookupError:
                return
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

                await maybe_update_member(msg, embed, who.member, "toggle")

        async def maybe_send_place_by_name(
            msg: discord.Message, member: discord.Member
        ):
            """Prompt user for place by name and send an embed if provided & valid."""
            try:
                await self.user_table.get_user(member)
            except LookupError:
                return
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

        async def update_totals(cog, description, taxon, inat_user, action, counts_pat):
            """Update the totals for the embed."""
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

        embeds = message.embeds
        if not embeds:
            return
        embed = embeds[0]
        taxon_id, place_id, user_id = get_ids(embed)
        if not taxon_id:
            return

        if str(emoji) == "#️⃣":  # Add/remove counts for self
            await maybe_update_member(message, embed, member, action)
        elif str(emoji) == "📝":  # Add/remove counts by name
            await maybe_update_member_by_name(message, embed, member)
        elif str(emoji) == "📍":
            await maybe_send_place_by_name(message, member)

    async def maybe_get_reaction(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> (discord.Member, discord.Message):
        """Return reaction member & message if valid."""
        await self._ready_event.wait()
        if not payload.guild_id:
            raise ValueError("Reaction is not on a guild channel.")
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            raise ValueError("User is not a guild member.")
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            raise ValueError("Reaction is not to our own message.")
        return (member, message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions added to bot messages."""
        try:
            (member, message) = await self.maybe_get_reaction(payload)
        except ValueError:
            return
        await self.handle_member_reaction(payload.emoji, member, message, "add")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions removed from bot messages."""
        try:
            (member, message) = await self.maybe_get_reaction(payload)
        except ValueError:
            return
        await self.handle_member_reaction(payload.emoji, member, message, "remove")
