"""Module to handle users."""
from typing import Union

from pyinaturalist.models import Place

from .converters.base import QuotedContextMemberConverter
from .utils import get_valid_user_config

RESERVED_PLACES = ["home", "none", "clear", "all", "any"]


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

        _guild = guild
        if not _guild and user:
            try:
                user_config = await get_valid_user_config(self.cog, user, anywhere=True)
                server_id = await user_config.server()
                _guild = next(
                    (
                        server
                        for server in self.cog.bot.guilds
                        if server.id == server_id
                    ),
                    None,
                )
            except LookupError:
                pass
        if isinstance(query, str):
            abbrev = query.lower()
            if abbrev == "home" and user:
                try:
                    user_config = await get_valid_user_config(
                        self.cog, user, anywhere=True
                    )
                    home_id = await user_config.home()
                except LookupError:
                    pass
                if not home_id and _guild:
                    guild_config = self.cog.config.guild(_guild)
                    home_id = await guild_config.home()
                if not home_id:
                    home_id = await self.cog.config.home()
        if home_id or isinstance(query, int) or query.isnumeric():
            place_id = home_id or query
            response = await self.cog.api.get_places(int(place_id))
        elif _guild:
            guild_config = self.cog.config.guild(_guild)
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
            return Place.from_json(place)

        raise LookupError("iNat place not known.")
