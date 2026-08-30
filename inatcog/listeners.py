"""Listeners module for inatcog."""

from attrs import define
from datetime import datetime, timedelta, timezone
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
from .menus.generic import EmbedMenu, EmbedSource
from .obs import maybe_match_obs
from dronefly.core.query import prepare_query_for_count, prepare_query_for_taxon
from dronefly.core.query.formatters import (
    get_query_count_formatter,
    get_query_taxon_formatter,
)
from dronefly.discord.embeds import MAX_EMBED_DESCRIPTION_LEN
from dronefly.discord.menus import (
    CountMenu,
    CountSource,
    TaxonMenu,
    TaxonSource,
)

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

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


class Listeners(INatEmbeds, MixinMeta):
    """Listeners mixin for inatcog."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track when users last received the default-mode reminder to enforce the 24hr cooldown
        self._default_prompt_cooldowns: dict[int, datetime] = {}

    async def _handle_auto_response(self, message: discord.Message, coro) -> None:
        """Helper to evaluate member response settings, execute the display coroutine,

        and handle the 'default' mode self-deleting prompt with a 24hr cooldown.
        """
        if message.author.bot:
            return

        if message.guild is None:
            effective_setting = "always"
        else:
            member_setting = await self.config.member(message.author).auto_respond()
            effective_setting = member_setting if member_setting else "default"

        if effective_setting == "never":
            return

        display_message = await coro()

        if display_message and effective_setting == "default":
            now = datetime.now(timezone.utc)
            last_prompted = self._default_prompt_cooldowns.get(message.author.id)

            if not last_prompted or (now - last_prompted) > timedelta(hours=24):
                self._default_prompt_cooldowns[message.author.id] = now

                prefix_list = await self.bot.get_prefix(message)

                mention_regex = re.compile(r"^<@!?\d+>$")
                non_mention = [
                    p for p in prefix_list if not mention_regex.match(p.strip())
                ]

                if non_mention:
                    chosen_prefix = non_mention[0].strip()
                    usage_instruction = f"use `{chosen_prefix}auto`."
                else:
                    mention_prefix = prefix_list[0].strip()
                    usage_instruction = (
                        f"mention the bot (e.g., {mention_prefix} `auto`)."
                    )

                explanation = (
                    "Use `/auto always` or `/auto never` to record "
                    "your preference for automatic displays like this.\n"
                    f"Alternatively, {usage_instruction}\n"
                    "I will not prompt again for 24 hrs.\n"
                )
                try:
                    reminder_msg = await message.reply(explanation)
                    await reminder_msg.delete(delay=60.0)
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Handle links to iNat."""
        await self._ready_event.wait()
        if message.author.bot:
            return

        guild = message.guild
        channel = message.channel

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

            bot_prefixes = await guild_config.bot_prefixes()
            if bot_prefixes:
                prefixes = r"|".join(re.escape(bp) for bp in bot_prefixes)
                if re.match(
                    r"^({prefixes})".format(prefixes=prefixes), message.content
                ):
                    return
        else:
            guild_config = None

        autoobs, autoobs_preview = await self._resolve_autoobs_config(
            guild, channel, guild_config
        )
        if autoobs:
            ctx = PartialContext(
                self.bot, guild, channel, message.author, message, "msg autoobs", None
            )
            obs, url = await maybe_match_obs(self, ctx, message.content)
            if obs:

                async def send_obs_menu():
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        embed = await self.make_obs_embed(
                            ctx, obs, url, preview=autoobs_preview
                        )
                        initial_message_params = {}
                        if obs.sounds:
                            async with self.sound_message_params(
                                ctx.channel, obs.sounds, embed=embed
                            ) as params:
                                if params:
                                    initial_message_params = params
                        if not initial_message_params:
                            initial_message_params["embed"] = embed

                        display_msg = await EmbedMenu(
                            source=EmbedSource([embed]),
                        ).start(ctx=ctx, **initial_message_params)
                        self.bot.dispatch("commandstats_action", ctx)
                        logger.info("autoobs_menu_message = %r", display_msg)
                        return display_msg

                await self._handle_auto_response(message, send_obs_menu)
                return

        dot_taxon = not guild or await self.config.channel(channel).dot_taxon()
        if dot_taxon is None and guild_config:
            dot_taxon = await guild_config.dot_taxon()

        if dot_taxon:
            mat = re.search(DOT_TAXON_PAT, message.content)
            if mat:
                ctx = PartialContext(
                    self.bot,
                    guild,
                    channel,
                    message.author,
                    message,
                    "msg dot_taxon",
                    None,
                )
                try:
                    query = await NaturalQueryConverter.convert(ctx, mat["query"])
                    if query.controlled_term:
                        return
                except (BadArgument, LookupError):
                    return

                async def send_query_menu():
                    async with self.inat_client.set_ctx_from_user(ctx) as inat_client:
                        ctx.inat_client = inat_client
                        try:
                            if query.user or query.place or query.project:
                                query_response = await prepare_query_for_count(
                                    ctx.inat_client, query
                                )
                                for_place = query_response.per == "place"
                                count_formatter = await get_query_count_formatter(
                                    client=ctx.inat_client,
                                    query_response=query_response,
                                )
                                menu = CountMenu(
                                    delete_message_after=False,
                                    clear_reactions_after=True,
                                    timeout=0,
                                    cog=self,
                                    inat_client=ctx.inat_client,
                                    source=CountSource(
                                        count=count_formatter.source.count,
                                        formatter=count_formatter,
                                    ),
                                    for_place=for_place,
                                )
                            else:
                                query_response = await prepare_query_for_taxon(
                                    ctx.inat_client, query
                                )
                                if not query_response.per:
                                    query_response.per = (
                                        "obs"
                                        if (
                                            query_response.user
                                            or not query_response.place
                                        )
                                        else "place"
                                    )
                                formatter_params = {
                                    "lang": ctx.inat_client.ctx.get_inat_user_default(
                                        "inat_lang"
                                    ),
                                    "max_len": MAX_EMBED_DESCRIPTION_LEN,
                                    "with_url": False,
                                }
                                taxon_formatter = await get_query_taxon_formatter(
                                    ctx.inat_client, query_response, **formatter_params
                                )
                                for_place = query_response.per == "place"
                                menu = TaxonMenu(
                                    source=TaxonSource(taxon_formatter),
                                    inat_client=ctx.inat_client,
                                    for_place=for_place,
                                    delete_message_after=False,
                                    clear_reactions_after=True,
                                    timeout=0,
                                    cog=self,
                                )

                            display_msg = await menu.start(ctx=ctx)
                            logger.info("dot_taxon_menu_message = %r", display_msg)
                            self.bot.dispatch("commandstats_action", ctx)
                            return display_msg
                        except LookupError as err:
                            logger.info("%s Ignoring query: %s", err, mat["query"])
                            return None

                await self._handle_auto_response(message, send_query_menu)

    async def _resolve_autoobs_config(
        self, guild, channel, guild_config
    ) -> tuple[bool, bool]:
        """Helper to parse channel vs guild autoobs and preview configurations."""
        if guild:
            channel_autoobs = await self.config.channel(channel).autoobs()
            channel_autoobs_preview = await self.config.channel(
                channel
            ).autoobs_preview()
        else:
            return True, False

        autoobs = (
            channel_autoobs
            if channel_autoobs is not None
            else await guild_config.autoobs()
        )
        autoobs_preview = (
            channel_autoobs_preview
            if channel_autoobs_preview is not None
            else await guild_config.autoobs_prevew()
        )
        return autoobs, autoobs_preview

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

        # TODO: class for interactions? currently just a dict keyed by full
        # message id and content is the parsed inat_embed
        # - this needs two corresponding pieces of code to make it work across cog reloads:
        #   - save all of those interactions in Config when cog is unloaded
        #   - load them from Config when cog is loaded
        full_message_id = (
            f"{message.guild.id}-{message.channel.id}-{message.id}"
            if message.guild
            else f"{message.channel.id}-{message.id}"
        )
        inat_embed = self.interactions.get(full_message_id)
        if not inat_embed:
            inat_embed = INatEmbed.from_discord_embed(message.embeds[0])
            # Maintain a shadow copy of the INatEmbed which is an augmented discord.Embed
            # that knows all of the iNat-specific parts. We never go out to the Discord
            # network from here on until the interaction ends, updating and writing out
            # this copy of the embed from here on.
            self.interactions[full_message_id] = inat_embed
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

    def maybe_get_reaction(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> Tuple[discord.Member, discord.Message]:
        """Return reaction member & message if valid."""
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
        message = next(
            (msg for msg in self.bot.cached_messages if msg.id == payload.message_id),
            None,
        )
        if message:
            if message.author != self.bot.user:
                raise ValueError("Reaction is not to our own message.")
            self.member_as[(guild_id, member.id)].stamp()
        return (member, message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions added to bot messages."""
        await self._ready_event.wait()
        try:
            member, message = self.maybe_get_reaction(payload)
        except ValueError as err:
            if self._log_ignored_reactions and str(err) != UNKNOWN_REACTION_MSG:
                logger.debug(str(err) + "\n" + repr(payload))
            return
        if message:
            await self.handle_member_reaction(payload.emoji, member, message, "add")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.raw_models.RawReactionActionEvent
    ) -> None:
        """Central handler for reactions removed from bot messages."""
        await self._ready_event.wait()
        try:
            member, message = self.maybe_get_reaction(payload)
        except ValueError as err:
            if self._log_ignored_reactions and str(err) != UNKNOWN_REACTION_MSG:
                logger.debug(str(err) + "\n" + repr(payload))
            return
        if message:
            await self.handle_member_reaction(payload.emoji, member, message, "remove")
