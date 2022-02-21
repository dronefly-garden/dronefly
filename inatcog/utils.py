"""Utilities module."""


async def get_valid_user_config(cog, ctx):
    """iNat user config known in this guild."""
    user_config = cog.config.user(ctx.author)
    inat_user_id = await user_config.inat_user_id()
    known_in = await user_config.known_in()
    known_all = await user_config.known_all()
    if not (inat_user_id and known_all or ctx.guild.id in known_in):
        raise LookupError("Ask a moderator to add your iNat profile link.")
    return user_config
