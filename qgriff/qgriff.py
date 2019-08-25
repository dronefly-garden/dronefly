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

        self.count = 0
        self.start_time = datetime.now()
        self.timezone = get_localzone()
        self.datetime_format = self.bot.config.get('hybrids', 'datetime_format', fallback='%H:%M %Z%z, %d %b')
        self.region = self.bot.config.get('hybrids', 'region', fallback='CA-NS')
        self.days = self.bot.config.getint('hybrids', 'days', fallback=30)
        self.run_hr = self.bot.config.getint('hybrids', 'run_hr', fallback=5)
        self.run_min = self.bot.config.getint('hybrids', 'run_min', fallback=0)
        self.run_at = datetime(1, 1, 1) # never (run immediately)

        try:
            self.ebird_key = self.bot.config.get('ebird', 'key')
        except configparser.NoSectionError:
            self.bot.log.warning('No ebird section in qgriff.ini; eBird commands disabled')
            self.ebird_key = None
        except configparser.NoOptionError:
            self.bot.log.warning('No ebird.key in qgriff.ini; eBird commands disabled')
            self.ebird_key = None

    def cog_unload(self):
        self.hybrids_task.cancel() # pylint: disable=no-member

    @commands.command()
    async def hybrids(self, ctx):
        """The command to start daily scan & report hybrids on eBird."""
        if not self.hybrids_task.get_task(): # pylint: disable=no-member
            if self.ebird_key:
                self.bot.log.info("Starting hybrids task.")
                self.hybrids_task.start(ctx) # pylint: disable=no-member
            else:
                await ctx.send("Configuration missing: ebird.key must be set in qgriff.ini.")
        else:
            times = 'once' if self.count == 1 else '%d times' % self.count
            message = "%s hybrids have been reported %s since %s and will report next at %s." % (
                self.region,
                times,
                self.start_time.astimezone(self.timezone).strftime(self.datetime_format),
                self.run_at.astimezone(self.timezone).strftime(self.datetime_format),
            )
            self.bot.log.info(message)
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
            self.bot.log.info(line)
        await ctx.send("\n".join(message))

if __name__ == "__main__":
    import os.path
    import sys

    from appdirs import AppDirs
    import configparser

    DIRS = AppDirs('qgriff', 'Quaggagriff')
    CONFIG_FILES = list(map(
        lambda path: os.path.join(path, 'qgriff.ini'),
        [DIRS.site_config_dir, DIRS.user_config_dir, '.'],
    ))

    CONFIG = configparser.ConfigParser()
    CONFIG.read(CONFIG_FILES)

    try:
        if CONFIG.has_section('discord'):
            DISCORD_KEY = CONFIG.get('discord', 'key')
            # Precautionary measure to ensure no code in the bot has access to the key:
            CONFIG.remove_option('discord', 'key')
    except configparser.NoSectionError:
        sys.exit('Missing required discord section in qgriff.ini')
    except configparser.NoOptionError:
        sys.exit('Missing required discord.key in qgriff.ini')

    logging.basicConfig(level=logging.INFO)
    CLIENT = commands.Bot(command_prefix=',')
    CLIENT.config = CONFIG
    CLIENT.log = logging.getLogger('discord')

    @CLIENT.event
    async def on_ready():
        """Announce when bot is ready."""
        CLIENT.log.info('Quaggagriff bot %s is ready.', CLIENT.user.name)

    CLIENT.add_cog(HybridsCog(CLIENT))
    CLIENT.run(DISCORD_KEY)
