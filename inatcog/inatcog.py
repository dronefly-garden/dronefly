"""Module to access iNaturalist API."""

from abc import ABC
import re
from typing import AsyncIterator, Tuple
import asyncio
import discord
from redbot.core import checks, commands, Config
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from pyparsing import ParseException
from .api import INatAPI
from .common import grouper, LOG
from .embeds import make_embed, sorry
from .inat_embeds import INatEmbeds
from .last import INatLinkMsg
from .obs import get_obs_fields, maybe_match_obs, PAT_OBS_LINK
from .parsers import RANK_EQUIVALENTS, RANK_KEYWORDS
from .taxa import INatTaxaQuery, get_taxon_fields
from .users import get_user_from_json, PAT_USER_LINK, User


class InheritableBoolConverter(commands.Converter):
    """Convert truthy or 'inherit' to True, False, or None (inherit)."""

    async def convert(self, ctx, argument):
        lowered = argument.lower()
        if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
            return True
        if lowered in ("no", "n", "false", "f", "0", "disable", "off"):
            return False
        if lowered in ("i", "inherit", "inherits", "inherited"):
            return None
        raise commands.BadArgument(
            f'{argument} is not a recognized boolean option or "inherit"'
        )


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    See https://github.com/mikeshardmind/SinbadCogs/blob/v3/rolemanagement/core.py
    """

    pass  # pylint: disable=unnecessary-pass


class INatCog(INatEmbeds, commands.Cog, metaclass=CompositeMetaClass):
    """An iNaturalist commands cog."""

    def __init__(self, bot):
        self.bot = bot
        self.api = INatAPI()
        self.taxa_query = INatTaxaQuery(self.api)
        self.config = Config.get_conf(self, identifier=1607)
        # TODO: generalize & make configurable
        self.config.register_guild(
            autoobs=False,
            project_emojis={33276: "<:discord:638537174048047106>", 15232: ":poop:"},
        )
        self.config.register_user(inat_user_id=None)
        self.config.register_channel(autoobs=None)
        super().__init__()

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass  # pylint: disable=unnecessary-pass

    @inat.group(invoke_without_command=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs(self, ctx, state: InheritableBoolConverter):
        """Set auto-observation mode for channel.
        `autoobs on`
        `autoobs off`
        `autoobs inherit` (i.e. inherits from server)
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.channel(ctx.channel)
        await config.autoobs.set(state)

        if state is None:
            server_state = await self.config.guild(ctx.guild).autoobs()
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if state else "off"
        await ctx.send(f"Channel observation auto-preview is {value}.")
        return

    @autoobs.command()
    @checks.admin_or_permissions(manage_messages=True)
    async def server(self, ctx, state: bool):
        """Set auto-observation mode for server.
        `autoobs server on`
        `autoobs server off`
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.autoobs.set(state)
        await ctx.send(
            f"Server observation auto-preview is {'on' if state else 'off'}."
        )
        return

    @autoobs.command()
    async def show(self, ctx):
        """Show auto-observation mode for channel & server.
        `autoobs show`
        """
        if ctx.author.bot or ctx.guild is None:
            return

        server_config = self.config.guild(ctx.guild)
        server_state = await server_config.autoobs()
        await ctx.send(
            f"Server observation auto-preview is {'on' if server_state else 'off'}."
        )
        channel_config = self.config.channel(ctx.channel)
        channel_state = await channel_config.autoobs()
        if channel_state is None:
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if channel_state else "off"
        await ctx.send(f"Channel observation auto-preview is {value}.")
        return

    @inat.command()
    async def last(self, ctx, kind, display=None):
        """Lookup iNat links contained in recent messages.

        `[p]inat last observation`
        `[p]inat last obs`
        > Displays a summary of the last mentioned observation.
        `[p]inat last obs map`
        `[p]inat last obs m`
        > Displays the map for the last mentioned observation.
        `[p]inat last obs taxon`
        `[p]inat last obs t`
        > Displays the taxon for last mentioned observation.
        `[p]inat last obs` *rank*, e.g.
        `[p]inat last obs family`
        > Displays the taxon for an ancestor rank of the last mentioned observation.

        Also, `[p]last` is an alias for `[p]inat last`, *provided the bot owner has added it*.
        """

        if kind in ("obs", "observation"):
            try:
                msgs = await ctx.history(limit=1000).flatten()
                inat_link_msg = INatLinkMsg(self.api)
                last = await inat_link_msg.get_last_obs_msg(msgs)
            except StopIteration:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return None

            if display:
                if display in ("t", "taxon"):
                    if last and last.obs and last.obs.taxon:
                        await ctx.send(embed=await self.make_taxa_embed(last.obs.taxon))
                elif display in ("m", "map"):
                    if last and last.obs and last.obs.taxon:
                        await ctx.send(
                            embed=await self.make_map_embed([last.obs.taxon])
                        )
                elif display in RANK_KEYWORDS:
                    rank = RANK_EQUIVALENTS.get(display) or display
                    if last.obs.taxon.rank == rank:
                        await ctx.send(embed=await self.make_taxa_embed(last.obs.taxon))
                        return
                    if last.obs.taxon:
                        full_record = get_taxon_fields(
                            await self.api.get_taxa(last.obs.taxon.taxon_id)["results"][
                                0
                            ]
                        )
                        ancestor = await self.taxa_query.get_taxon_ancestor(
                            full_record, display
                        )
                        if ancestor:
                            await ctx.send(embed=await self.make_taxa_embed(ancestor))
                        else:
                            await ctx.send(
                                embed=sorry(
                                    apology=f"The last observation has no {rank} ancestor."
                                )
                            )
                    else:
                        await ctx.send(
                            embed=sorry(apology="The last observation has no taxon.")
                        )
                else:
                    await ctx.send_help()
                    return
            else:
                # By default, display the observation embed for the matched last obs.
                await ctx.send(embed=await self.make_last_obs_embed(ctx, last))
                if last and last.obs and last.obs.sound:
                    await self.maybe_send_sound_url(ctx.channel, last.obs.sound)
        elif kind in ("t", "taxon"):
            try:
                msgs = await ctx.history(limit=1000).flatten()
                inat_link_msg = INatLinkMsg(self.api)
                last = await inat_link_msg.get_last_taxon_msg(msgs)
            except StopIteration:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return None

            if display:
                if display in ("m", "map"):
                    if last and last.taxon:
                        await ctx.send(embed=await self.make_map_embed([last.taxon]))
                elif display in RANK_KEYWORDS:
                    rank = RANK_EQUIVALENTS.get(display) or display
                    if last.taxon.rank == rank:
                        await ctx.send(embed=await self.make_taxa_embed(last.taxon))
                        return
                    if last.taxon:
                        full_record = get_taxon_fields(
                            await self.api.get_taxa(last.taxon.taxon_id)["results"][0]
                        )
                        ancestor = await self.taxa_query.get_taxon_ancestor(
                            full_record, display
                        )
                        if ancestor:
                            await ctx.send(embed=await self.make_taxa_embed(ancestor))
                        else:
                            await ctx.send(
                                embed=sorry(
                                    apology=f"The last taxon has no {rank} ancestor."
                                )
                            )
                    else:
                        await ctx.send(
                            embed=sorry(
                                apology="Lookup failed using the last taxon link."
                            )
                        )
                else:
                    await ctx.send_help()
                    return
            else:
                # By default, display the embed for the matched last taxon.
                await ctx.send(embed=await self.make_taxa_embed(last.taxon))
        else:
            await ctx.send_help()
            return

    @inat.command()
    async def link(self, ctx, *, query):
        """Look up an iNat link and summarize its contents in an embed.

        e.g.
        ```
        [p]inat link https://inaturalist.org/observations/#
           -> an embed summarizing the observation link
        ```
        """
        mat = re.search(PAT_OBS_LINK, query)
        if mat:
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            url = mat["url"]

            results = (
                await self.api.get_observations(obs_id, include_new_projects=True)
            )["results"]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(ctx.guild, obs, url))
            if obs and obs.sound:
                await self.maybe_send_sound_url(ctx.channel, obs.sound)
        else:
            await ctx.send(embed=sorry())

    @inat.command()
    async def map(self, ctx, *, query):
        """Generate an observation range map of one or more species.

        **Examples:**
        ```
        [p]inat map polar bear
        [p]inat map 24255,24267
        [p]inat map boreal chorus frog,western chorus frog
        ```
        """

        if not query:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxa_query.query_taxa(query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_map_embed(taxa))

    @inat.command()
    async def obs(self, ctx, *, query):
        """Look up an iNat observation and summarize its contents in an embed.

        e.g.
        ```
        [p]inat obs #
           -> an embed summarizing the numbered observation
        [p]inat obs https://inaturalist.org/observations/#
           -> an embed summarizing the observation link (minus the preview,
              which Discord provides itself)
        ```
        """

        obs, url = await maybe_match_obs(self.api, query, id_permitted=True)
        # Note: if the user specified an invalid or deleted id, a url is still
        # produced (i.e. should 404).
        if url:
            await ctx.send(
                embed=await self.make_obs_embed(ctx.guild, obs, url, preview=False)
            )
            if obs and obs.sound:
                await self.maybe_send_sound_url(ctx.channel, obs.sound)
            return

        await ctx.send(embed=sorry())
        return

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

    @inat.command()
    async def taxon(self, ctx, *, query):
        """Look up the taxon best matching the query.

        - Match the taxon with the given iNat id#.
        - Match words that start with the terms typed.
        - Exactly match words enclosed in double-quotes.
        - Match a taxon 'in' an ancestor taxon.
        - Filter matches by rank keywords before or after other terms.
        - Match the AOU 4-letter code (if it's in iNat's Taxonomy).
        **Examples:**
        ```
        [p]inat taxon bear family
           -> Ursidae (Bears)
        [p]inat taxon prunella
           -> Prunella (self-heals)
        [p]inat taxon prunella in animals
           -> Prunella
        [p]inat taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        Also, `[p]sp`, `[p]ssp`, `[p]family`, `[p]subfamily`, etc. are
        shortcuts for the corresponding `[p]inat taxon` *rank* commands
        (provided the bot owner has created those aliases).
        """

        if not query:
            await ctx.send_help()
            return

        try:
            taxon = await self.taxa_query.query_taxon(query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_taxa_embed(taxon))

    @inat.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def useradd(self, ctx, discord_user: discord.User, inat_user):
        """Add user as an iNat user."""
        config = self.config.user(discord_user)

        inat_user_id = await config.inat_user_id()
        if inat_user_id:
            await ctx.send("iNat user already known.")
            return

        mat_link = re.search(PAT_USER_LINK, inat_user)
        match = mat_link and (mat_link["user_id"] or mat_link["login"])
        if match:
            user_query = match
        else:
            user_query = inat_user

        user = None
        response = self.api.get_users(user_query)
        if response and response["results"]:
            user = get_user_from_json(response["results"][0])
            LOG.info(user)
            mat_login = user_query.lower()
            mat_id = int(user_query) if user_query.isnumeric() else None
            if not ((user.login == mat_login) or (user.user_id == mat_id)):
                user = None

        if not user:
            await ctx.send("iNat user not found.")
            return

        await config.inat_user_id.set(user.user_id)
        await ctx.send(
            f"{discord_user.display_name} is added as {user.display_name()}."
        )

    @inat.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def userdel(self, ctx, discord_user: discord.User):
        """Remove user as an iNat user."""
        config = self.config.user(discord_user)
        if not await config.inat_user_id():
            ctx.send("iNat user not known.")
            return
        await config.inat_user_id.clear()
        await ctx.send("iNat user removed.")

    @checks.admin_or_permissions(manage_roles=True)
    @inat.command()
    async def userlist(self, ctx):
        """List users with known iNat ids is known."""
        all_names = [
            f"{duser.display_name} is {iuser.display_name()}"
            async for (duser, iuser) in self.get_user_pairs()
        ]

        pages = ["\n".join(filter(None, names)) for names in grouper(all_names, 10)]
        embeds = [make_embed(description=page) for page in pages]
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @inat.command()
    async def usershow(self, ctx, discord_user: discord.User):
        """Show user if their iNat id is known."""
        config = self.config.user(discord_user)
        inat_user_id = await config.inat_user_id()
        if not inat_user_id:
            await ctx.send("iNat user not known.")
            return
        user = None
        response = self.api.get_users(inat_user_id)
        if response and response["results"] and len(response["results"]) == 1:
            user = get_user_from_json(response["results"][0])
        if not user:
            await ctx.send("iNat user id lookup failed.")
            return
        await ctx.send(
            embed=make_embed(
                description=f"{discord_user.display_name} is {user.profile_link()}"
            )
        )

    async def get_user_pairs(self) -> AsyncIterator[Tuple[discord.User, User]]:
        """
        yields:
            discord.User, User
        """

        all_users = await self.config.all_users()

        for discord_id in all_users:
            discord_user = await self.bot.fetch_user(discord_id)
            user_json = self.api.get_users(all_users[discord_id]["inat_user_id"])
            inat_user = None
            if user_json:
                results = user_json["results"]
                if results:
                    LOG.info(results[0])
                    inat_user = get_user_from_json(results[0])
                    # TODO: replace quick-and-dirty rate limit with something reasonable
                    await asyncio.sleep(0.2)

            yield (discord_user, inat_user)
