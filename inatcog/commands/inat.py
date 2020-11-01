"""Module for inat command group."""

import asyncio
from typing import Optional, Union
import discord
from redbot.core import checks, commands

from inatcog.base_classes import WWW_BASE_URL
from inatcog.converters import InheritableBoolConverter
from inatcog.embeds import make_embed
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta


class CommandsInat(INatEmbeds, MixinMeta):
    """Mixin providing inat command group."""

    @commands.group()
    async def inat(self, ctx):
        """Show/change iNat settings.

        See `[p]help iNat` for all `inatcog` help topics."""

    @inat.group(name="set")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_set(self, ctx):
        """Change iNat settings (mods)."""

    @inat_set.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_bot_prefixes(self, ctx, *prefixes):
        """Set server ignored bot prefixes (mods).

        All messages starting with one of these *prefixes* will be ignored by
        [botname].

        - If *prefixes* is empty, current setting is shown.
        - You particularly need to set *bot_prefixes* if your server has more
          than one bot with `inatcog` loaded, otherwise it's unlikely you
          need to set this.
        - Set this to all prefixes of other bots separated by spaces to
          ensure [botname] ignores commands sent to them, especially when
          *autoobs* is enabled.
        - You don't need to include any prefixes of [botname] itself.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if prefixes:
            await config.bot_prefixes.set(prefixes)
        else:
            prefixes = await config.bot_prefixes()

        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @inat_set.command(name="inactive_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_inactive_role(self, ctx, inactive_role: Optional[discord.Role]):
        """Set server Inactive role."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if inactive_role:
            msg = inactive_role.mention
            await config.inactive_role.set(inactive_role.id)
        else:
            find = await config.inactive_role()
            if find:
                inactive_role = next(
                    (role for role in ctx.guild.roles if role.id == find), None
                )
                msg = (
                    inactive_role.mention
                    if inactive_role
                    else f"missing role: <@&{find}>"
                )
            else:
                msg = "not set"
        await ctx.send(embed=make_embed(description=f"Inactive role: {msg}"))

    @inat_set.command(name="active_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_active_role(self, ctx, active_role: Optional[discord.Role]):
        """Set server Active role."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if active_role:
            msg = active_role.mention
            await config.active_role.set(active_role.id)
        else:
            find = await config.active_role()
            if find:
                active_role = next(
                    (role for role in ctx.guild.roles if role.id == find), None
                )
                msg = (
                    active_role.mention if active_role else f"missing role: <@&{find}>"
                )
            else:
                msg = "not set"
        await ctx.send(embed=make_embed(description=f"Active role: {msg}"))

    @inat.group(name="clear")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_clear(self, ctx):
        """Clear iNat settings (mods)."""

    @inat_clear.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def clear_bot_prefixes(self, ctx):
        """Clear server ignored bot prefixes (mods)."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.bot_prefixes.clear()

        await ctx.send("Server ignored bot prefixes cleared.")

    @inat_set.group(invoke_without_command=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs(self, ctx, state: InheritableBoolConverter):
        """Set channel auto-observation mode (mods).

        To set the mode for the channel:
        ```
        [p]inat set autoobs on
        [p]inat set autoobs off
        [p]inat set autoobs inherit
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

    @autoobs.command(name="server")
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs_server(self, ctx, state: bool):
        """Set server auto-observation mode (mods).

        ```
        [p]inat set autoobs server on
        [p]inat set autoobs server off
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

    @commands.command()
    async def dot_taxon(self, ctx):
        """How to use the `.taxon.` lookup feature.

        • Surround taxon to lookup with `.`
        • Separate from other text with blanks
        • Only one lookup will be performed per message
        • Taxonomy tree is omitted for `by` or `from` lookups
        • Show the setting with `[p]inat show dot_taxon`
        • Set with `[p]inat set dot_taxon` (mods)

        **Examples:**
        ```
        It's .rwbl. for sure.
        ```
        • behaves like  `[p]taxon rwbl`
        ```
        Check out these .lace bugs by me. , please.
        ```
        • behaves like `[p]obs lace bugs by me`
        """
        await ctx.send_help()

    @inat_set.group(invoke_without_command=True, name="dot_taxon")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_dot_taxon(self, ctx, state: InheritableBoolConverter):
        """Set channel .taxon. lookup (mods).

        To set .taxon. lookup for the channel:
        ```
        [p]inat set dot_taxon on
        [p]inat set dot_taxon off
        [p]inat set dot_taxon inherit
        ```
        When `inherit` is specified, channel mode inherits from the server
        setting.

        See `[p]help dot_taxon` for usage of the feature.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.channel(ctx.channel)
        await config.dot_taxon.set(state)

        if state is None:
            server_state = await self.config.guild(ctx.guild).dot_taxon()
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if state else "off"
        await ctx.send(f"Channel .taxon. lookup is {value}.")
        return

    @set_dot_taxon.command(name="server")
    @checks.admin_or_permissions(manage_messages=True)
    async def dot_taxon_server(self, ctx, state: bool):
        """Set server .taxon. lookup (mods).

        ```
        [p]inat set dot_taxon server on
        [p]inat set dot_taxon server off
        ```

        See `[p]help dot_taxon` for usage of the feature.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.dot_taxon.set(state)
        await ctx.send(f"Server .taxon. lookup is {'on' if state else 'off'}.")
        return

    @inat.group(name="show")
    async def inat_show(self, ctx):
        """Show iNat settings."""

    @inat_show.command(name="autoobs")
    async def show_autoobs(self, ctx):
        """Show channel & server auto-observation mode."""
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

    @inat_show.command(name="dot_taxon")
    async def show_dot_taxon(self, ctx):
        """Show channel & server .taxon. lookup.

        See `[p]help dot_taxon` for how to use the feature."""
        if ctx.author.bot or ctx.guild is None:
            return

        server_config = self.config.guild(ctx.guild)
        server_state = await server_config.dot_taxon()
        await ctx.send(f"Server .taxon. lookup is {'on' if server_state else 'off'}.")
        channel_config = self.config.channel(ctx.channel)
        channel_state = await channel_config.dot_taxon()
        if channel_state is None:
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if channel_state else "off"
        await ctx.send(f"Channel .taxon. lookup is {value}.")
        return

    @inat_show.command(name="bot_prefixes")
    async def show_bot_prefixes(self, ctx):
        """Show server ignored bot prefixes."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        prefixes = await config.bot_prefixes()
        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @inat_set.command(name="home")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_home(self, ctx, home: str):
        """Set server default home place (mods)."""
        config = self.config.guild(ctx.guild)
        try:
            place = await self.place_table.get_place(ctx.guild, home, ctx.author)
        except LookupError as err:
            await ctx.send(err)
            return
        await config.home.set(place.place_id)
        await ctx.send(f"iNat server default home set:\n{place.url}")

    @inat_show.command(name="home")
    async def show_home(self, ctx):
        """Show server default home place."""
        config = self.config.guild(ctx.guild)
        home = await config.home()
        await ctx.send("iNat server default home:")
        try:
            place = await self.place_table.get_place(ctx.guild, int(home), ctx.author)
            await ctx.send(place.url)
        except LookupError as err:
            await ctx.send(err)

    @inat_set.command(name="user_project")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_user_project(
        self, ctx, project_id: int, emoji: Union[str, discord.Emoji]
    ):
        """Add a server user project (mods)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)
        if project_id_str in user_projects:
            await ctx.send("iNat user project already known.")
            return

        user_projects[project_id_str] = str(emoji)
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project added.")

    @inat_clear.command(name="user_project")
    @checks.admin_or_permissions(manage_roles=True)
    async def clear_user_project(self, ctx, project_id: int):
        """Clear a server user project (mods)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)

        if project_id_str not in user_projects:
            await ctx.send("iNat user project not known.")
            return

        del user_projects[project_id_str]
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project removed.")

    @inat_show.command(name="user_projects")
    async def show_user_projects(self, ctx):
        """Show server user projects."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        for project_id in user_projects:
            await ctx.send(
                f"{user_projects[project_id]} {WWW_BASE_URL}/projects/{project_id}"
            )
            await asyncio.sleep(1)
