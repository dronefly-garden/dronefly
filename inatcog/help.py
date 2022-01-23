"""Custom iNat help module."""
import dataclasses
import re

from redbot.core.commands.commands import Command
from redbot.core.commands.help import RedHelpFormatter, HelpSettings

# When CATEGORY_TAG is found in the help text, it trigers custom
# help features for "additional help" (i.e. help-only commands):
# - The additional help topic:
#   - Is streamlined, suppressing all features pertaining to commands
#     (syntax, aliases, default tagline).
#   - Is put in a custom separate category with CATEGORY_NAME.
# - The help categories are reordered as follows:
#   - The additional help category is listed first.
#   - Then the remaining help topics from PRIORITIZED_COG are listed.
#   - Finally, help from all other cogs are listed after that.

CATEGORY_TAG = "\u200b"
CATEGORY_NAME = "iNat features, terms, and syntax"
PRIORITIZED_COG = "iNat"
EMPTY_SYNTAX_BOX = re.compile(r"```.*\nSyntax: None\n+```", re.MULTILINE)


def _additional_help(ctx, obj):
    return (
        isinstance(obj, Command)
        and obj.format_help_for_context(ctx).find(CATEGORY_TAG) == 0
    )


class INatHelp(RedHelpFormatter):
    """Custom help, with support for additional (non-command) help topics."""

    @staticmethod
    def get_command_signature(ctx, command):
        if _additional_help(ctx, command):
            # Omit "Syntax:" for additional help, as it is not a command.
            # - sadly, Red's format_command_help doesn't handle this, so later
            #   we do a horrific kludge to remove the empty Syntax section
            return None
        else:
            return RedHelpFormatter.get_command_signature(ctx, command)

    async def send_help(self, *args, **kwargs):
        return await super().send_help(*args, **kwargs)

    async def format_command_help(self, ctx, obj, help_settings: HelpSettings):
        if _additional_help(ctx, obj):
            _help_settings = dataclasses.replace(
                help_settings, show_aliases=False, tagline=" "
            )
            await super().format_command_help(ctx, obj, _help_settings)
            return

        await super().format_command_help(ctx, obj, help_settings)

    async def make_and_send_embeds(self, ctx, emb, help_settings: HelpSettings):
        embed = emb["embed"]
        # The horrors! This only works for help embeds and not help as text.
        # Also the removal of the empty "Syntax:" box is highly dependent on the
        # implementation of Red's formatting or the pattern won't match.
        _emb = {
            **emb,
            "embed": {
                **embed,
                "description": re.sub(EMPTY_SYNTAX_BOX, "", embed["description"]),
            },
        }
        await super().make_and_send_embeds(ctx, _emb, help_settings)

    async def get_bot_help_mapping(self, ctx, help_settings: HelpSettings):
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
        # Insert our help before help from all other cogs:
        if command_topics:
            sorted_iterable.insert(0, (PRIORITIZED_COG, command_topics))
        # Insert additional help before commands help:
        if additional_topics:
            sorted_iterable.insert(0, (CATEGORY_NAME, additional_topics))

        return sorted_iterable
