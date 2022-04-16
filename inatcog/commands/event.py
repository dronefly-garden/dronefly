"""Module for event command group."""
from typing import Union

import discord
from redbot.core import checks, commands
from pyinaturalist.models import Project

from ..checks import can_manage_users
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta

_DRONEFLY_INAT_ID = 3969847


class CommandsEvent(INatEmbeds, MixinMeta):
    """Mixin providing event command group."""

    @commands.group()
    @can_manage_users()
    async def event(self, ctx):
        """Commands to manage server events."""

    @event.command(name="join")
    async def event_join(self, ctx, abbrev: str, user: Union[discord.Member, discord.User]):
        """Join member to server event."""
        try:
            manager_inat_user = await self.user_table.get_user(ctx.author, anywhere=False)
            manager_inat_id = manager_inat_user.user_id
        except LookupError:
            await ctx.send("Your iNat login is not known here.")
            return
        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()
        event_project = event_projects.get(abbrev)
        event_project_id = int(event_project["project_id"]) if event_project else 0
        if not (event_project and event_project_id > 0):
            await ctx.send(f"Event project not known.")
            return
        response = await self.api.get_projects_by_id(ctx, event_project_id)
        if (not response):
            await ctx.send("iNat project not found.")
            return
        project = Project.from_json(response["results"][0])
        if project.prefers_user_trust:
            await ctx.send("Users must login on the web to join this project:")
            await (self.bot.get_command("project")(ctx, query=event_project_id))
            return
        try:
            inat_user = await self.user_table.get_user(user, anywhere=False)
        except LookupError as err:
            await ctx.send(str(err))
            return
        required_admins = [admin.id for admin in project.admins if admin.id in [manager_inat_id, _DRONEFLY_INAT_ID] and admin.role in ["admin", "manager"]]
        if (_DRONEFLY_INAT_ID not in required_admins):
            await ctx.send("I am not an admin or manager of this project.")
            return
        if (manager_inat_id not in required_admins):
            await ctx.send("You are not an admin or manager of this project.")
            return
        await ctx.send(repr(inat_user))
        await ctx.send(project.title)

    @event.command(name="list")
    @checks.bot_has_permissions(embed_links=True)
    async def event_list(self, ctx, abbrev: str):
        """List members of server event."""
        await self.user_list(ctx, abbrev)

    @event.command(name="leave")
    async def event_leave(self, ctx, abbrev: str, user):
        """Remove member from server event."""
