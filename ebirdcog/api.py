"""Module to access eBird API."""
from ebird.api import get_region


class EBirdAPI:
    """EBird API helper class."""

    def __init__(self, cog):
        self.cog = cog

    async def get_region(self, channel, region_code):
        """Gets region observations."""
        ebird_key = await self.get_api_key(channel)
        if ebird_key is None:
            return False
        return get_region(ebird_key["api_key"], region_code)

    async def get_api_key(self, channel):
        """Gets API key."""
        key = await self.cog.bot.get_shared_api_tokens("ebird")
        if key["api_key"] is None:
            await channel.send(
                "The eBird API key is not set yet.\n"
                "1. Get one here:\n"
                "   https://ebird.org/api/keygen\n"
                "2. Set the key:\n"
                "   [p]set api ebird api_key,your-key-goes-here"
            )
            return None
        return key
