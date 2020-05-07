"""Checks for iNatcog."""
from redbot.core import commands


def known_inat_user():
    """Allow command to be used by known iNat users."""

    async def check(ctx: commands.Context):
        """Check for known iNat user."""
        if not ctx.guild:
            return False
        cog = ctx.bot.get_cog("iNat")
        if not cog:
            return False

        user_config = None
        try:
            user_config = await cog.get_valid_user_config(ctx)
        except LookupError:
            pass
        return bool(user_config)

    return commands.check(check)
