"""Module to handle users."""
import re
from typing import AsyncIterator, Tuple, Union

import discord
from pyinaturalist.models import User
from redbot.core.commands import BadArgument, Context

from .common import DEQUOTE
from .converters.base import MemberConverter
from .utils import get_cog, get_valid_user_config


class INatUserTable:
    """Lookup helper for registered iNat users."""

    def __init__(self, cog):
        self.cog = cog

    async def get_user(
        self,
        member: Union[discord.Member, discord.User],
        refresh_cache=False,
        anywhere=True,
    ):
        """Get user for Discord member."""
        inat_user_id = None
        user = None
        # Note: may raise LookupError if user is not known in the specified scope:
        user_config = await get_valid_user_config(self.cog, member, anywhere=anywhere)
        inat_user_id = await user_config.inat_user_id()

        response = await self.cog.api.get_users(inat_user_id, refresh_cache)
        if response and response["results"] and len(response["results"]) == 1:
            user = User.from_json(response["results"][0])
        if not user:
            # The account is (probably) deleted, as I know of no temporary
            # failure of the API that wouldn't raise a different error.
            raise LookupError("iNat user id lookup failed.")

        return user

    async def get_member_pairs(
        self,
        guild: discord.Guild,
        users,
        anywhere: True,
        mock_users_without_observations=True,
    ) -> AsyncIterator[Tuple[discord.Member, User]]:
        """
        yields:
            discord.Member, User

        Parameters
        ----------
        users: dict
            discord_id -> inat_id mapping
        """

        known_users = []
        uncached_known_user_ids = []
        for discord_id in users:
            user_json = None
            inat_user = None

            discord_member = guild.get_member(discord_id)
            if guild.id in users[discord_id].get("known_in") or (
                anywhere and users[discord_id].get("known_all")
            ):
                inat_user_id = users[discord_id].get("inat_user_id")
                if inat_user_id:
                    if (
                        inat_user_id not in self.cog.api.users_cache
                        and inat_user_id not in uncached_known_user_ids
                    ):
                        uncached_known_user_ids.append(inat_user_id)
                    known_users.append([discord_member or discord_id, inat_user_id])

        if uncached_known_user_ids:
            try:
                # cache all the remaining known users in one call
                await self.cog.api.bulk_load_users_from_observers(
                    user_ids=uncached_known_user_ids
                )
            except LookupError:
                pass

        for (discord_member, inat_user_id) in known_users:
            if (
                inat_user_id not in self.cog.api.users_cache
                and mock_users_without_observations
            ):
                # Optimize listing these users:
                # - yield the registered user's user_id, but don't look up the
                #   user as this can be quite costly when iterating over all of
                #   them
                inat_user = User(id=inat_user_id, login=str(inat_user_id))
            else:
                try:
                    user_json = await self.cog.api.get_users(inat_user_id)
                except LookupError:
                    continue
                if user_json:
                    results = user_json["results"]
                    if results:
                        inat_user = User.from_json(results[0])
            if inat_user:
                yield (discord_member, inat_user)


async def get_inat_user(ctx: Context, user: str):
    """Get iNat user from iNat user_id, known member, or iNat login, in that order."""

    async def _get_user(cog, user: str, **kwargs):
        try:
            response = await cog.api.get_users(user, **kwargs)
            if response and response["results"] and len(response["results"]) == 1:
                return User.from_json(response["results"][0])
        except (BadArgument, LookupError):
            pass
        return None

    cog = get_cog(ctx)
    _user = None
    if user.isnumeric():
        _user = await _get_user(cog, user)
    if not _user:
        try:
            who = await MemberConverter.convert(ctx, re.sub(DEQUOTE, r"\1", user))
            _user = await cog.user_table.get_user(who.member)
        except (BadArgument, LookupError):
            pass

    if isinstance(user, str) and not _user and " " not in str(user):
        _user = await _get_user(cog, user, by_login_id=True)

    if not _user:
        raise LookupError("iNat member is not known or iNat login is not valid.")

    return _user
