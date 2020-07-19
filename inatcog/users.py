"""Module to handle users."""
import re
from typing import AsyncIterator, Tuple
import discord
from .base_classes import WWW_URL_PAT, User

# Match user profile link from any partner site.
PAT_USER_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/(people|users)"
    r"/((?P<user_id>\d+)|(?P<login>[a-z][-_a-z0-9]{2,39}))"
    r")\b",
    re.I,
)


class INatUserTable:
    """Lookup helper for registered iNat users."""

    def __init__(self, cog):
        self.cog = cog

    async def get_user(self, member: discord.Member, refresh_cache=False):
        """Get user for Discord member."""
        inat_user_id = None
        user = None
        user_config = self.cog.config.user(member)

        if (
            member.guild.id in await user_config.known_in()
            or await user_config.known_all()
        ):
            inat_user_id = await user_config.inat_user_id()
        if not inat_user_id:
            raise LookupError("iNat user not known.")

        response = await self.cog.api.get_users(inat_user_id, refresh_cache)
        if response and response["results"] and len(response["results"]) == 1:
            user = User.from_dict(response["results"][0])
        if not user:
            raise LookupError("iNat user id lookup failed.")

        return user

    async def get_member_pairs(
        self, guild: discord.Guild, users
    ) -> AsyncIterator[Tuple[discord.Member, User]]:
        """
        yields:
            discord.Member, User

        Parameters
        ----------
        users: dict
            discord_id -> inat_id mapping
        """

        for discord_id in users:
            user_json = None
            inat_user = None

            discord_member = guild.get_member(discord_id)
            if (
                discord_member
                and guild.id in users[discord_id].get("known_in")
                or users[discord_id].get("known_all")
            ):
                inat_user_id = users[discord_id].get("inat_user_id")
                if inat_user_id:
                    user_json = await self.cog.api.get_users(inat_user_id)
            if user_json:
                results = user_json["results"]
                if results:
                    inat_user = User.from_dict(results[0])
            if discord_member and inat_user:
                yield (discord_member, inat_user)
