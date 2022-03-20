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


async def _can_manage(ctx: commands.Context, what: str, dm_allowed: False) -> bool:
    bot = ctx.bot
    cog = bot.get_cog("iNat")
    if not cog:
        return False
    guild = ctx.guild
    if not guild:
        return dm_allowed

    member = ctx.author
    if (
        member == guild.owner
        or await bot.is_owner(member)
        or await bot.is_admin(member)
    ):
        return True

    guild_config = cog.config.guild(guild)
    role_id = await guild_config.get_raw(f"manage_{what}_role")
    if not role_id:
        return None

    manage_role = guild.get_role(role_id)
    return manage_role and manage_role in member.roles


def can_manage_places():
    """Check if guild member can manage places."""

    async def check(ctx: commands.Context) -> bool:
        """Author is bot owner, guild owner or admin, or has manage places role.
            
        If no can_manage_places role is set, users that were added by a user
        manager in the current server are implicitly trusted to manage places.
        """
        can_manage = await _can_manage(ctx, "places", dm_allowed=False)
        if can_manage is None:
            return await _known_inat_user(ctx, anywhere=False)
        return can_manage

    return commands.check(check)


def can_manage_projects():
    """Check if guild member can manage projects."""

    async def check(ctx: commands.Context) -> bool:
        """Author is bot owner, guild owner or admin, or has manage places role.
            
        If no can_manage_projects role is set, users that were added by a user
        manager in the current server are implicitly trusted to manage projects.
        """
        can_manage = await _can_manage(ctx, "projects", dm_allowed=False)
        if can_manage is None:
            return await _known_inat_user(ctx, anywhere=False)
        return can_manage

    return commands.check(check)


def can_manage_users():
    """Check if guild member can manage users."""

    async def check(ctx: commands.Context) -> bool:
        """Author is bot owner, guild owner or admin, or has manage users role."""
        can_manage = await _can_manage(ctx, "users", dm_allowed=False)
        return bool(can_manage)

    return commands.check(check)
