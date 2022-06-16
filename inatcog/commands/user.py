"""Module for user command group."""
import asyncio
import contextlib
from datetime import datetime
import re

import discord
from discord.ext.commands import MemberConverter as DiscordMemberConverter, CommandError
from dronefly.core.parsers.url import PAT_USER_LINK
from redbot.core import checks, commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.utils.predicates import MessagePredicate

from ..base_classes import User, WWW_BASE_URL
from ..checks import can_manage_users, known_inat_user
from ..common import DEQUOTE, grouper
from ..converters.base import (
    MemberConverter,
    QuotedContextMemberConverter,
    NaturalQueryConverter,
)
from ..embeds.common import apologize, make_embed
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..projects import UserProject
from ..utils import get_valid_user_config


class CommandsUser(INatEmbeds, MixinMeta):
    """Mixin providing user command group."""

    @commands.group(invoke_without_command=True, aliases=["who"])
    @checks.bot_has_permissions(embed_links=True)
    async def user(self, ctx, *, who: QuotedContextMemberConverter):
        """Show user if their iNat id is known.

        `Aliases: [p]who`

        First characters of the nickname or username are matched provided that user is cached by the server (e.g. if they were recently active).
        Otherwise, the nickname or username must be exact. If there is more than one username that exactly matches, append '#' plus the 4-digit discriminator to disambiguate.

        Examples:

        `[p]user Syn`
          matches `SyntheticBee#4951` if they spoke recently.
        `[p]user SyntheticBee`
          matches `SyntheticBee#4951` even if not recently active, assuming there is only one `SyntheticBee`.
        `[p]user SyntheticBee#4951`
          matches `SyntheticBee#4951` even if not recently active.

        If the server has defined any event_projects, then observations, species, & leaf taxa stats for each project are shown.
        Leaf taxa are explained here:
        https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        """  # noqa: E501
        if not (ctx.guild or (ctx.author == who.member)):
            return

        member = who.member
        try:
            user = await self.user_table.get_user(member, refresh_cache=True)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return

        async with ctx.typing():
            embed = await self.make_user_embed(ctx, member, user)
            await ctx.send(embed=embed)

    @user.command(name="add")
    @can_manage_users()
    async def user_add(self, ctx, discord_user: str, inat_user: str):
        """Add user in this server, or `me` to add yourself.

        `discord_user`
        - `me`, Discord user mention, ID, username, or nickname.
        - You can only add yourself in DM.
        - Username and nickname must be enclosed in double quotes if they contain blanks, so a mention or ID is easier.
        - Turn on `Developer Mode` in your Discord user settings to enable `Copy ID` when right-clicking/long-pressing a user's PFP.
          Depending on your platform, the setting is in `Behavior` or `Appearance > Advanced`.

        `inat_user`
        - iNat login id or iNat user profile URL
        """  # noqa: E501
        if discord_user == "me":
            if ctx.guild:
                await ctx.send(
                    f"`{ctx.clean_prefix}user add me` is only supported in DM with the bot.\n"
                    "To be added in this server, a mod must add you by your Discord username."
                )
                return
            discord_user = ctx.author
        else:
            if not ctx.guild:
                await ctx.send(
                    f"Add yourself with `{ctx.clean_prefix}user add me`.\n"
                    "Other users cannot be added in DM."
                )
                return
            try:
                ctx_member = await DiscordMemberConverter().convert(ctx, discord_user)
                discord_user = ctx_member
            except (BadArgument, CommandError):
                await ctx.send("Invalid or unknown Discord member.")
                return
        config = self.config.user(discord_user)

        inat_user_id = await config.inat_user_id()
        known_in = await config.known_in()
        guild_id = ctx.guild.id if ctx.guild else 0
        if inat_user_id and guild_id in known_in:
            await ctx.send("iNat user already added.")
            return

        mat_link = re.search(PAT_USER_LINK, inat_user)
        match = mat_link and (mat_link["user_id"] or mat_link["login"])
        if match:
            user_query = match
        else:
            user_query = inat_user

        user = None
        try:
            response = await self.api.get_users(user_query, refresh_cache=True)
        except LookupError:
            pass
        if response and response["results"]:
            user = User.from_dict(response["results"][0])
            mat_login = user_query.lower()
            mat_id = int(user_query) if user_query.isnumeric() else None
            if not ((user.login == mat_login) or (user.user_id == mat_id)):
                user = None

        if not user:
            await ctx.send("iNat user not found.")
            return

        # We don't support registering one Discord user on different servers
        # to different iNat user IDs! Corrective action is: bot owner removes
        # the user (will be removed from all guilds) before they can be added
        # under the new iNat ID.
        if inat_user_id:
            if inat_user_id != user.user_id:
                await ctx.send(
                    "New iNat user id for user! Registration under old id must be removed first."
                )
                return
        else:
            await config.inat_user_id.set(user.user_id)

        known_in.append(guild_id)
        await config.known_in.set(known_in)

        await ctx.send(
            f"{discord_user.display_name} is added as {user.display_name()}."
        )

    @staticmethod
    async def _user_clear(ctx, config):
        # Removal from last server removes all traces of the user:
        await config.inat_user_id.clear()
        await config.known_all.clear()
        await config.known_in.clear()
        await ctx.send("iNat user completely removed.")

    @user.command(name="remove")
    @can_manage_users()
    async def user_remove(self, ctx, discord_user: str):
        """Remove user in this server, or `me` to remove yourself.

        `discord_user`
        - `me`, Discord user mention, ID, username, or nickname.
        - You can only remove yourself in DM.
        - enclose in double-quotes if it contains blanks
        - for this reason, a mention is easier
        """

        if discord_user == "me":
            if ctx.guild:
                await ctx.send(
                    f"`{ctx.clean_prefix}user remove me` is only supported in DM with the bot.\n"
                    "To be removed in this server, a mod must remove you by your Discord username."
                )
                return
            discord_user = ctx.author
        else:
            if not ctx.guild:
                await ctx.send(
                    f"Remove yourself with `{ctx.clean_prefix}user remove me`.\n"
                    "Other users cannot be added or removed in DM."
                )
                return
            try:
                ctx_member = await DiscordMemberConverter().convert(ctx, discord_user)
                discord_user = ctx_member
            except (BadArgument, CommandError):
                await ctx.send("Invalid or unknown Discord member.")
                return
        config = self.config.user(discord_user)
        inat_user_id = await config.inat_user_id()
        known_in = await config.known_in()
        known_all = await config.known_all()
        # User can only be removed from servers where they were added unless
        # in a DM (special value 0).
        guild_id = ctx.guild.id if ctx.guild else 0
        if not inat_user_id or not (known_all or guild_id in known_in):
            await ctx.send("iNat user not known.")
            return

        # DMs are a special case:
        if not guild_id:
            query = await ctx.send(
                "This action is irrevocable and will remove all your settings"
                " including on any servers where you may have been added.\n\n"
                "If you really want to remove yourself completely, type:\n"
                "  `I understand`"
            )
            try:
                response = await self.bot.wait_for(
                    "message_without_command",
                    check=MessagePredicate.same_context(
                        channel=ctx.channel, user=ctx.author
                    ),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
                    return
            if response.content.lower() == "i understand":
                await self._user_clear(ctx, config)
            return

        if known_in:
            if guild_id in known_in:
                known_in.remove(guild_id)
                await config.known_in.set(known_in)
                if known_in:
                    await ctx.send("iNat user removed from this server.")
                else:
                    # Removal from last server removes all traces of the user:
                    # - note: if they added themself via DM, only they can
                    #   completely remove themself because "server" 0 will
                    #   be in their DM
                    await self._user_clear(ctx, config)
            elif known_all:
                await ctx.send(
                    "iNat user was added on another server or in DM and can only be removed there."
                )

    async def user_show_settings(self, ctx, config, setting: str = "all"):
        """iNat user settings."""
        if setting not in ["all", "known", "home", "lang"]:
            await ctx.send(f"Unknown setting: {setting}")
            return
        if setting in ["all", "known"]:
            known_all = await config.known_all()
            await ctx.send(f"known: {known_all}")
        if setting in ["all", "home"]:
            home_id = await config.home()
            if home_id:
                try:
                    home = await self.place_table.get_place(ctx.guild, home_id)
                    await ctx.send(f"home: {home.display_name} (<{home.url}>)")
                except LookupError:
                    await ctx.send(f"Non-existent place ({home_id})")
            else:
                await ctx.send("home: none")
        if setting in ["all", "lang"]:
            lang = await config.lang()
            await ctx.send(f"lang: {str(lang).lower()}")

    @user.command(name="remove_all")
    @checks.is_owner()
    async def user_remove_all(self, ctx, discord_user: discord.User):
        """Remove a user's settings for all servers."""
        config = self.config.user(discord_user)
        query = await ctx.send(
            "This action is irrevocable and will remove all of this user's"
            " settings on all servers. Only do this if the user requested it.\n"
            "Settings removal does not prevent the user from later being re-added"
            " or from accessing other bot functions. To do that, ban them with"
            f" `{ctx.clean_prefix}userlocalblocklist add`.\n\n"
            f"If you really want to remove {discord_user.mention} completely, type:\n"
            "  `I understand`"
        )
        try:
            response = await self.bot.wait_for(
                "message_without_command",
                check=MessagePredicate.same_context(
                    channel=ctx.channel, user=ctx.author
                ),
                timeout=30,
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(discord.HTTPException):
                await query.delete()
                return
        if response and response.content.lower() == "i understand":
            await self._user_clear(ctx, config)
        return

    @user.group(name="set", invoke_without_command=True)
    @known_inat_user()
    async def user_set(self, ctx, arg: str = None):
        """Show or set your iNat user settings.

        `[p]user set` shows all settings
        `[p]user set [name]` shows the named setting
        `[p]user set [name] [value]` set value of the named setting
        """
        if arg:
            await ctx.send(f"Unknown setting: {arg}")
            return
        try:
            config = await get_valid_user_config(self, ctx.author, anywhere=True)
        except LookupError as err:
            await ctx.send(err)
            return

        await self.user_show_settings(ctx, config)

    @user_set.command(name="home")
    @known_inat_user()
    async def user_set_home(self, ctx, *, value: str = None):
        """Show or set your home iNat place.

        `[p]user set home` show your home place
        `[p]user set home clear` clear your home place
        `[p]user set home [place]` set your home place

        Set also: `[p]help user set lang`.
        """
        try:
            config = await get_valid_user_config(self, ctx.author, anywhere=True)
        except LookupError as err:
            await ctx.send(err)
            return

        if value is not None:
            value = re.sub(DEQUOTE, r"\1", value)
            bot = self.bot.user.name
            if value.lower() in ["clear", "none", ""]:
                await config.home.clear()
                await ctx.send(f"{bot} no longer has a home place set for you.")
            else:
                try:
                    home = await self.place_table.get_place(ctx.guild, value)
                    await config.home.set(home.place_id)
                    await ctx.send(
                        f"{bot} will use {home.display_name} as your home place."
                    )
                except LookupError as err:
                    await ctx.send(err)
                    return

        await self.user_show_settings(ctx, config, "home")

    @user_set.command(name="known")
    @known_inat_user()
    async def user_set_known(self, ctx, value: bool = None):
        """Show or set if your iNat user settings are known on other servers.

        `[p]user set known` show known on other servers (default: not known)
        `[p]user set known true` set known on other servers
        """
        try:
            config = await get_valid_user_config(self, ctx.author, anywhere=True)
        except LookupError as err:
            await ctx.send(err)
            return

        if value is not None:
            await config.known_all.set(value)

            bot = self.bot.user.name
            if value:
                await ctx.send(
                    f"{bot} will know your iNat settings when you join a server it is on."
                )
            else:
                await ctx.send(
                    f"{bot} will not know your iNat settings when you join a server it is on"
                    " until you have been added there."
                )

        await self.user_show_settings(ctx, config, "known")

    @user_set.command(name="lang")
    @known_inat_user()
    async def user_set_lang(self, ctx, *, lang: str = None):
        """Show or set your preferred language for common names.

        `[p]user set lang` show your preferred language for common names
        `[p]user set lang clear` clear your preferred language for common names
        `[p]user set lang [lang]` set your preferred language for common names

        It is recommended to only use this setting if the language of your home place is not your preferred language for common names.

        When set, the common name shown in bot displays will be the first name with a locale exactly equal to the `lang` value. If no matching name is found, then the preferred common name for your home place is used by default.

        Due to limitations of the API, the `lang` argument must be one of the locale abbreviations supported by iNaturalist, e.g. `en` for English, `de` for German, etc. Unfortunately, this means quite a number of minor languages that iNaturalist has translations for, but are not associated with a locale are not represented.

        See: `[p]help user set home`.
        """  # noqa: E501
        try:
            config = await get_valid_user_config(self, ctx.author, anywhere=True)
        except LookupError as err:
            await ctx.send(err)
            return

        if lang is not None:
            _lang = re.sub(DEQUOTE, r"\1", lang).lower()
            bot = self.bot.user.name
            if _lang in ["clear", "none", ""]:
                await config.lang.clear()
                await ctx.send(f"{bot} no longer has a preferred language set for you.")
            else:
                try:
                    if not re.search(r"^[a-z-]+$", lang):
                        raise LookupError(
                            "Language must contain only letters or a dash, e.g. `en`, `de`, `zh`, `zh-CN`."
                        )
                    await config.lang.set(_lang)
                    await ctx.send(
                        f"{bot} will use `{_lang}` as your preferred language."
                    )
                except LookupError as err:
                    await ctx.send(err)
                    return

        await self.user_show_settings(ctx, config, "lang")

    async def _user_list_filter_role(self, ctx, abbrev, config, event_projects):
        filter_role = None
        filter_role_id = None
        if abbrev:
            if abbrev in ["active", "inactive"]:
                filter_role_id = await (
                    config.active_role()
                    if abbrev == "active"
                    else config.inactive_role()
                )
                if not filter_role_id:
                    raise BadArgument(
                        f"The {abbrev} role is undefined. To set it, use: `{ctx.clean_prefix}inat set {abbrev}`"
                    )
            elif abbrev in event_projects:
                filter_role_id = event_projects[abbrev]["role"]
            else:
                raise BadArgument(
                    "That event doesn't exist."
                    f" To create it, use: `{ctx.clean_prefix}inat set event`"
                )

        if filter_role_id:
            filter_role = next(
                (role for role in ctx.guild.roles if role.id == filter_role_id), None
            )
            if not filter_role:
                raise BadArgument(
                    f"The defined {abbrev} role doesn't exist: <@&{filter_role_id}>."
                    f" To update it, use: `{ctx.clean_prefix}inat set event`"
                )

        return filter_role

    async def _user_list_event_info(self, ctx, abbrev, event_projects):
        team_roles = []
        team_abbrevs = []
        event_project_ids = {}

        main_event_project_ids = {
            int(event_projects[prj_abbrev]["project_id"]): prj_abbrev
            for prj_abbrev in event_projects
            if event_projects[prj_abbrev]["main"]
            and int(event_projects[prj_abbrev]["project_id"])
        }

        if abbrev in event_projects:
            prj = event_projects[abbrev]
            prj_id = int(prj["project_id"])
            if prj_id:
                event_project_ids[prj_id] = abbrev
                teams = prj["teams"]
                team_abbrevs = teams.split(",") if teams else []
            for team_abbrev in team_abbrevs:
                if team_abbrev in event_projects:
                    prj = event_projects[team_abbrev]
                    prj_id = int(prj["project_id"])
                    event_project_ids[prj_id] = team_abbrev
                    team_role_id = prj["role"]
                    team_role = next(
                        (role for role in ctx.guild.roles if role.id == team_role_id),
                        None,
                    )
                    if team_role:
                        team_roles.append(team_role)
        else:
            event_project_ids = main_event_project_ids

        return (team_roles, team_abbrevs, event_project_ids, main_event_project_ids)

    async def _user_list_get_projects(
        self, ctx, event_project_ids, main_event_project_ids
    ):
        responses = [
            await self.api.get_projects(prj_id, refresh_cache=True)
            for prj_id in event_project_ids
        ]
        projects = {
            response["results"][0]["id"]: UserProject.from_dict(response["results"][0])
            for response in responses
            if response
        }

        # Only do the extra work to initially cache all the observers when
        # listing all users.
        # - TODO: review caching and make it a little less magic
        if main_event_project_ids and not self.user_cache_init.get(ctx.guild.id):
            await self.api.get_observers_from_projects(list(main_event_project_ids))
            self.user_cache_init[ctx.guild.id] = True
        return projects

    async def _user_list_match_members(
        self,
        ctx,
        abbrev,
        event_projects,
        filter_role,
    ):
        def abbrevs_for_user(user_id: int, event_project_ids, projects):
            return [
                event_project_ids[int(project_id)]
                for project_id in projects
                if user_id in projects[int(project_id)].observed_by_ids()
            ]

        def formatted_user(dmember, iuser, project_abbrevs):
            if dmember:
                if isinstance(dmember, discord.User) or isinstance(
                    dmember, discord.Member
                ):
                    user_is = f"{dmember.mention} is "
                else:
                    user_is = f"<@{dmember}> is "
            else:
                user_is = ":ghost: *(unknown user)* is "
            if isinstance(iuser, User):
                profile_link = iuser.profile_link()
            else:
                profile_link = f"[{iuser}](https://www.inaturalist.org/people/{iuser})"
            return f"{user_is}{profile_link}\n{' '.join(project_abbrevs)}"

        (
            team_roles,
            team_abbrevs,
            event_project_ids,
            main_event_project_ids,
        ) = await self._user_list_event_info(ctx, abbrev, event_projects)

        matching_names = []
        non_matching_names = []
        known_inat_user_ids_in_event = []
        all_user_ids = []
        all_users = await self.config.all_users()
        guild_id = ctx.guild.id
        known_user_ids_by_inat_id = {}
        for (discord_user_id, user_config) in all_users.items():
            inat_user_id = user_config.get("inat_user_id")
            if inat_user_id:
                if guild_id in user_config.get("known_in"):
                    known_user_ids_by_inat_id[inat_user_id] = discord_user_id
        projects = await self._user_list_get_projects(
            ctx, event_project_ids, main_event_project_ids
        )

        if abbrev in event_projects:
            prj = event_projects[abbrev]
            prj_id = int(prj["project_id"])
            if prj_id:
                all_user_ids = projects[prj_id].observed_by_ids()

        # Main pass:
        # - Candidate members are all users known to the bot.
        async for (dmember, iuser) in self.user_table.get_member_pairs(
            ctx.guild, all_users
        ):
            project_abbrevs = abbrevs_for_user(
                iuser.user_id, event_project_ids, projects
            )
            candidate = not abbrev or abbrev in project_abbrevs
            if filter_role and not candidate:
                candidate = filter_role in dmember.roles
            if not candidate:
                continue
            line = formatted_user(dmember, iuser, project_abbrevs)
            if filter_role:
                # Partition into those whose role matches the event they signed
                # up for vs. those who don't match, and therefore need attention
                # by a project admin.
                known_inat_user_ids_in_event.append(iuser.user_id)
                has_opposite_team_role = False
                for role in [filter_role, *team_roles]:
                    if role in dmember.roles:
                        line += f" {role.mention}"
                        if role in team_roles:
                            has_opposite_team_role = True
                role_strictly_matches_project = (
                    abbrev in project_abbrevs
                    and abbrev not in team_abbrevs
                    and filter_role in dmember.roles
                    and not has_opposite_team_role
                )
            else:
                known_inat_user_ids_in_event.append(iuser.user_id)
                role_strictly_matches_project = True
            if role_strictly_matches_project:
                matching_names.append(line)
            else:
                non_matching_names.append(line)

        # Second pass:
        # - Project members who are not (or are no longer) Discord server members:
        #   - i.e. user erroneously added when not a Discord server member, or
        #     they were added when they were a server member, but later left
        #   - Note: Discord user ID intentionally not shown even if known to the
        #     bot for a different server but not in this one
        for inat_user_id in all_user_ids:
            if inat_user_id not in known_inat_user_ids_in_event:
                known_discord_user_id = known_user_ids_by_inat_id.get(inat_user_id)
                inat_user = None
                if inat_user_id in self.api.users_cache:
                    try:
                        user_json = await self.api.get_users(inat_user_id)
                        results = user_json.get("results")
                        if results:
                            inat_user = User.from_dict(results[0])
                    except LookupError:
                        pass
                if known_discord_user_id:
                    discord_member = ctx.guild.get_member(known_discord_user_id)
                    # i.e. added in this server, but not a Discord server member anymore
                    if not discord_member:
                        discord_user = self.bot.get_user(known_discord_user_id)
                        if inat_user:
                            project_abbrevs = abbrevs_for_user(inat_user_id, event_project_ids, projects)
                            line = ":ghost: " + formatted_user(
                                discord_user or known_discord_user_id,
                                inat_user or inat_user_id,
                                project_abbrevs,
                            )
                            non_matching_names.append(line)
                else:
                    # User is in the event project observer rules and may or may
                    # not be known to the bot, but is not known in this server.
                    # In either case, we only list them as "unknown user".
                    line = formatted_user(
                        None, inat_user or inat_user_id, project_abbrevs
                    )
                    non_matching_names.append(line)

        return (matching_names, non_matching_names)

    @user.command(name="list")
    @can_manage_users()
    @checks.bot_has_permissions(embed_links=True, read_message_history=True)
    async def user_list(self, ctx, abbrev: str = None):
        """List members with known iNat ids on this server.

        The `abbrev` can be `active`, `inactive`, or an *event* abbreviation. The user list will only show known users with the associated role and/or in the event project. Discrepancies will be listed first.

        Note: If a user not known in the server holds an event role, or is added to an event project, those discrepancies won't be reported.

        See also: `[p]help inat set event`, `[p]help inat set active_role`, and `[p]help inat set inactive_role`.
        """  # noqa: E501
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()
        try:
            filter_role = await self._user_list_filter_role(
                ctx, abbrev, config, event_projects
            )
        except BadArgument as err:
            await ctx.send(
                embed=make_embed(
                    title=f"Invalid abbreviation: {abbrev}", description=str(err)
                )
            )
            return

        # If filter_role is given, resulting list of names will be partitioned
        # into matching and non matching names, where "non-matching" is any
        # discrepancy between the role(s) assigned and the project they're in,
        # or when a non-server-member is in the specified event project.
        (matching_names, non_matching_names) = await self._user_list_match_members(
            ctx, abbrev, event_projects, filter_role
        )
        # Placing non matching names first allows an event manager to easily
        # spot and correct mismatches.
        pages = [
            "\n".join(filter(None, names))
            for names in grouper([*non_matching_names, *matching_names], 10)
        ]

        if pages:
            pages_len = len(pages)
            if abbrev in ["active", "inactive"]:
                list_name = f"{abbrev.capitalize()} known server members"
            elif abbrev:
                list_name = f"Membership report for event: {abbrev}"
            else:
                list_name = f"Known server members"
            embeds = [
                make_embed(
                    title=f"{list_name} (page {index} of {pages_len})",
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(f"No known members matched.")

    @user.command(name="inatyear")
    @known_inat_user()
    @checks.bot_has_permissions(embed_links=True)
    async def user_inatyear(self, ctx, user: str = "me", year: int = None):
        """Display the URL for the user's iNat year graphs.

        Where `year` is a valid year on or after 1950, and `user` is a Discord user whose iNat profile is known to the bot.
        """  # noqa: E501

        this_year = datetime.today().year
        stats_year = this_year if year is None else year
        # 1950 experimentally determined (as of 2020-07-26) to be the floor year
        # as 1949 and earlier produces a 404 Error.
        if stats_year < 1950 or stats_year > this_year:
            await apologize(
                ctx,
                f"Sorry, iNat does not support stats for that year: `{stats_year}`",
            )
            return

        try:
            ctx_member = await MemberConverter.convert(ctx, user)
            member = ctx_member.member
            inat_user = await self.user_table.get_user(member)
        except (BadArgument, LookupError) as err:
            await ctx.send(err)
            return

        await ctx.send(
            f"https://www.inaturalist.org/stats/{stats_year}/{inat_user.login}"
        )

    @commands.command()
    async def iuser(self, ctx, *, login: str):
        """iNat user page for their login name.

        Examples:

        `[p]iuser kueda`
        """
        if not ctx.guild:
            return

        found = None
        try:
            response = await self.api.get_users(login, refresh_cache=True)
        except LookupError:
            pass
        if response and response["results"]:
            found = next(
                (
                    result
                    for result in response["results"]
                    if login in (str(result["id"]), result["login"])
                ),
                None,
            )
        if not found:
            await apologize(ctx, "Not found")
            return

        inat_user = User.from_dict(found)
        await ctx.send(inat_user.profile_url())

    @commands.command()
    @known_inat_user()
    @checks.bot_has_permissions(embed_links=True)
    async def me(self, ctx):  # pylint: disable=invalid-name
        """Show your iNat info & stats for this server."""
        member = await MemberConverter.convert(ctx, "me")
        await self.user(ctx, who=member)

    @commands.group(invoke_without_command=True)
    @known_inat_user()
    @checks.bot_has_permissions(embed_links=True)
    async def my(self, ctx, *, project: str):  # pylint: disable=invalid-name
        """Your rank in *project* (alias `[p]rank` *project* `me`).

        Use `[p]my` subcommands below to show other iNat info
        for your account.
        """
        await (self.bot.get_command("project stats")(ctx, project, user="me"))

    @my.command(name="inatyear")
    @known_inat_user()
    async def my_inatyear(self, ctx, year: int = None):
        """URL for your iNat year graphs.

        Where *year* is a valid year on or after 1950."""
        await self.user_inatyear(ctx, user="me", year=year)

    @my.command(name="obs")
    @known_inat_user()
    async def my_obs(self, ctx, *, query=""):
        """Search your observations (alias `[p]s obs my`)."""
        my_query = await NaturalQueryConverter.convert(ctx, f"{query} by me")
        await (self.bot.get_command("search obs")(ctx, query=my_query))

    @my.command(name="map")
    @known_inat_user()
    async def my_map(self, ctx, *, query=""):
        """Map observations by you (alias `[p]map obs my` *query*)."""
        my_query = await NaturalQueryConverter.convert(ctx, f"{query} by me")
        await (self.bot.get_command("map obs")(ctx, query=my_query))

    @my.command(name="idmap")
    @known_inat_user()
    async def my_idmap(self, ctx, *, query=""):
        """Map ided by you (alias `[p]map obs` *query* `id by me`)."""
        my_query = await NaturalQueryConverter.convert(ctx, f"{query} id by me")
        await (self.bot.get_command("map obs")(ctx, query=my_query))

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def rank(
        self, ctx, project: str, *, user: str
    ):  # pylint: disable=invalid-name
        """Rank in *project* (alias `[p]prj stats `*project* *user*)."""
        await (self.bot.get_command("project stats")(ctx, project, user=user))
