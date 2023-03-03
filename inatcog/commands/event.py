"""Module for event command group."""
from typing import Union

import discord
from redbot.core import checks, commands
from pyinaturalist.models import Project
from pyinaturalist.exceptions import AuthenticationError
from requests.exceptions import HTTPError

from ..checks import can_manage_users
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta

_ACTION = {"join": "added", "leave": "removed"}
_ACTION_PREP = {"join": "to", "leave": "from"}
_DRONEFLY_INAT_ID = 3969847


class CommandsEvent(INatEmbeds, MixinMeta):
    """Mixin providing event command group."""

    @commands.group()
    @can_manage_users()
    async def event(self, ctx):
        """Commands to manage server events."""

    async def _event_action(self, ctx, action, abbrev, user):
        try:
            manager_inat_user = await self.user_table.get_user(
                ctx.author, anywhere=False
            )
            manager_inat_id = manager_inat_user.user_id
        except LookupError:
            await ctx.send("Your iNat login is not known here.")
            return
        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()
        event_project = event_projects.get(abbrev)
        event_project_id = int(event_project["project_id"]) if event_project else 0
        if not (event_project and event_project_id > 0):
            await ctx.send("Event project not known.")
            return
        response = await self.api.get_projects_by_id(ctx, event_project_id)
        if not response:
            await ctx.send("iNat project not found.")
            return
        project = Project.from_json(response["results"][0])
        try:
            inat_user = await self.user_table.get_user(user, anywhere=False)
        except LookupError as err:
            await ctx.send(str(err))
            return
        inat_user_id = inat_user.user_id
        required_admins = [
            admin.id
            for admin in project.admins
            if admin.id in [manager_inat_id, _DRONEFLY_INAT_ID]
            and admin.role in ["admin", "manager"]
        ]
        if _DRONEFLY_INAT_ID not in required_admins:
            await ctx.send("I am not an admin or manager of this project.")
            return
        if manager_inat_id not in required_admins:
            await ctx.send("You are not an admin or manager of this project.")
            return

        update_response = None
        async with self.client.set_ctx(ctx, typing=True) as client:
            try:
                update_response = await client.update_project_users(
                    ctx,
                    action=action,
                    project_id=project.id,
                    user_ids=inat_user_id,
                )
            except (AuthenticationError, HTTPError) as err:
                await ctx.send(str(err))
                return
        if update_response:
            user_id = next(
                iter(
                    [
                        rule["operand_id"]
                        for rule in response.project_observation_rules
                        if rule["operand_type"] == "User"
                        and rule["operator"] == "observed_by_user?"
                        if rule["operand_id"] == inat_user_id
                    ]
                ),
                None,
            )
            if user_id if action == "join" else not user_id:
                await ctx.send(
                    f"Succesfully {_ACTION[action]} {inat_user.login} "
                    f"{_ACTION_PREP[action]} {project.title}."
                )
                return
        await ctx.send(f"Something went wrong! User not {_ACTION[action]}.")

    @event.command(name="join")
    async def event_join(
        self, ctx, abbrev: str, user: Union[discord.Member, discord.User]
    ):
        """Join member to server event."""
        await self._event_action(ctx, "join", abbrev, user)

    @event.command(name="list")
    @checks.bot_has_permissions(embed_links=True)
    async def event_list(self, ctx, abbrev: str):
        """List members of server event."""
        await self.user_list(ctx, abbrev)

    @event.command(name="leave")
    async def event_leave(
        self, ctx, abbrev: str, user: Union[discord.Member, discord.User]
    ):
        """Remove member from server event."""
        await self._event_action(ctx, "leave", abbrev, user)
