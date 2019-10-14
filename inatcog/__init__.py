"""INatCog init."""
from .inatcog import INatCog


def setup(bot):
    """Add cog to bot."""
    bot.add_cog(INatCog(bot))
