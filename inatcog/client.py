from contextlib import asynccontextmanager
from functools import partial
from typing import List, Optional, Union

import discord
from dronefly.core.clients.inat import iNatClient as CoreiNatClient
from dronefly.core.commands import Context as DroneflyContext
from pyinaturalist import get_access_token
from redbot.core.commands import Context

from .utils import get_dronefly_ctx


class iNatClient(CoreiNatClient):
    @asynccontextmanager
    async def set_ctx(
        self,
        ctx: Context,
        author: Optional[Union[discord.Member, discord.User]],
        dronefly_ctx: Optional[DroneflyContext],
        typing: bool = False,
    ):
        """A client with both Red and Dronefly command contexts."""
        self.ctx = ctx
        self.dronefly_ctx = dronefly_ctx or get_dronefly_ctx(ctx, author or ctx.author)
        if typing:
            async with ctx.typing():
                yield self
        else:
            yield self

    async def update_project_users(
        self,
        action: str,
        project_id: int,
        user_ids: Union[int, List],
    ):
        """Add or remove users from a project's 'observed by' rules."""
        if action not in ("join", "leave"):
            raise ValueError(f"Unknown action: {action}")
        token = get_access_token()
        if action == "join":
            endpoint = self.projects.add_users
        else:
            endpoint = self.projects.delete_users
        return await self.loop.run_in_executor(
            None, partial(endpoint, project_id, user_ids, access_token=token)
        )
