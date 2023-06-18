"""Listeners module for inatcog."""
from attrs import define
from typing import Optional, Tuple, Union
import asyncio
import contextlib
from copy import copy
import logging
import re

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import BadArgument
from .client import iNatClient
from .converters.base import NaturalQueryConverter
from .embeds.common import NoRoomInDisplay
from .embeds.inat import INatEmbed, INatEmbeds, REACTION_EMOJI
from .interfaces import MixinMeta
from .obs import maybe_match_obs
from .utils import has_valid_user_config

logger = logging.getLogger("red.dronefly." + __name__)

# Minimum 4 characters, first dot must not be followed by a space. Last dot
# must not be preceded by a space.
DOT_TAXON_PAT = re.compile(r"(^|\s)\.(?P<query>[^\s\.].{2,}?[^\s\.])\.(\s|$)")
KNOWN_REACTION_EMOJIS = REACTION_EMOJI.values()
UNKNOWN_REACTION_MSG = "Not a known reaction."

# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981


@define
class PartialMessage:
    """Partial Message to satisfy bot & guild checks."""

    author: discord.User
    guild: discord.Guild


@define
class PartialContext:
    "Partial Context synthesized from objects passed into listeners."
    bot: Red
    guild: discord.Guild
    channel: discord.ChannelType
    author: discord.User
    message: Optional[Union[discord.Message, PartialMessage]]
    command: Optional[str] = ""
    assume_yes: bool = True
    interaction: Optional[discord.Interaction] = None
    inat_client: iNatClient = None


