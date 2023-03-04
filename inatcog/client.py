from contextlib import asynccontextmanager
from functools import partial
from typing import Optional, Union

import discord
from dronefly.core.clients.inat import iNatClient as CoreiNatClient
from dronefly.core.commands import Context as DroneflyContext
from pyinaturalist import get_access_token
from pyinaturalist.models import Project
from redbot.core import commands

from .base_classes import User
from .utils import get_dronefly_ctx


class iNatClient(CoreiNatClient):
    @asynccontextmanager
    async def set_ctx(
        self,
        red_ctx: commands.Context,
        author: Optional[Union[discord.Member, discord.User]] = None,
        dronefly_ctx: Optional[DroneflyContext] = None,
        typing: bool = False,
    ):
        """A client with both Red and Dronefly command contexts."""
        self.red_ctx = red_ctx
        self.ctx = dronefly_ctx or await get_dronefly_ctx(
            self.red_ctx, author or red_ctx.author
        )
        if typing:
            async with red_ctx.typing():
                yield self
        else:
            yield self

    async def update_event_project_user(
        self,
        action: str,
        project: Project,
        user: User,
    ):
        """Add or remove users from a project's 'observed by' rules."""
        if action not in ("join", "leave"):
            raise ValueError(f"Unknown action: {action}")
        if action == "join":
            endpoint = self.projects.add_users
        else:
            endpoint = self.projects.delete_users
        return await self.loop.run_in_executor(
            None, partial(endpoint, project.id, user.user_id, auth=True)
        )
