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
        self.timezone = get_localzone()
        self.datetime_format = self.bot.config.get('hybrids', 'datetime_format', fallback='%H:%M %Z%z, %d %b')
        self.region = self.bot.config.get('hybrids', 'region', fallback='CA-NS')
        self.days = self.bot.config.getint('hybrids', 'days', fallback=30)
        self.run_hr = self.bot.config.getint('hybrids', 'run_hr', fallback=5)
        self.run_min = self.bot.config.getint('hybrids', 'run_min', fallback=0)
        self.tasks = {}

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
        start_tasks = False
        if not self.tasks:
            if self.ebird_key:
                self.bot.log.info("Initializing hybrids tasks.")
                start_tasks = True
            else:
                await ctx.send("Configuration missing: ebird.key must be set in qgriff.ini.")
        if not ctx.channel.id in self.tasks:
            self.tasks[ctx.channel.id] = {
                "count": 0,
                "ctx": ctx,
                "run_at": datetime(1, 1, 1), # Never
                "start": datetime.now(),
            }
            if start_tasks:
                self.hybrids_task.start() # pylint: disable=no-member
            else:
                self.hybrids_task.restart() # pylint: disable=no-member
        else:
            task = self.tasks[ctx.channel.id]
            times = 'once' if task["count"] == 1 else '%d times' % task["count"]
            message = "%s hybrids have been reported %s since %s and will report next at %s." % (
                self.region,
                times,
                task["start"].astimezone(self.timezone).strftime(self.datetime_format),
                task["run_at"].astimezone(self.timezone).strftime(self.datetime_format),
            )
            self.bot.log.info(message)
            await task["ctx"].send(message)

    # - see https://discordpy.readthedocs.io/en/latest/ext/tasks/
    @tasks.loop(seconds=60)
    async def hybrids_task(self):
        """Check scheduled time & when reached, do a hybrids report."""
        now = datetime.now()
        # Past time to run & hasn't run yet:
        reported = False
        for channel_id in self.tasks:
            task = self.tasks[channel_id]
            if now >= task["run_at"]:
                # Schedule for today (in case running ahead of schedule):
                task["run_at"] = datetime(now.year, now.month, now.day, self.run_hr, self.run_min)
                running_ahead_of_schedule = (now.hour, now.minute) < (self.run_hr, self.run_min)
                if not running_ahead_of_schedule:
                # Reschedule for tomorrow (i.e. the normal case):
                    task["run_at"] += timedelta(days=1)
                reported = True
                await self.report_hybrids(task)
        if not reported:
            # No reports made. Allow other tasks to run.
            await asyncio.sleep(1)

    async def report_hybrids(self, task):
        """From eBird, get recent hybrid sightings for a region and report them."""
        from ebird.api import get_observations
        task["count"] += 1
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
        await task["ctx"].send("\n".join(message))

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

    DISCORD_KEY = CONFIG.get('discord', 'key', fallback=None)
    if DISCORD_KEY is None:
        sys.exit('Missing required discord.key in qgriff.ini')
    # Precautionary measure to ensure no code in the bot has access to the key:
    CONFIG.remove_option('discord', 'key')

    logging.basicConfig(level=logging.INFO)
    CLIENT = commands.Bot(CONFIG.get('bot', 'command_prefix', fallback=','))
    CLIENT.config = CONFIG
    CLIENT.log = logging.getLogger('discord')

    @CLIENT.event
    async def on_ready():
        """Announce when bot is ready."""
        CLIENT.log.info('Quaggagriff bot %s is ready.', CLIENT.user.name)

    CLIENT.add_cog(HybridsCog(CLIENT))
    CLIENT.run(DISCORD_KEY)
