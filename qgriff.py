import discord
import asyncio
from datetime import datetime, timedelta
from discord.ext import tasks, commands
import logging

logging.basicConfig(level=logging.INFO)

client = commands.Bot(command_prefix = ',')

with open('discord.key') as f:
    discord_key = f.readline().rstrip()

@client.event
async def on_ready():
    print('CuckooBee is ready.')

class HybridsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Run daily at specified time:
        (self.run_hr, self.run_min) = (5, 0) # scheduled for 05:00
        self.run_at = datetime(1, 1, 1) # never (run immediately)
        
        with open('ebird.key') as f:
            self.ebird_key = f.readline().rstrip()

    @commands.command()
    async def hybrids(self, ctx):
        # TODO: ensure only 1 hybrids_task & support cancelling it
        self.hybrids_task.start(ctx)

    # Wake up every 60 seconds to see if it's time to run
    # - see https://discordpy.readthedocs.io/en/latest/ext/tasks/
    @tasks.loop(seconds = 60)
    async def hybrids_task(self, ctx):
        now = datetime.now()
        # Past time to run & hasn't run yet:
        if (now >= self.run_at):
            # Schedule for today (in case running ahead of schedule):
            self.run_at = datetime(now.year, now.month, now.day, self.run_hr, self.run_min)
            running_ahead_of_schedule = (now.hour, now.minute) < (self.run_hr, self.run_min)
            if (not running_ahead_of_schedule):
               # Reschedule for tomorrow (i.e. the normal case):
                self.run_at += timedelta(days = 1)
            await self.report_hybrids(ctx)
        else:
            # Not time to run yet. Allow other tasks to run.
            await asyncio.sleep(1)
            
    async def report_hybrids(self, ctx):
            from ebird.api import get_observations
            # Docs at: https://github.com/ProjectBabbler/ebird-api
            records = get_observations(self.ebird_key, 'CA-NS', back =
                    30, category = "hybrid", provisional = True)
            message = []
            for record in records:
                sciname = record['sciName']
                comname = record['comName']
                locname = record['locName']
                print(f'Common name: {comname} Scientific name:{sciname} Location: {locname}')
                message.append(f'Common name: {comname} Scientific name:{sciname} Location: {locname}')
            await ctx.send("\n".join(message))

client.add_cog(HybridsCog(client))
client.run(discord_key)
