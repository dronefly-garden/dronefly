"""Module to handle users."""
from typing import AsyncIterator, Tuple, Union

import discord

from .base_classes import User
from .utils import get_valid_user_config


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
            user = User.from_dict(response["results"][0])
        if not user:
            # The account is (probably) deleted, as I know of no temporary
            # failure of the API that wouldn't raise a different error.
            raise LookupError("iNat user id lookup failed.")

        return user

    async def get_member_pairs(
        self, guild: discord.Guild, users, anywhere: True
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
            if discord_member and (
                guild.id in users[discord_id].get("known_in")
                or (anywhere and users[discord_id].get("known_all"))
            ):
                inat_user_id = users[discord_id].get("inat_user_id")
                if inat_user_id:
                    if inat_user_id not in self.cog.api.users_cache:
                        uncached_known_user_ids.append(inat_user_id)
                    known_users.append([discord_member, inat_user_id])

        if uncached_known_user_ids:
            try:
                # cache all the remaining known users in one call
                await self.cog.api.get_observers_from_projects(
                    user_ids=uncached_known_user_ids
                )
            except LookupError:
                pass

        for (discord_member, inat_user_id) in known_users:
            try:
                user_json = await self.cog.api.get_users(inat_user_id)
            except LookupError:
                continue
            if user_json:
                results = user_json["results"]
                if results:
                    inat_user = User.from_dict(results[0])
            if inat_user:
                yield (discord_member, inat_user)
