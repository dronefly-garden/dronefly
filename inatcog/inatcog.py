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

        color = 0x90ee90
        embed = discord.Embed(color=color)

        records = await self.taxa_query(*terms) or []
        record = None

        if records:
            record = records[0]
            matched_term_is_a_name = False

            # Try to intelligently match code, name, or common name:
            treat_term_as_code = len(terms) == 1 and len(terms[0]) == 4
            code = terms[0].upper() if treat_term_as_code else None

            term = None
            for rec in records:
                if 'matched_term' in rec:
                    term = rec['matched_term']
                    name = rec['name']
                    common = rec['preferred_common_name']

                    matched_term_is_a_name = term in (name, common)
                    if matched_term_is_a_name or (code and term == code):
                        record = rec
                        break

            if term and not matched_term_is_a_name:
                embed.add_field(
                    name='Matched:',
                    value=term,
                    inline=False,
                )

        if record:
            common = None
            thumbnail = None
            name = record['name']
            inat_id = record['id']
            url = f'https://www.inaturalist.org/taxa/{inat_id}'
            if 'preferred_common_name' in record:
                common = record['preferred_common_name']
            if 'default_photo' in record:
                photo = record['default_photo']
                if photo and ('square_url' in photo):
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
        treat_as_id = len(terms) == 1 and terms[0].isdigit()

        if treat_as_id:
            results = requests.get(
                f'{inaturalist_api}taxa/{terms[0]}',
                headers={'Accept': 'application/json'},
            ).json()['results']
        else:
            results = requests.get(
                f'{inaturalist_api}taxa/',
                headers={'Accept': 'application/json'},
                params={'q': ' '.join(terms)},
            ).json()['results']

        return results
