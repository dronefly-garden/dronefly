"""Module for event command group."""
import json
import logging
from typing import Union

import discord
from pyinaturalist.exceptions import AuthenticationError
from pyinaturalist.models import Project, User
from redbot.core import checks, commands
from requests.exceptions import HTTPError

from ..checks import can_manage_users
from ..client import iNatClient
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..projects import get_event_project
from ..utils import use_client

_ACTION = {
    "join": {"verb": "added", "prep": "to"},
    "leave": {"verb": "removed", "prep": "from"},
}
_DRONEFLY_INAT_ID = 3969847

logger = logging.getLogger(__name__)


class CommandsEvent(INatEmbeds, MixinMeta):
    """Mixin providing event command group."""

    @commands.group()
    @can_manage_users()
    async def event(self, ctx):
        """Commands to manage server events."""

    async def _event_action(
        self,
        ctx: commands.Context,
        client: iNatClient,
        action: str,
        abbrev: str,
        user: Union[discord.Member, discord.User],
    ):
        async def get_manager_inat_user(client: iNatClient):
            try:
                ctx = client.red_ctx
                manager_inat_user = await self.user_table.get_user(
                    ctx.author, anywhere=False
                )
            except LookupError as err:
                raise LookupError("Your iNat login is not known here.") from err
            return manager_inat_user

        async def check_manager(project: Project, manager_inat_user: User):
            # checks the validity of the bot user and the manager user:
            required_admins = [
                admin.id
                for admin in project.admins
                if admin.id in [manager_inat_user.id, _DRONEFLY_INAT_ID]
                and admin.role in ["admin", "manager"]
            ]
            if _DRONEFLY_INAT_ID not in required_admins:
                raise AuthenticationError(
                    "I am not an admin or manager of this project."
                )
            if manager_inat_user.id not in required_admins:
                raise AuthenticationError(
                    "You are not an admin or manager of this project."
                )

        async def get_inat_user(user: Union[discord.Member, discord.User]):
            return await self.user_table.get_user(user, anywhere=False)

        def match_user_in_response(inat_user: User, response: dict):
            if not response:
                raise ValueError()
            user_id = next(
                iter(
                    [
                        rule["operand_id"]
                        for rule in response.project_observation_rules
                        if rule["operand_type"] == "User"
                        and rule["operator"] == "observed_by_user?"
                        if rule["operand_id"] == inat_user.id
                    ]
                ),
                None,
            )
            return user_id

        async def get_command_response(
            inat_user: User, project: Project, update_response: dict
        ):
            valid_response = False
            (verb, prep) = (_ACTION[action]["verb"], _ACTION[action]["prep"])

            command_response = f"Something went wrong! User not {verb}."
            try:
                user_id = match_user_in_response(inat_user, update_response)
            except (ValueError, AttributeError):
                try:
                    pretty_response = json.dumps(
                        update_response, sort_keys=True, indent=4
                    )
                except TypeError:
                    pretty_response = repr(update_response)
                if pretty_response.len > 40:
                    pretty_response = "\n" + pretty_response
                logger.error(
                    "%sevent %s - invalid response: %s",
                    ctx.clean_prefix,
                    action,
                    pretty_response,
                )
            if action == "join":
                valid_response = user_id
            else:
                valid_response = not user_id
            if valid_response:
                command_response = (
                    f"Succesfully {verb} {inat_user.login} {prep} {project.title}."
                )

            return command_response

        msg = None
        try:
            manager_inat_user = await get_manager_inat_user(client)
            guild_config = self.config.guild(ctx.guild)
            project = await get_event_project(guild_config, abbrev, client)
            await check_manager(project, manager_inat_user)
            inat_user = await get_inat_user(user)

            if action == "join":
                update_response = await client.projects.add_users(
                    project.id, inat_user.id
                )
            else:
                update_response = await client.projects.delete_users(
                    project.id, inat_user.id
                )
            command_response = await get_command_response(
                inat_user, project, update_response
            )

            msg = command_response
        except (
            commands.CommandError,
            LookupError,
            AuthenticationError,
            HTTPError,
        ) as err:
            msg = str(err)
        return msg

    @use_client
    @event.command(name="join")
    async def event_join(
        self,
        ctx: commands.Context,
        abbrev: str,
        user: Union[discord.Member, discord.User],
    ):
        """Join member to server event."""
        async with ctx.typing():
            msg = await self._event_action(
                ctx, client=ctx.inat_client, action="join", abbrev=abbrev, user=user
            )
        await ctx.send(msg)

    @event.command(name="list")
    @checks.bot_has_permissions(embed_links=True)
    async def event_list(self, ctx: commands.Context, abbrev: str):
        """List members of server event."""
        await self.user_list(ctx, abbrev)

    @use_client
    @event.command(name="leave")
    async def event_leave(
        self,
        ctx: commands.Context,
        abbrev: str,
        user: Union[discord.Member, discord.User],
    ):
        """Remove member from server event."""
        async with ctx.typing():
            msg = await self._event_action(
                ctx, client=ctx.inat_client, action="leave", abbrev=abbrev, user=user
            )
        await ctx.send(msg)
