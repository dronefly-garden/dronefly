from asyncio import AbstractEventLoop
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, Dict, Optional, Union

import discord
from dronefly.core.clients.inat import iNatClient as CoreiNatClient
from dronefly.core.commands import Context as DroneflyContext
from pyinaturalist import controllers as pyic
from pyinaturalist.session import ClientSession
from redbot.core import commands
from requests import Session

from .utils import get_dronefly_ctx


class ProjectController(pyic.ProjectController):
    async def async_add_users(self, *args, **kwargs):
        return await self.client.loop.run_in_executor(
            None, partial(self.add_users, *args, **kwargs)
        )

    async def async_delete_users(self, *args, **kwargs):
        return await self.client.loop.run_in_executor(
            None, partial(self.delete_users, *args, **kwargs)
        )

    async def async_from_ids(self, *args, **kwargs):
        return await self.client.loop.run_in_executor(
            None, partial(self.from_ids, *args, **kwargs)
        )


class iNatClient(CoreiNatClient):
    def __init__(
        self,
        creds: Optional[Dict[str, str]] = None,
        default_params: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        loop: Optional[AbstractEventLoop] = None,
        session: Optional[Session] = None,
        **kwargs,
    ):
        """A Dronefly client with async wrappers for each controller/action we use."""
        self.creds = creds or {}
        self.default_params = default_params or {}
        self.dry_run = dry_run
        self.loop = loop
        self.session = session or ClientSession(**kwargs)

        self._access_token = None
        self._token_expires = None

        self.controlled_terms = pyic.ControlledTermController(
            self
        )
        self.observations = pyic.ObservationController(self)
        self.places = pyic.PlaceController(self)
        self.projects = ProjectController(self)
        self.taxa = pyic.TaxonController(self)
        self.users = pyic.UserController(self)

    @asynccontextmanager
    async def set_ctx_from_user(
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
