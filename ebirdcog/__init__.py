"""EbirdCog init."""
from .ebirdcog import EBirdCog

def setup(bot):
    """Add cog to bot."""
    bot.add_cog(EBirdCog(bot))
