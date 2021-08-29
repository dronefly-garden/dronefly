"""Listeners module for inatcog."""
from typing import NamedTuple, Tuple, Union
import asyncio
import contextlib
from copy import copy
import re
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import BadArgument
from .common import LOG
from .converters.base import NaturalQueryConverter
from .embeds.common import NoRoomInDisplay
from .embeds.inat import INatEmbed, INatEmbeds, REACTION_EMOJI
from .interfaces import MixinMeta
from .obs import maybe_match_obs

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
                embed = await self.make_obs_embed(obs, url, preview=False)
                await self.send_obs_embed(ctx, embed, obs)
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
                    query = await NaturalQueryConverter.convert(ctx, mat["query"])
                    if query.controlled_term:
                        return
                    query_response = await self.query.get(ctx, query)
                except (BadArgument, LookupError):
                    return
                if query.user or query.place or query.project:
                    msg = await channel.send(
                        embed=await self.make_obs_counts_embed(query_response)
                    )
                    await self.add_obs_reaction_emojis(ctx, msg, query_response)
                else:
                    msg = await channel.send(
                        embed=await self.make_taxa_embed(ctx, query_response)
                    )
                    await self.add_taxon_reaction_emojis(ctx, msg, query_response)
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

        if not message.embeds or not message.reactions:
            return
        reaction = next(
            (
                reaction
                for reaction in message.reactions
                if reaction.emoji == str(emoji)
            ),
            None,
        )
        if not reaction or not reaction.me:
            return

        inat_embed = INatEmbed.from_discord_embed(message.embeds[0])
        msg = copy(message)
        msg.embeds[0] = inat_embed

        try:
            if str(emoji) == REACTION_EMOJI["taxonomy"]:
                await self.maybe_update_taxonomy(msg)
                dispatch_commandstats(message, "react taxonomy")
            elif not inat_embed.has_places():
                if str(emoji) == REACTION_EMOJI["self"]:
                    await self.maybe_update_user(msg, member=member, action=action)
                    dispatch_commandstats(message, "react self")
                elif str(emoji) == REACTION_EMOJI["user"]:
                    ctx = PartialContext(
                        self.bot, message.guild, message.channel, member
                    )
                    await self.maybe_update_user_by_name(ctx, msg=msg, member=member)
                    dispatch_commandstats(message, "react user")
            if not (inat_embed.has_users() or inat_embed.has_not_by_users()):
                if str(emoji) == REACTION_EMOJI["home"]:
                    await self.maybe_update_place(msg, member, action)
                    dispatch_commandstats(message, "react home")
                elif str(emoji) == REACTION_EMOJI["place"]:
                    await self.maybe_update_place_by_name(msg, member)
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
    ) -> Tuple[discord.Member, discord.Message]:
        """Return reaction member & message if valid."""
        await self._ready_event.wait()
        if not payload.guild_id:
            raise ValueError("Reaction is not on a guild channel.")
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            raise ValueError("User is not a guild member.")
        if self.member_as[(guild.id, member.id)].spammy:
            LOG.info(
                "Spammy: %d-%d-%d; ignored reaction: %s",
                guild.id,
                payload.channel_id,
                member.id,
                payload.emoji,
            )
            raise ValueError("Member is being spammy")
        channel = self.bot.get_channel(payload.channel_id)
        try:
            message = next(
                msg for msg in self.bot.cached_messages if msg.id == payload.message_id
            )
        except StopIteration as err:  # too old; have to fetch it
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                raise ValueError(
                    "Message was deleted before reaction handled."
                ) from err
        if message.author != self.bot.user:
            raise ValueError("Reaction is not to our own message.")
        self.member_as[(guild.id, member.id)].stamp()
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
