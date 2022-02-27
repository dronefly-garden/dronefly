"""Checks for iNatcog."""
from redbot.core import commands
from .utils import get_valid_user_config


async def _known_inat_user(ctx, anywhere):
    cog = ctx.bot.get_cog("iNat")
    if not cog:
        return False

    user_config = None
    try:
        user_config = await get_valid_user_config(cog, ctx.author, anywhere=anywhere)
    except LookupError:
        pass
    return bool(user_config)


def known_inat_user():
    """Allow command to be used by iNat user known in any guild."""

    async def check(ctx: commands.Context):
        """Check if iNat user is known anywhere.

        Note: Even if the user is known in another guild, they
        are not considered known anywhere until they permit it
        with `,user set known True`.
        """
        return await _known_inat_user(ctx, anywhere=True)

    return commands.check(check)


def known_inat_user_here():
    """Allow command to be used by iNat user known in this guild."""

    async def check(ctx: commands.Context):
        """Check if iNat user is known here."""
        return await _known_inat_user(ctx, anywhere=False)

    return commands.check(check)


def can_manage_users():
    """Check if guild member can manage users."""

    async def check(ctx: commands.Context) -> bool:
        """Author is bot owner, guild owner or admin, or has manage users role."""
        bot = ctx.bot
        cog = bot.get_cog("iNat")
        if not cog:
            return False
        guild = ctx.guild
        if not guild:
            # Everyone is a user manager in their own DM with the bot, but
            # the only user they can manage is themself.
            return True

        member = ctx.author
        if (
            member == guild.owner
            or await bot.is_owner(member)
            or await bot.is_admin(member)
        ):
            return True

        guild_config = cog.config.guild(guild)
        role_id = await guild_config.manage_users_role()
        manage_users_role = guild.get_role(role_id)
        return manage_users_role and manage_users_role in member.roles

    return commands.check(check)
