"""Module to access eBird API."""
from redbot.core import commands
import discord
import requests

class INatCog(commands.Cog):
    """An iNaturalist commands cog."""
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass # pylint: disable=unnecessary-pass

    @inat.command()
    async def taxon(self, ctx, *terms):
        """Show taxon by id or unique code or name."""
        records = await self.taxa_query(*terms) or []

        color = 0x90ee90
        embed = discord.Embed(color=color)

        record = records[0] if records and records[0] else None

        if record:
            common = None
            thumbnail = None
            name = record['name']
            key = 'preferred_common_name'
            if key in record:
                common = record[key]
            key = 'default_photo'
            if key in record:
                photo = record[key]
                key = 'square_url'
                if key in photo:
                    thumbnail = photo['square_url']

            embed.add_field(
                name=name,
                value=common or '\u200b',
                inline=False,
            )

            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
        else:
            embed.add_field(
                name='Sorry',
                value='Nothing found',
                inline=False,
            )

        await ctx.send(embed=embed)

    async def taxa_query(self, *terms):
        """Query /taxa for taxa matching terms."""
        inaturalist_api = 'https://api.inaturalist.org/v1/'
        results = requests.get(
            inaturalist_api + 'taxa/',
            headers={'Accept': 'application/json'},
            params={'q':' '.join(terms)},
        ).json()['results']
        return results
