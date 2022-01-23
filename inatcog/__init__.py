"""INatCog init."""
from redbot.core.utils import get_end_user_data_statement
from redbot.core.commands.commands import Command
from redbot.core.commands.help import RedHelpFormatter, HelpSettings

from .inatcog import INatCog

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)

CATEGORY_TAG = "\u200b"  # invisible help-only marker
CATEGORY_NAME = "iNat features, terms, and syntax"


class INatHelp(RedHelpFormatter):
    """Put help tagged as help-only in category separate from commands.'"""

    async def send_help(self, *args, **kwargs):
        return await super().send_help(*args, **kwargs)

    async def get_bot_help_mapping(self, ctx, help_settings: HelpSettings):
        def _additional_help(ctx, obj):
            return (
                isinstance(obj, Command)
                and obj.format_help_for_context(ctx).find(CATEGORY_TAG) == 0
            )

        sorted_iterable = []
        command_topics = {}
        additional_topics = {}
        for cogname, cog in (*sorted(ctx.bot.cogs.items()), (None, None)):
            cm = await self.get_cog_help_mapping(ctx, cog, help_settings=help_settings)
            if cm:
                if cogname == "iNat":
                    for key in cm:
                        if _additional_help(ctx, cm[key]):
                            additional_topics[key] = cm[key]
                        else:
                            command_topics[key] = cm[key]
                else:
                    sorted_iterable.append((cogname, cm))
        if command_topics:
            sorted_iterable.insert(0, ("iNat", command_topics))
        # Put these first, as they are otherwise easy to miss after
        # the lengthy list of commands.
        if additional_topics:
            sorted_iterable.insert(0, (CATEGORY_NAME, additional_topics))

        return sorted_iterable


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