class Listeners(INatEmbeds, MixinMeta):
    """Listeners mixin for inatcog."""

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Handle links to iNat."""
        await self._ready_event.wait()
        if message.author.bot:
            return

        guild = message.guild
        channel = message.channel

        # Autoobs and dot_taxon features both need embed_links:
        if guild:
            if not channel.permissions_for(guild.me).embed_links:
                return
            guild_config = self.config.guild(guild)
            server_listen_scope = await guild_config.listen()
            if server_listen_scope is False or (
                server_listen_scope is None
                and not isinstance(message.channel, discord.Thread)
            ):
                return

            # - on_message_without_command only ignores bot prefixes for this instance
            # - implementation as suggested by Trusty:
            #   - https://cogboard.red/t/approved-dronefly/541/5?u=syntheticbee
            bot_prefixes = await guild_config.bot_prefixes()

            if bot_prefixes:
                prefixes = r"|".join(
                    re.escape(bot_prefix) for bot_prefix in bot_prefixes
                )
                prefix_pattern = re.compile(r"^({prefixes})".format(prefixes=prefixes))
                if re.match(prefix_pattern, message.content):
                    return

        channel_autoobs = not guild or await self.config.channel(channel).autoobs()
        if channel_autoobs is None:
            autoobs = await guild_config.autoobs()
        else:
            autoobs = channel_autoobs

        if autoobs:
            ctx = PartialContext(
                self.bot, guild, channel, message.author, message, "msg autoobs", None
            )
            obs, url = await maybe_match_obs(self, ctx, message.content)
            if obs:
                # Only output if an observation is found
                async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                    ctx.inat_client = inat_client
                    embed = await self.make_obs_embed(ctx, obs, url, preview=False)
                    await self.send_obs_embed(ctx, embed, obs)
                    self.bot.dispatch("commandstats_action", ctx)

        channel_dot_taxon = not guild or await self.config.channel(channel).dot_taxon()
        if channel_dot_taxon is None:
            dot_taxon = await guild_config.dot_taxon()
        else:
            dot_taxon = channel_dot_taxon

        if dot_taxon:
            mat = re.search(DOT_TAXON_PAT, message.content)
            if mat:
                msg = None
                ctx = PartialContext(
                    self.bot,
                    guild,
                    channel,
                    message.author,
                    message,
                    "msg dot_taxon",
                    None,
                )
                async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                    ctx.inat_client = inat_client
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
                            embed=await self.get_taxa_embed(ctx, query_response)
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

        def fake_command_context(message, command, member):
            fake_command_message = PartialMessage(member, message.guild)
            ctx = PartialContext(
                self.bot,
                message.guild,
                message.channel,
                member,
                fake_command_message,
                command,
                None,
            )
            return ctx

        def dispatch_commandstats(ctx):
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
                command = "react taxonomy"
                # TODO: DRY up with a context manager:
                ctx = fake_command_context(message, command, member)
                async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                    ctx.inat_client = inat_client
                    await self.maybe_update_taxonomy(ctx, msg)
                    dispatch_commandstats(ctx)
            elif not inat_embed.has_places():
                if str(emoji) == REACTION_EMOJI["self"]:
                    command = "react self"
                    ctx = fake_command_context(message, command, member)
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        await self.maybe_update_user(
                            ctx, msg, member=member, action=action
                        )
                        dispatch_commandstats(ctx)
                elif str(emoji) == REACTION_EMOJI["user"]:
                    ctx = PartialContext(
                        self.bot, message.guild, message.channel, member, None
                    )
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        await self.maybe_update_user_by_name(
                            ctx, msg=msg, member=member
                        )
                        dispatch_commandstats(ctx)
            if not (inat_embed.has_users() or inat_embed.has_not_by_users()):
                if str(emoji) == REACTION_EMOJI["home"]:
                    command = "react home"
                    ctx = fake_command_context(message, command, member)
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        await self.maybe_update_place(ctx, msg, member, action)
                        dispatch_commandstats(ctx)
                elif str(emoji) == REACTION_EMOJI["place"]:
                    command = "react place"
                    ctx = fake_command_context(message, command, member)
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        await self.maybe_update_place_by_name(ctx, msg, member)
                        dispatch_commandstats(ctx)
        except NoRoomInDisplay as err:
            if message.id not in self.predicate_locks:
                self.predicate_locks[message.id] = asyncio.Lock()
            async with self.predicate_locks[message.id]:
                error_message = await message.channel.send(err.args[0])
                await asyncio.sleep(15)
                with contextlib.suppress(discord.HTTPException):
                    await error_message.delete()
        except Exception:
            logger.error(
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
        if str(payload.emoji) not in KNOWN_REACTION_EMOJIS:
            raise ValueError(UNKNOWN_REACTION_MSG)
        guild_id = payload.guild_id or 0
        if not guild_id:
            # in DM
            member = self.bot.get_user(payload.user_id)
        else:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            # defensive: not possible?
            if member is None:
                raise ValueError("User is not a guild member.")
        if member.bot:
            raise ValueError("User is a bot.")
        if self.member_as[(guild_id, member.id)].spammy:
            logger.info(
                "Spammy: %d-%d-%d; ignored reaction: %s",
                guild_id,
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
            if guild_id and not channel.permissions_for(guild.me).read_message_history:
                raise ValueError(
                    "Message can't be read without read_message_history permission."
                ) from err
            try:
                # Reacting to old messages is an API call, so is a privilege only
                # extended to users added in this server.
                if await has_valid_user_config(self, member, anywhere=False):
                    # TODO: antispam to prevent exceeded fetch messages > 24 hrs
                    # rate limit. We need different buckets for different classes
                    # of use:
                    # - reasonable limit globally over 24 hrs
                    # - reasonable limit per member over 24 hrs
                    logger.debug(
                        "Handling reaction %s by %d to uncached message: %s-%s",
                        payload.channel_id,
                        payload.message_id,
                        payload.emoji,
                        member.id,
                    )
                    message = await channel.fetch_message(payload.message_id)
                else:
                    raise ValueError(
                        "Discarded reaction to uncached message by member not known in this server."
                    ) from err
            except discord.errors.NotFound:
                raise ValueError(
                    "Message was deleted before reaction handled."
                ) from err
        if message.author != self.bot.user:
            raise ValueError("Reaction is not to our own message.")
        self.member_as[(guild_id, member.id)].stamp()
        return (member, message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions added to bot messages."""
        try:
            (member, message) = await self.maybe_get_reaction(payload)
        except ValueError as err:
            if self._log_ignored_reactions and str(err) != UNKNOWN_REACTION_MSG:
                logger.debug(str(err) + "\n" + repr(payload))
            return
        await self.handle_member_reaction(payload.emoji, member, message, "add")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions removed from bot messages."""
        try:
            (member, message) = await self.maybe_get_reaction(payload)
        except ValueError as err:
            if self._log_ignored_reactions and str(err) != UNKNOWN_REACTION_MSG:
                logger.debug(str(err) + "\n" + repr(payload))
            return
        await self.handle_member_reaction(payload.emoji, member, message, "remove")
