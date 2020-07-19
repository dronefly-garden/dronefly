"""Module to handle users."""
import re
from typing import Union
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin
from .api_classes import WWW_BASE_URL, WWW_URL_PAT
from .converters import QuotedContextMemberConverter

# Match place link from any partner site.
PAT_PLACE_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/places"
    r"/((?P<place_id>\d+)|(?P<place_slug>[a-z][-_a-z0-9]{2,39}))"
    r")\b",
    re.I,
)

RESERVED_PLACES = ["home", "none", "clear", "all", "any"]


@dataclass
class Place(DataClassJsonMixin):
    """An iNat place."""

    display_name: str
    place_id: int = field(metadata=config(field_name="id"))
    url: str = field(init=False)

    def __post_init__(self):
        """URL for place."""
        self.url = f"{WWW_BASE_URL}/places/{self.place_id}"


class INatPlaceTable:
    """Lookup helper for places."""

    def __init__(self, cog):
        self.cog = cog

    async def get_place(
        self, guild, query: Union[int, str], user: QuotedContextMemberConverter = None
    ):
        """Get place by guild abbr or via id#/keyword lookup in API."""
        place = None
        response = None
        home_id = None

        if isinstance(query, str):
            abbrev = query.lower()
            if abbrev == "home" and user:
                user_config = self.cog.config.user(user)
                home_id = await user_config.home()
        if home_id or isinstance(query, int) or query.isnumeric():
            place_id = home_id or query
            response = await self.cog.api.get_places(int(place_id))
        elif guild:
            guild_config = self.cog.config.guild(guild)
            places = await guild_config.places()
            if abbrev in places:
                response = await self.cog.api.get_places(places[abbrev])

        if not response:
            response = await self.cog.api.get_places(
                "autocomplete", q=query, order_by="area"
            )

        if response:
            results = response.get("results")
            if results:
                place = results[0]

        if place:
            return Place.from_dict(place)

        raise LookupError("iNat place not known.")
