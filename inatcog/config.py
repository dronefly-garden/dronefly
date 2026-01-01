import re
from typing import Optional, Union

from redbot.core.commands import BadArgument, Context
from discord import Member, User

from dronefly.core.models import BaseConfig

from .common import DEQUOTE
from .converters.base import MemberConverter
from .utils import get_cog, get_home_server, get_hub_server, get_valid_user_config

LOWEST_DISCORD_ID = 10**16


class ContextConfig(BaseConfig):
    """Config for the current context."""

    def __init__(
        self, ctx: Context, discord_user: Optional[Union[Member, User]] = None
    ):
        self.ctx = ctx
        self.cog = get_cog(ctx)
        self.discord_user = discord_user or self.ctx.author

    async def user_id(self, user: Union[Member, User, str, int]) -> Union[int, str]:
        """Get best matching iNat user id in this context.

        Match in this order:
          - if numeric, return its integer value (i.e. it could be an iNat id)
          - if it matches a known member with an iNat id, return the matching iNat id
          - if it's a string without blanks, return it (i.e. it could be an iNat login)
        """

        async def inat_user_id_for_discord_user(discord_user):
            user_id = None
            user_config = await get_valid_user_config(
                self.cog, discord_user, anywhere=False
            )
            if user_config:
                user_id = await user_config.inat_user_id()
            return user_id

        user_id = None

        if isinstance(user, Member) or isinstance(user, User):
            discord_user = user
        elif isinstance(user, int) or user.isnumeric():
            user_id = int(user)

        if discord_user or not user_id:
            try:
                if not discord_user:
                    # Maybe the name matches a known member
                    discord_user = (
                        await MemberConverter.convert(
                            self.ctx, re.sub(DEQUOTE, r"\1", user)
                        )
                    ).member
                user_id = await inat_user_id_for_discord_user(discord_user)
            except (BadArgument, LookupError):
                pass

        if not user_id and isinstance(user, str) and " " not in str(user):
            # Maybe it's a login id
            user_id = user

        if not user_id:
            raise LookupError("iNat member is not known.")

        return user_id

    async def user(self, user: Union[Member, User, str, int]) -> Union[int, str]:
        user_id = await self.user_id(user)
        # FIXME: update flake8 config to no longer require the noqa tags here
        return await anext(  # noqa: F821
            aiter(self.ctx.inat_client.users.from_ids(user_id)), None  # noqa: F821
        )

    async def place_id(
        self, abbrev: str, discord_user: Optional[Union[Member, User]] = None
    ):
        """Return place id for abbrev if the config defines one."""

        async def _get_place_id(guild, abbrev):
            guild_config = self.cog.config.guild(guild)
            places = await guild_config.places()
            return places.get(abbrev)

        _abbrev = abbrev.lower() if isinstance(abbrev, str) else None
        home_id = None
        place_id = None
        _discord_user = discord_user or self.discord_user
        _guild = self.ctx.guild or await get_home_server(
            self.cog, discord_user or self.ctx.author
        )

        if _abbrev == "home" and _discord_user:
            try:
                user_config = await get_valid_user_config(
                    self.cog, _discord_user, anywhere=True
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

    async def project_id(
        self, abbrev: str, discord_user: Optional[Union[Member, User]] = None
    ):
        """Return project id for abbrev if the config defines one."""

        async def _get_project_id(guild, abbrev):
            guild_config = self.cog.config.guild(guild)
            projects = await guild_config.projects()
            return projects.get(abbrev)

        project_id = None
        _abbrev = abbrev.lower() if isinstance(abbrev, str) else None
        _discord_user = discord_user or self.discord_user
        _guild = self.ctx.guild or await get_home_server(self.cog, _discord_user)

        if _guild and abbrev:
            project_id = await _get_project_id(_guild, _abbrev)
            if not project_id:
                hub_server = await get_hub_server(self.cog, _guild)
                if hub_server:
                    project_id = await _get_project_id(hub_server, _abbrev)
        return project_id
