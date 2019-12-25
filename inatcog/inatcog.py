"""Module to access iNaturalist API."""

from abc import ABC
from math import ceil
import re
from typing import AsyncIterator, NamedTuple, Tuple, Union
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
from .projects import UserProject
from .taxa import INatTaxaQuery, get_taxon_fields
from .users import PAT_USER_LINK, User

SPOILER_PAT = re.compile(r"\|\|")
DOUBLE_BAR_LIT = "\\|\\|"


class ContextMemberConverter(NamedTuple):
    """Context-aware member converter."""

    member: discord.Member

    @classmethod
    async def convert(cls, ctx: commands.Context, arg: str):
        """Find best match for member from recent messages."""
        if not ctx.guild:
            return

        # Prefer exact match:
        try:
            match = await commands.MemberConverter().convert(ctx, arg)
            return cls(match)
        except commands.BadArgument:
            match = None

        pat = re.escape(arg)

        # Try partial match on name or nick from recent messages for this guild.
        cached_members = {
            str(msg.author.name): msg.author
            for msg in ctx.bot.cached_messages
            if not msg.author.bot
            and ctx.guild == msg.guild
            and ctx.guild.get_member(msg.author.id)
        }
        matches = [
            cached_members[name]
            for name in cached_members
            if re.match(pat, name, re.I)
            or (
                cached_members[name].nick
                and re.match(pat, cached_members[name].nick, re.I)
            )
        ]
        # First match is considered the best match (i.e. more recently active)
        match = ctx.guild.get_member(matches[0].id) if matches else None
        if match:
            return cls(match)

        # Otherwise no partial match from context, & no exact match
        raise commands.BadArgument(
            "No recently active member found. Try exact username or nickname."
        )


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
            user_projects={},
            project_emojis={33276: "<:discord:638537174048047106>", 15232: ":poop:"},
        )
        self.config.register_user(inat_user_id=None)
        self.config.register_channel(autoobs=None)
        super().__init__()

    def cog_unload(self):
        """Cleanup when the cog unloads."""
        self.api.session.detach()

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform.

        Note: When configured as recommended, single word command aliases are
        defined for every `[p]inat` subcommand, `[p]family` is an alias for
        `[p]inat taxon family`, and likewise for all other ranks. See the
        help topics for each subcommand for details.
        """

    @inat.group(invoke_without_command=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs(self, ctx, state: InheritableBoolConverter):
        """Set auto-observation mode for channel (mods only).

        To set the mode for the channel:
        ```
        [p]inat autoobs on
        [p]inat autoobs off
        [p]inat autoobs inherit
        ```
        When `inherit` is specified, channel mode inherits from the server
        setting.
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
        """Set auto-observation mode for server (mods only).

        ```
        [p]inat autoobs server on
        [p]inat autoobs server off
        ```
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

        ```
        [p]inat autoobs show
        ```
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
        """Show info for recently mentioned iNat page:

        ```
        [p]inat last observation
        [p]inat last obs map
        [p]inat last obs taxon
        [p]inat last obs family
        ```
        Keywords can be abbreviated:
        - `obs` for `observation`
        - `m` for `map`
        - `t` for `taxon`
        When configured as recommended, `[p]last` is an alias for `[p]inat last`.
        """

        if kind in ("obs", "observation"):
            msgs = await ctx.history(limit=1000).flatten()
            inat_link_msg = INatLinkMsg(self.api)
            last = await inat_link_msg.get_last_obs_msg(msgs)
            if not last:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return

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
                            (await self.api.get_taxa(last.obs.taxon.taxon_id))[
                                "results"
                            ][0]
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
            msgs = await ctx.history(limit=1000).flatten()
            inat_link_msg = INatLinkMsg(self.api)
            last = await inat_link_msg.get_last_taxon_msg(msgs)
            if not last:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return

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
                            (await self.api.get_taxa(last.taxon.taxon_id))["results"][0]
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
        """Show summary for iNaturalist link.

        e.g.
        ```
        [p]inat link https://inaturalist.org/observations/#
           -> an embed summarizing the observation link
        ```
        When configured as recommended,
        `[p]link` is an alias for `[p]inat link`.
        """
        mat = re.search(PAT_OBS_LINK, query)
        if mat:
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            url = mat["url"]

            results = (await self.api.get_observations(obs_id, include_new_projects=1))[
                "results"
            ]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(ctx.guild, obs, url))
            if obs and obs.sound:
                await self.maybe_send_sound_url(ctx.channel, obs.sound)
        else:
            await ctx.send(embed=sorry())

    @inat.command()
    async def map(self, ctx, *, taxa_list):
        """Show range map for a list of one or more taxa.

        **Examples:**
        ```
        [p]inat map polar bear
        [p]inat map 24255,24267
        [p]inat map boreal chorus frog,western chorus frog
        ```
        See `[p]help inat taxon` for help specifying taxa.

        When configured as recommended,
        `[p]map` is an alias for `[p]inat map`.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxa_query.query_taxa(taxa_list)
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
        """Show observation summary for link or number.

        e.g.
        ```
        [p]inat obs #
           -> an embed summarizing the numbered observation
        [p]inat obs https://inaturalist.org/observations/#
           -> an embed summarizing the observation link (minus the preview,
              which Discord provides itself)
        ```
        When configured as recommended,
        `[p]obs` is an alias for `[p]inat obs`.
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
    async def related(self, ctx, *, taxa_list):
        """Relatedness of a list of taxa.

        **Examples:**
        ```
        [p]inat related 24255,24267
        [p]inat related boreal chorus frog,western chorus frog
        ```
        See `[p]help inat taxon` for help specifying taxa.

        When configured as recommended,
        `[p]related` is an alias for `[p]inat related`.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxa_query.query_taxa(taxa_list)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_related_embed(taxa))

    @inat.command()
    async def taxon(self, ctx, *, query):
        """Show taxon best matching the query.

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
        When configured as recommended, these aliases save typing:
        - `[p]t` or `[p]taxon` for `[p]inat taxon`
        and all rank keywords also work as command aliases, e.g.
        - `[p]family bear`
        - `[p]t family bear` (both equivalent to the 1st example)
        Abbreviated rank keywords are:
        - `sp` for `species`
        - `ssp` for `subspecies`
        - `gen` for `genus`
        - `var` for `variety`
        Multiple rank keywords may be given, e.g.
        - `[p]t ssp var form domestic duck` to search for domestic
        duck subspecies, variety, or form
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
    async def projectadd(self, ctx, project_id: int, emoji: Union[str, discord.Emoji]):
        """Add user project for guild (mods only)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)
        if project_id_str in user_projects:
            await ctx.send("iNat user project already known.")
            return

        user_projects[project_id_str] = str(emoji)
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project added.")

    @inat.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def projectdel(self, ctx, project_id: int):
        """Remove user project for guild (mods only)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)

        if project_id_str not in user_projects:
            await ctx.send("iNat user project not known.")
            return

        del user_projects[project_id_str]
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project removed.")

    @inat.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def useradd(self, ctx, discord_user: discord.User, inat_user):
        """Add user as an iNat user (mods only)."""
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
        response = await self.api.get_users(user_query)
        if response and response["results"]:
            user = User.from_dict(response["results"][0])
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
        """Remove user as an iNat user (mods only)."""
        config = self.config.user(discord_user)
        if not await config.inat_user_id():
            ctx.send("iNat user not known.")
            return
        await config.inat_user_id.clear()
        await ctx.send("iNat user removed.")

    @checks.admin_or_permissions(manage_roles=True)
    @inat.command()
    async def userlist(self, ctx):
        """List members with known iNat ids (mods only)."""
        if not ctx.guild:
            return

        # Avoid having to fully enumerate pages of discord/iNat user pairs
        # which would otherwise do expensive API calls if not in the cache
        # already just to get # of pages of member users:
        all_users = await self.config.all_users()
        user_projects = await self.config.guild(ctx.guild).user_projects()

        responses = [
            await self.api.get_projects(int(project_id)) for project_id in user_projects
        ]
        projects = [
            UserProject.from_dict(response["results"][0])
            for response in responses
            if response
        ]

        def emojis(user_id: int):
            emojis = [
                user_projects[str(project.project_id)]
                for project in projects
                if user_id in project.observed_by_ids()
            ]
            return " ".join(emojis)

        all_member_users = {
            key: value
            for (key, value) in all_users.items()
            if ctx.guild.get_member(key)
        }
        pages_num = ceil(len(all_member_users) / 10)

        all_names = [
            f"{duser.mention} is {iuser.profile_link()} {emojis(iuser.user_id)}"
            async for (duser, iuser) in self.get_user_pairs(all_member_users)
        ]

        pages = ["\n".join(filter(None, names)) for names in grouper(all_names, 10)]

        embeds = [
            make_embed(
                title=f"Discord iNat user list (page {index} of {pages_num})",
                description=page,
            )
            for index, page in enumerate(pages, start=1)
        ]
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @inat.command()
    async def usershow(self, ctx, who: ContextMemberConverter):
        """Show user if their iNat id is known."""
        if not ctx.guild:
            return

        config = self.config.user(who.member)
        inat_user_id = await config.inat_user_id()
        if not inat_user_id:
            await ctx.send("iNat user not known.")
            return
        user = None
        response = await self.api.get_users(inat_user_id)
        if response and response["results"] and len(response["results"]) == 1:
            user = User.from_dict(response["results"][0])
        if not user:
            await ctx.send("iNat user id lookup failed.")
            return
        await ctx.send(
            embed=make_embed(
                description=f"{who.member.mention} is {user.profile_link()}"
            )
        )

    async def get_user_pairs(self, users) -> AsyncIterator[Tuple[discord.User, User]]:
        """
        yields:
            discord.User, User

        Parameters
        ----------
        users: dict
            discord_id -> inat_id mapping
        """

        for discord_id in users:
            discord_user = self.bot.get_user(discord_id)
            user_json = await self.api.get_users(users[discord_id]["inat_user_id"])
            inat_user = None
            if user_json:
                results = user_json["results"]
                if results:
                    LOG.info(results[0])
                    inat_user = User.from_dict(results[0])

            yield (discord_user, inat_user)
