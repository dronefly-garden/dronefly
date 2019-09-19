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
        if not terms:
            await ctx.send_help()
            return

        records = await self.taxa_query(*terms) or []
        record = None

        color = 0x90ee90
        embed = discord.Embed(color=color)

        if records:
            matches = len(records)
            record = records[0]
            # Try to intelligently match up a better result instead of just using first:
            if matches > 1:
                treat_term_as_code = len(terms) == 1 and len(terms[0]) == 4
                match_term = terms[0].upper() if treat_term_as_code else None

                for rec in records:
                    term = rec['matched_term']
                    if match_term and term == match_term:
                        record = rec
                        break

        if record:
            common = None
            thumbnail = None
            name = record['name']
            key = 'preferred_common_name'
            inat_id = record['id']
            url = f'https://www.inaturalist.org/taxa/{inat_id}'
            if key in record:
                common = record[key]
            key = 'default_photo'
            if key in record:
                photo = record[key]
                key = 'square_url'
                if key in photo:
                    thumbnail = photo['square_url']

            embed.title = f'{name} ({common})' if common else name
            embed.url = url
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
