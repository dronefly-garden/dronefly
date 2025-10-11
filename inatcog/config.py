from typing import Optional, Union

from redbot.core.commands import Context
from discord import Member, User

from dronefly.core.models import BaseConfig

from .utils import get_cog, get_home_server, get_hub_server, get_valid_user_config


class ContextualConfig(BaseConfig):
    """Config for the current context and member or user."""

    def __init__(
        self, ctx: Context, member_or_user: Optional[Union[Member, User]] = None
    ):
        self.ctx = ctx
        self.cog = get_cog(ctx)
        self.member_or_user = member_or_user

    async def user(self, name_or_id: Union[str, int]):
        """TODO"""

    async def place(self, abbrev: str):
        async def _get_place_id(guild, abbrev):
            guild_config = self.cog.config.guild(guild)
            places = await guild_config.places()
            return places[abbrev]

        _abbrev = abbrev.lower() if isinstance(abbrev, str) else None
        home_id = None
        place_id = None
        _guild = self.ctx.guild or await get_home_server(self.cog, self.member_or_user)

        if _abbrev == "home" and self.user:
            try:
                user_config = await get_valid_user_config(
                    self.cog, self.member_or_user, anywhere=True
                )
                home_id = await user_config.home()
            except LookupError:
                pass
            if not home_id and _guild:
                guild_config = self.cog.config.guild(_guild)
                home_id = await guild_config.home()
            if not home_id:
                home_id = await self.cog.config.home()

        if not home_id and _guild and _abbrev:
            place_id = await _get_place_id(_guild, abbrev)
            if not place_id:
                hub_server = await get_hub_server(self.cog, _guild)
                if hub_server:
                    place_id = await _get_place_id(hub_server, abbrev)

        if not place_id:
            if home_id or isinstance(_abbrev, int) or _abbrev.isnumeric():
                place_id = int(home_id or _abbrev)
        return place_id

    async def project(self, abbrev: str):
        async def _get_project_id(guild, abbrev):
            guild_config = self.cog.config.guild(guild)
            projects = await guild_config.projects()
            return projects.get(abbrev)

        project_id = None
        _abbrev = abbrev.lower() if isinstance(abbrev, str) else None
        _guild = self.ctx.guild or await get_home_server(self.cog, self.member_or_user)

        if _guild and abbrev:
            project_id = await _get_project_id(_guild, _abbrev)
            if not project_id:
                hub_server = await get_hub_server(self.cog, _guild)
                if hub_server:
                    project_id = await _get_project_id(hub_server, _abbrev)
        return project_id
