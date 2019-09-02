"""Module to access eBird API."""
from datetime import datetime
from redbot.core import commands, checks, Config
from ebird.api import get_observations

class ObsRecord(dict):
    """A human-readable observation record."""
    def __init__(self, datetime_format='%H:%M, %d %b, %Y', **kwargs):
        self.datetime_format = datetime_format
        super().__init__(**kwargs)

    def __getitem__(self, key):
        """Reformat datetime into human-readable format."""
        val = super().__getitem__(key)
        if key == 'obsDt':
            return datetime.strptime(val, '%Y-%m-%d %H:%M').strftime(self.datetime_format)
        return val

class EBirdCog(commands.Cog):
    """An eBird commands cog."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8008)
        default_global = {
            "region": 'CA-NS',
            "days": 30,
            "datetime_format": '%H:%M, %d %b',
        }
        self.config.register_global(**default_global)

    @commands.group()
    async def ebird(self, ctx):
        """Access the eBird platform."""

    @ebird.command()
    async def hybrids(self, ctx):
        """Report recent hybrid observations."""
        records = await self.get_hybrid_observations(ctx) or []
        fmt = await self.config.datetime_format()
        for record in records:
            rec = ObsRecord(fmt, **record)
            msg = '{comName} ({sciName}); {howMany} observed at {obsDt}, from {locName}' \
                .format_map(rec)
            await ctx.send(msg)
        if not records:
            days = await self.config.days()
            await ctx.send("No hybrids observed in the past %d days." % days)

    @ebird.command()
    @checks.is_owner()
    async def setregion(self, ctx, value: str):
        """Set eBird region."""
        await self.config.region.set(value)
        await ctx.send('eBird region has been changed.')

    @ebird.command()
    @checks.is_owner()
    async def setdays(self, ctx, value: int):
        """Set eBird days to include in recent observations."""
        await self.config.days.set(value)
        await ctx.send('eBird days to include in recent observations has been changed.')

    async def get_hybrid_observations(self, ctx):
        """Get recent hybrid observations."""
        ebird_key = await self.get_api_key(ctx)
        if ebird_key is None:
            return
        region = await self.config.region()
        days = await self.config.days()
        # Docs at: https://github.com/ProjectBabbler/ebird-api
        return get_observations(
            ebird_key["api_key"],
            region,
            back=days,
            category="hybrid",
            detail="simple",
            provisional=True,
        )

    async def get_api_key(self, ctx):
        """Get API key."""
        key = await self.bot.db.api_tokens.get_raw("ebird", default={"api_key": None})
        if key["api_key"] is None:
            await ctx.send("The eBird API key has not been set.")
            return None
        return key
