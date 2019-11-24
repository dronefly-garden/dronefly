"""Module to handle users."""
import re
from typing import NamedTuple
from .api import WWW_BASE_URL

PAT_USER_LINK = re.compile(
    r"\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/(people|users)/"
    + r"((?P<user_id>\d+)|(?P<login>[a-z][a-z0-9]{2,39})))\b",
    re.I,
)


class User(NamedTuple):
    """A user."""

    user_id: int
    name: str
    login: str

    def display_name(self):
        """Name to include in displays."""
        return f"{self.name} ({self.login})" if self.name else self.login

    def profile_url(self):
        """User profile url."""
        return f"{WWW_BASE_URL}/people/{self.login}" if self.login else ""

    def profile_link(self):
        """User profile link in markdown format."""
        return f"[{self.display_name()}]({self.profile_url()})"


def get_user_from_json(record):
    """Get User from JSON record.

    Parameters
    ----------
    record: dict
        A JSON record from /v1/users or other endpoints including user
        records.

    Returns
    -------
    User
        A User object from the JSON record.
    """
    user_id = record["id"]
    name = record["name"]
    login = record["login"]

    return User(user_id, name, login)
