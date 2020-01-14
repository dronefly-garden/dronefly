"""Module to handle users."""
import re
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin
import discord
from .api import WWW_BASE_URL

PAT_USER_LINK = re.compile(
    r"\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/(people|users)/"
    + r"((?P<user_id>\d+)|(?P<login>[a-z][-_a-z0-9]{2,39})))\b",
    re.I,
)


@dataclass
class User(DataClassJsonMixin):
    """A user."""

    user_id: int = field(metadata=config(field_name="id"))
    name: str
    login: str
    observations_count: int
    identifications_count: int

    def display_name(self):
        """Name to include in displays."""
        return f"{self.name} ({self.login})" if self.name else self.login

    def profile_url(self):
        """User profile url."""
        return f"{WWW_BASE_URL}/people/{self.login}" if self.login else ""

    def profile_link(self):
        """User profile link in markdown format."""
        return f"[{self.display_name()}]({self.profile_url()})"


class INatUserTable:
    """Lookup helper for registered iNat users."""

    def __init__(self, bot):
        self.bot = bot

    async def get_user(self, member: discord.Member, refresh_cache=False):
        """Get user for Discord member."""
        user = None
        user_config = self.bot.config.user(member)

        inat_user_id = await user_config.inat_user_id()
        if not inat_user_id:
            raise LookupError("iNat user not known.")

        response = await self.bot.api.get_users(inat_user_id, refresh_cache)
        if response and response["results"] and len(response["results"]) == 1:
            user = User.from_dict(response["results"][0])
        if not user:
            raise LookupError("iNat user id lookup failed.")

        return user
