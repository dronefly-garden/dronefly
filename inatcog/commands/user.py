"""Module for user command group."""
from datetime import datetime
import re

import discord
from redbot.core import checks, commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..base_classes import User
from ..checks import known_inat_user
from ..common import DEQUOTE, grouper
from ..converters.base import (
    MemberConverter,
    QuotedContextMemberConverter,
    NaturalQueryConverter,
)
from ..core.parsers.url import PAT_USER_LINK
from ..embeds.common import apologize, make_embed
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..projects import UserProject


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

        If the server has defined any user_projects, then observations, species, & leaf taxa stats for each project are shown.
        Leaf taxa are explained here:
        https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        """  # noqa: E501
        if not ctx.guild:
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
    @checks.admin_or_permissions(manage_roles=True)
    async def user_add(self, ctx, discord_user: discord.User, inat_user):
        """Add user as an iNat user (mods only).

        `discord_user`
        - Discord user mention, ID, username, or nickname.
        - Username and nickname must be enclosed in double quotes if they contain blanks, so a mention or ID is easier.
        - Turn on `Developer Mode` in your Discord user settings to enable `Copy ID` when right-clicking/long-pressing a user's PFP.
          Depending on your platform, the setting is in `Behavior` or `Appearance > Advanced`.

        `inat_user`
        - iNat login id or iNat user profile URL
        """  # noqa: E501
        config = self.config.user(discord_user)

        inat_user_id = await config.inat_user_id()
        known_all = await config.known_all()
        known_in = await config.known_in()
        if inat_user_id and known_all or ctx.guild.id in known_in:
            await ctx.send("iNat user already known.")
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

        known_in.append(ctx.guild.id)
        await config.known_in.set(known_in)

        await ctx.send(
            f"{discord_user.display_name} is added as {user.display_name()}."
        )

    @user.command(name="remove")
    @checks.admin_or_permissions(manage_roles=True)
    async def user_remove(self, ctx, discord_user: discord.User):
        """Remove user as an iNat user (mods only).

        `discord_user`
        - Discord username or nickname
        - enclose in double-quotes if it contains blanks
        - for this reason, a mention is easier
        """
        config = self.config.user(discord_user)
        inat_user_id = await config.inat_user_id()
        known_in = await config.known_in()
        known_all = await config.known_all()
        if not inat_user_id or not (known_all or ctx.guild.id in known_in):
            await ctx.send("iNat user not known.")
            return
        # User can only be removed from servers where they were added:
        if ctx.guild.id in known_in:
            known_in.remove(ctx.guild.id)
            await config.known_in.set(known_in)
            if known_in:
                await ctx.send("iNat user removed from this server.")
            else:
                # Removal from last server removes all traces of the user:
                await config.inat_user_id.clear()
                await config.known_all.clear()
                await config.known_in.clear()
                await ctx.send("iNat user removed.")
        elif known_in and known_all:
            await ctx.send(
                "iNat user was added on another server and can only be removed there."
            )

    async def get_valid_user_config(self, ctx):
        """iNat user config known in this guild."""
        user_config = self.config.user(ctx.author)
        inat_user_id = await user_config.inat_user_id()
        known_in = await user_config.known_in()
        known_all = await user_config.known_all()
        if not (inat_user_id and known_all or ctx.guild.id in known_in):
            raise LookupError("Ask a moderator to add your iNat profile link.")
        return user_config

    async def user_show_settings(self, ctx, config, setting: str = "all"):
        """iNat user settings."""
        if setting not in ["all", "known", "home"]:
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
            config = await self.get_valid_user_config(ctx)
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
        """
        try:
            config = await self.get_valid_user_config(ctx)
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
            config = await self.get_valid_user_config(ctx)
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

    @user.command(name="list")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def user_list(self, ctx, with_role: str = None):
        """List members with known iNat ids (mods only)."""
        if not ctx.guild:
            return

        # Avoid having to fully enumerate pages of discord/iNat user pairs
        # which would otherwise do expensive API calls if not in the cache
        # already just to get # of pages of member users:
        all_users = await self.config.all_users()
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        filter_role = None
        filter_role_id = None
        if with_role:
            if with_role == "active":
                filter_role_id = await config.active_role()
            elif with_role == "inactive":
                filter_role_id = await config.inactive_role()
            else:
                await ctx.send_help()
                return
        if with_role and not filter_role_id:
            await ctx.send(embed=make_embed(description=f"No {with_role} role set."))
            return

        if filter_role_id:
            filter_role = next(
                (role for role in ctx.guild.roles if role.id == filter_role_id), None
            )
            if not filter_role:
                await ctx.send(
                    embed=make_embed(
                        description=f"The {with_role} role is not a guild role: "
                        f"<@&{filter_role_id}>."
                    )
                )
                return

        responses = [
            await self.api.get_projects(int(project_id)) for project_id in user_projects
        ]
        projects = [
            UserProject.from_dict(response["results"][0])
            for response in responses
            if response
        ]

        if not self.user_cache_init.get(ctx.guild.id):
            await self.api.get_observers_from_projects(user_projects.keys())
            self.user_cache_init[ctx.guild.id] = True

        def emojis(user_id: int):
            emojis = [
                user_projects[str(project.project_id)]
                for project in projects
                if user_id in project.observed_by_ids()
            ]
            return " ".join(emojis)

        # TODO: Support lazy loading of pages of users (issues noted in comments below).
        all_names = [
            f"{dmember.mention} is {iuser.profile_link()} {emojis(iuser.user_id)}"
            async for (dmember, iuser) in self.user_table.get_member_pairs(
                ctx.guild, all_users
            )
            if not filter_role or filter_role in dmember.roles
        ]

        pages = ["\n".join(filter(None, names)) for names in grouper(all_names, 10)]

        if pages:
            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            embeds = [
                make_embed(
                    title=f"Discord iNat user list (page {index} of {pages_len})",
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            # menu() does not support lazy load of embeds iterator.
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(
                f"No iNat login ids are known. Add them with `{ctx.clean_prefix}user add`."
            )

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
