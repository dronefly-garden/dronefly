"""Module to handle users."""
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin


@dataclass
class Place(DataClassJsonMixin):
    """A place."""

    place_id: int = field(metadata=config(field_name="id"))
    name: str


async def get_place(cog, guild, query):
    """Get place by guild abbr or via id#/keyword lookup in API."""
    place = None
    response = None

    if query.isnumeric():
        response = await cog.api.get_places(query)
    elif guild:
        abbrev = query.lower()
        guild_config = cog.config.guild(guild)
        places = await guild_config.places()
        if abbrev in places:
            response = await cog.api.get_places(places[abbrev])

    if not response:
        response = await cog.api.get_places("autocomplete", q=query, order_by="area")

    if response:
        results = response.get("results")
        if results:
            place = results[0]

    return place
