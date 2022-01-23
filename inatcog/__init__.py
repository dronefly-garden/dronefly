"""INatCog init."""
from redbot.core.utils import get_end_user_data_statement

from .help import INatHelp
from .inatcog import INatCog

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


def setup(bot):
    """Setup bot with our custom formatter, then add our cog.

    Note: incompatible with cogs providing their own help formatter, but inatcog
    is such a special-purpose cog, it's not really intended to use it on a
    general-purpose bot, so this is OK(-ish).
    """
    bot.set_help_formatter(INatHelp())
    bot.add_cog(INatCog(bot))


def teardown(bot):
    bot.reset_help_formatter()
