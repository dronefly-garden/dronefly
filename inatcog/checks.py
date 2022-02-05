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
            return False

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
