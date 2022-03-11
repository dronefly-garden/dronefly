"""Module for event command group."""

from redbot.core import checks, commands

from ..checks import can_manage_users
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta


class CommandsEvent(INatEmbeds, MixinMeta):
    """Mixin providing event command group."""

    @commands.group()
    @can_manage_users()
    async def event(self, ctx):
        """Commands to manage server events."""

    @event.command(name="join")
    async def event_join(self, ctx, abbrev: str, user):
        """Join member to server event."""

    @event.command(name="list")
    @checks.bot_has_permissions(embed_links=True)
    async def event_list(self, ctx, abbrev: str):
        """List members of server event."""
        await self.user_list(ctx, abbrev)

    @event.command(name="leave")
    async def event_leave(self, ctx, abbrev: str, user):
        """Remove member from server event."""
