"""INatCog init."""
from redbot.core.utils import get_end_user_data_statement

from .inat import INat

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot):
    """Setup bot."""
    cog = INat(bot)
    await bot.add_cog(cog)
