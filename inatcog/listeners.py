"""Listeners module for inatcog."""
from typing import NamedTuple, Union
import asyncio
import contextlib
import re
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import BadArgument
from .common import LOG
from .converters import NaturalCompoundQueryConverter
from .embeds import NoRoomInDisplay
from .inat_embeds import INatEmbeds
from .interfaces import MixinMeta
from .obs import maybe_match_obs
from .taxa import (
    TAXON_COUNTS_HEADER_PAT,
    TAXON_NOTBY_HEADER_PAT,
    TAXON_PLACES_HEADER_PAT,
)

# Minimum 4 characters, first dot must not be followed by a space. Last dot
# must not be preceded by a space.
DOT_TAXON_PAT = re.compile(r"(^|\s)\.(?P<query>[^\s\.].{2,}?[^\s\.])\.(\s|$)")


class PartialAuthor(NamedTuple):
    """Partial Author to satisfy bot check."""

    bot: bool


class PartialMessage(NamedTuple):
    """Partial Message to satisfy bot & guild checks."""

    author: PartialAuthor
    guild: discord.Guild


class PartialContext(NamedTuple):
    "Partial Context synthesized from objects passed into listeners."

    bot: Red
    guild: discord.Guild
    channel: discord.ChannelType
    author: discord.User
    message: Union[discord.Message, PartialMessage] = None
    command: str = ""
    assume_yes: bool = True


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

        # Autoobs and dot_taxon features both need embed_links:
        if not channel.permissions_for(guild.me).embed_links:
            return
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
            ctx = PartialContext(
                self.bot, guild, channel, message.author, message, "msg autoobs"
            )
            obs, url = await maybe_match_obs(self, ctx, message.content)
            # Only output if an observation is found
            if obs:
                await message.channel.send(
                    embed=await self.make_obs_embed(guild, obs, url, preview=False)
                )
                if obs and obs.sounds:
                    await self.maybe_send_sound_url(channel, obs.sounds[0])
                self.bot.dispatch("commandstats_action", ctx)

        channel_dot_taxon = await self.config.channel(channel).dot_taxon()
        if channel_dot_taxon is None:
            dot_taxon = await guild_config.dot_taxon()
        else:
            dot_taxon = channel_dot_taxon

        if dot_taxon:
            mat = re.search(DOT_TAXON_PAT, message.content)
            if mat:
                msg = None
                ctx = PartialContext(
                    self.bot, guild, channel, message.author, message, "msg dot_taxon"
                )
                try:
                    query = await NaturalCompoundQueryConverter.convert(
                        ctx, mat["query"]
                    )
                    if query.controlled_term:
                        return
                    filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
                except (BadArgument, LookupError):
                    return
                if query.user or query.place:
                    msg = await channel.send(
                        embed=await self.make_obs_counts_embed(filtered_taxon)
                    )
                    self.add_obs_reaction_emojis(msg)
                else:
                    msg = await channel.send(
                        embed=await self.make_taxa_embed(ctx, filtered_taxon)
                    )
                    self.add_taxon_reaction_emojis(msg, filtered_taxon)
                self.bot.dispatch("commandstats_action", ctx)

    async def handle_member_reaction(
        self,
        emoji: discord.PartialEmoji,
        member: discord.Member,
        message: discord.Message,
        action: str,
    ):
        """Central handler for member reactions."""

        def dispatch_commandstats(message, command):
            partial_author = PartialAuthor(bot=False)
            fake_command_message = PartialMessage(partial_author, message.guild)
            ctx = PartialContext(
                self.bot,
                message.guild,
                message.channel,
                message.author,
                fake_command_message,
                command,
            )
            self.bot.dispatch("commandstats_action", ctx)

        embeds = message.embeds
        if not embeds:
            return
        embed = embeds[0]
        if embed.url:
            taxon_id, place_id, inat_user_id = self.get_inat_url_ids(embed.url)
        else:
            return
        if not taxon_id:
            return

        description = embed.description or ""
        has_users = re.search(TAXON_COUNTS_HEADER_PAT, description)
        has_not_by_users = re.search(TAXON_NOTBY_HEADER_PAT, description)
        has_places = re.search(TAXON_PLACES_HEADER_PAT, description)

        try:
            if str(emoji) == "🇹":
                await self.maybe_update_taxonomy(message, taxon_id)
                dispatch_commandstats(message, "react taxonomy")
            elif has_places is None:
                unobserved = True if has_not_by_users else False
                if str(emoji) == "#️⃣":  # Add/remove counts for self
                    await self.maybe_update_member(
                        message,
                        member,
                        action,
                        taxon_id,
                        place_id,
                        unobserved=unobserved,
                    )
                    dispatch_commandstats(message, "react self")
                elif str(emoji) == "📝":  # Toggle counts by name
                    ctx = PartialContext(
                        self.bot, message.guild, message.channel, member
                    )
                    await self.maybe_update_member_by_name(
                        ctx,
                        msg=message,
                        user=member,
                        taxon_id=taxon_id,
                        place_id=place_id,
                        unobserved=unobserved,
                    )
                    dispatch_commandstats(message, "react user")
            if has_users is None and has_not_by_users is None:
                if str(emoji) == "🏠":
                    await self.maybe_update_place(
                        message, member, action, taxon_id, inat_user_id, member
                    )
                    dispatch_commandstats(message, "react home")
                elif str(emoji) == "📍":
                    await self.maybe_update_place_by_name(
                        message, taxon_id, inat_user_id, member
                    )
                    dispatch_commandstats(message, "react place")
        except NoRoomInDisplay as err:
            if message.id not in self.predicate_locks:
                self.predicate_locks[message.id] = asyncio.Lock()
            async with self.predicate_locks[message.id]:
                error_message = await message.channel.send(err.args[0])
                await asyncio.sleep(15)
                with contextlib.suppress(discord.HTTPException):
                    await error_message.delete()
        except Exception:
            LOG.error(
                "Exception handling %s %s reaction by %s on %s",
                action,
                str(emoji),
                repr(member),
                repr(message),
            )
            raise

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
        try:
            message = next(
                msg for msg in self.bot.cached_messages if msg.id == payload.message_id
            )
        except StopIteration:  # too old; have to fetch it
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                raise ValueError("Message was deleted before reaction handled.")
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
