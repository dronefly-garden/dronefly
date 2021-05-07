"""EbirdCog init."""
from redbot.core.utils import get_end_user_data_statement

from .ebirdcog import EBirdCog

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


def setup(bot):
    """Add cog to bot."""
    bot.add_cog(EBirdCog(bot))
