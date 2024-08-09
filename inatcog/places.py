"""Module to handle users."""
from typing import Union

from pyinaturalist.models import Place

from .converters.base import QuotedContextMemberConverter
from .utils import get_home_server, get_hub_server, get_valid_user_config

RESERVED_PLACES = ["home", "none", "clear", "all", "any"]


class INatPlaceTable:
    """Lookup helper for places."""

    def __init__(self, cog):
        self.cog = cog

    async def get_place(
        self, guild, query: Union[int, str], user: QuotedContextMemberConverter = None
    ):
        """Get place by guild abbr or via id#/keyword lookup in API."""

        async def _get_place_abbrev(guild, abbrev):
            response = None
            guild_config = self.cog.config.guild(guild)
            places = await guild_config.places()
            if abbrev in places:
                response = await self.cog.api.get_places(places[abbrev])
            return response

        abbrev = query.lower() if isinstance(query, str) else None
        home_id = None
        place = None
        response = None
        _guild = guild or await get_home_server(self.cog, user)

        if abbrev == "home" and user:
            try:
                user_config = await get_valid_user_config(self.cog, user, anywhere=True)
                home_id = await user_config.home()
            except LookupError:
                pass
            if not home_id and _guild:
                guild_config = self.cog.config.guild(_guild)
                home_id = await guild_config.home()
            if not home_id:
                home_id = await self.cog.config.home()

        if not home_id and _guild and abbrev:
            response = await _get_place_abbrev(_guild, abbrev)
            if not response:
                hub_server = await get_hub_server(self.cog, _guild)
                if hub_server:
                    response = await _get_place_abbrev(hub_server, abbrev)

        if not response:
            if home_id or isinstance(query, int) or query.isnumeric():
                place_id = int(home_id or query)
                response = await self.cog.api.get_places(place_id)

        if not response:
            response = await self.cog.api.get_places(
                "autocomplete", q=query, order_by="area"
            )

        if response:
            results = response.get("results")
            if results:
                place = results[0]

        if place:
            return Place.from_json(place)

        raise LookupError("iNat place not known.")
