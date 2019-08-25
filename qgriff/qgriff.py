"""The quaggagriff bot itself."""
import asyncio
import logging
from datetime import datetime, timedelta
from tzlocal import get_localzone
from discord.ext import tasks, commands

class HybridsCog(commands.Cog):
    """The hybrids command and scheduled task."""
    def __init__(self, bot):
        self.bot = bot
        self.region = 'CA-NS'
        self.days = 30
        self.count = 0
        self.start_time = datetime.now()
        self.timezone = get_localzone()
        self.datetime_format = '%H:%M %Z%z, %d %b'
        self.log = logging.getLogger('discord')

        # Run daily at specified time:
        (self.run_hr, self.run_min) = (5, 0) # scheduled for 05:00
        self.run_at = datetime(1, 1, 1) # never (run immediately)

        with open('ebird.key') as ebird_key_file:
            self.ebird_key = ebird_key_file.readline().rstrip()

    def cog_unload(self):
        self.hybrids_task.cancel() # pylint: disable=no-member

    @commands.command()
    async def hybrids(self, ctx):
        """The command to start daily scan & report hybrids on eBird."""
        if not self.hybrids_task.get_task(): # pylint: disable=no-member
            self.log.info("Starting hybrids task.")
            self.hybrids_task.start(ctx) # pylint: disable=no-member
        else:
            times = 'once' if self.count == 1 else '%d times' % self.count
            message = "%s hybrids have been reported %s since %s and will report next at %s." % (
                self.region,
                times,
                self.start_time.astimezone(self.timezone).strftime(self.datetime_format),
                self.run_at.astimezone(self.timezone).strftime(self.datetime_format),
            )
            self.log.info(message)
            await ctx.send(message)

    # - see https://discordpy.readthedocs.io/en/latest/ext/tasks/
    @tasks.loop(seconds=60)
    async def hybrids_task(self, ctx):
        """Check scheduled time & when reached, do a hybrids report."""
        now = datetime.now()
        # Past time to run & hasn't run yet:
        if now >= self.run_at:
            # Schedule for today (in case running ahead of schedule):
            self.run_at = datetime(now.year, now.month, now.day, self.run_hr, self.run_min)
            running_ahead_of_schedule = (now.hour, now.minute) < (self.run_hr, self.run_min)
            if not running_ahead_of_schedule:
               # Reschedule for tomorrow (i.e. the normal case):
                self.run_at += timedelta(days=1)
            await self.report_hybrids(ctx)
        else:
            # Not time to run yet. Allow other tasks to run.
            await asyncio.sleep(1)

    async def report_hybrids(self, ctx):
        """From eBird, get recent hybrid sightings for a region and report them."""
        from ebird.api import get_observations
        self.count += 1
        # Docs at: https://github.com/ProjectBabbler/ebird-api
        records = get_observations(
            self.ebird_key,
            self.region,
            back=self.days,
            category="hybrid",
            provisional=True,
        )
        message = []
        for record in records:
            sciname = record['sciName']
            comname = record['comName']
            locname = record['locName']
            obsdt = datetime.strptime(record['obsDt'], '%Y-%m-%d %H:%M')
            line = '%s: %s (%s) at %s' % (
                obsdt.astimezone(self.timezone).strftime(self.datetime_format),
                comname,
                sciname,
                locname,
            )
            message.append(line)
        for line in message:
            self.log.info(line)
        await ctx.send("\n".join(message))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    CLIENT = commands.Bot(command_prefix=',')
    @CLIENT.event
    async def on_ready():
        """Announce when bot is ready."""
        logging.getLogger('discord').info('Quaggagriff bot %s is ready.', CLIENT.user.name)

    with open('discord.key') as discord_key_file:
        DISCORD_KEY = discord_key_file.readline().rstrip()

    CLIENT.add_cog(HybridsCog(CLIENT))
    CLIENT.run(DISCORD_KEY)
