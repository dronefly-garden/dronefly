"""Module to access eBird API."""
from redbot.core import commands
import discord
import requests

def get_fields(record):
    """Deserialize just the fields we need from JSON record."""
    term = common = thumbnail = None

    name = record['name']
    inat_id = record['id']
    if 'preferred_common_name' in record:
        common = record['preferred_common_name']
    if 'matched_term' in record:
        term = record['matched_term']
    if 'default_photo' in record:
        photo = record['default_photo']
        if photo and ('square_url' in photo):
            thumbnail = photo['square_url']
    return {
        'name': name,
        'inat_id': inat_id,
        'common': common,
        'term': term,
        'thumbnail': thumbnail,
    }

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

        embed = discord.Embed(color=0x90ee90)
        records = await self.taxa_query(*terms)

        if not records:
            embed.add_field(
                name='Sorry',
                value='Nothing found',
                inline=False,
            )
            await ctx.send(embed=embed)
            return

        matched_term_is_a_name = False
        treat_term_as_code = len(terms) == 1 and len(terms[0]) == 4
        code = terms[0].upper() if treat_term_as_code else None

        # Find first record matching name, common name, or code
        rec = None
        for record in records:
            rec = get_fields(record)
            matched_term_is_a_name = rec['term'] in (rec['name'], rec['common'])
            if matched_term_is_a_name or (code and rec['term'] == code):
                break
            else:
                rec = None

        if not rec:
            rec = get_fields(records[0])

        embed.title = ('{name} ({common})').format_map(rec) if rec['common'] else rec['name']
        embed.url = f'https://www.inaturalist.org/taxa/{rec["inat_id"]}'
        if rec['thumbnail']:
            embed.set_thumbnail(url=rec['thumbnail'])

        if rec['term'] and not matched_term_is_a_name:
            embed.add_field(
                name='Matched:',
                value=rec['term'],
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
