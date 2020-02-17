"""Module to handle users."""
from typing import Union
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin
from .api import WWW_BASE_URL


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

    async def get_place(self, guild, query: Union[int, str]):
        """Get place by guild abbr or via id#/keyword lookup in API."""
        place = None
        response = None

        if isinstance(query, int) or query.isnumeric():
            response = await self.cog.api.get_places(int(query))
        elif guild:
            abbrev = query.lower()
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
