"""INatCog init."""

import discord
from redbot.core.utils import get_end_user_data_statement

from .help import INatHelp
from .inatcog import INatCog
from .commands.context import show_taxon

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot):
    """Setup bot

    - Supplies our custom formatter
      - Note: incompatible with cogs providing their own help formatter, but inatcog
        is such a special-purpose cog, it's not really intended to use it on a
        general-purpose bot, so this is OK(-ish).
    - Adds context commands
    """
    bot.set_help_formatter(INatHelp())
    cog = INatCog(bot)
    bot.tree.add_command(show_taxon)
    await bot.add_cog(cog)


def teardown(bot):
    """Teardown bot

    - tears down context commands
    - removes our custom help formatter
    """
    bot.tree.remove_command("Show taxon", type=discord.AppCommandType.message)
    bot.reset_help_formatter()
