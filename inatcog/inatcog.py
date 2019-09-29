"""Module to access iNaturalist API."""
import functools
import logging
import re
from collections import namedtuple
from redbot.core import commands
import discord
import requests

Taxon = namedtuple('Taxon', 'name, taxon_id, common, term, thumbnail')
LOG = logging.getLogger('red.quaggagriff.inatcog')

def get_fields_from_results(results):
    """Map get_taxa results into namedtuples of selected fields."""
    def get_fields(record):
        photo = record.get('default_photo')
        rec = Taxon(
            record['name'],
            record['id'] if 'id' in record else record['taxon_id'],
            record.get('preferred_common_name'),
            record.get('matched_term'),
            photo.get('square_url') if photo else None,
        )
        return rec
    return list(map(get_fields, results))

RANKS = [
    'kingdom',
    'phylum',
    'subphylum',
    'superclass',
    'class',
    'subclass',
    'superorder',
    'order',
    'suborder',
    'infraorder',
    'superfamily',
    'epifamily',
    'family',
    'subfamily',
    'supertribe',
    'tribe',
    'subtribe',
    'genus',
    'genushybrid',
    'species',
    'hybrid',
    'subspecies',
    'variety',
    'form',
]

def get_taxa_from_user_args(function):
    """Map taxon query to /taxa API call arguments."""
    @functools.wraps(function)
    def query_wrapper(query, **kwargs):
        if query.isdigit():
            taxon_id = query
        else:
            words = query.split()
            query_words = []
            ranks = []
            for word in words:
                rank = word.lower()
                if rank in RANKS:
                    ranks.append(rank)
                else:
                    query_words.append(word)

            taxon_id = ''
            kwargs['q'] = ' '.join(query_words)
            if ranks:
                kwargs['rank'] = ','.join(ranks)
        return function(taxon_id, **kwargs)
    return query_wrapper

def score_match(query, record, phrase=None):
    """Score a matched record. A higher score is a better match."""
    score = 0
    if phrase:
        phrase_matched = re.search(phrase, record.term)
        phrase_matched_name = re.search(phrase, record.name)
        phrase_matched_common = re.search(phrase, record.common) if record.common else False
    else:
        phrase_matched = phrase_matched_name = phrase_matched_common = False

    if not phrase and len(query) == 4 and query.upper() == record.term:
        score = 300
    elif phrase_matched_name or phrase_matched_common or phrase_matched:
        score = 200
    else:
        score = 100

    LOG.info('Final score: %d', score)
    return score

def match_taxon(query, records):
    """Match a single taxon for the given query among records returned by API."""
    if re.match(r'".*"$', query):
        exact_query = query.replace('"', '')
        LOG.info('Matching exact query: %s', exact_query)
    else:
        exact_query = None

    if exact_query:
        phrase = re.compile(r'\b%s\b' % exact_query, re.I)
    else:
        phrase = None
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(query, record, phrase=phrase)

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    return (best_record, best_score) if (not exact_query) or (best_score >= 200) else (None, None)

@get_taxa_from_user_args
def get_taxa(*args, **kwargs):
    """Query /taxa for taxa matching parameters."""
    inaturalist_api = 'https://api.inaturalist.org/v1/'

    results = requests.get(
        f'{inaturalist_api}taxa/{args[0] if args else ""}',
        headers={'Accept': 'application/json'},
        params=kwargs,
    ).json()['results']

    return results

class INatCog(commands.Cog):
    """An iNaturalist commands cog."""
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger('red.quaggagriff.inatcog')

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass # pylint: disable=unnecessary-pass

    @inat.command()
    async def taxon(self, ctx, *, query):
        """Show taxon by id or unique code or name."""
        if not query:
            await ctx.send_help()
            return

        embed = discord.Embed(color=0x90ee90)
        records = get_taxa(query)
        if not records:
            await self.sorry(ctx, embed, 'Nothing found')
            return

        (rec, score) = match_taxon(query, get_fields_from_results(records))
        if not rec:
            await self.sorry(ctx, embed, 'No exact match')
            return

        await self.send_taxa_embed(ctx, embed, rec, score)

    async def sorry(self, ctx, embed, message="I don't understand"):
        """Notify user their request could not be satisfied."""
        embed.add_field(
            name='Sorry',
            value=message,
            inline=False,
        )
        await ctx.send(embed=embed)

    async def send_taxa_embed(self, ctx, embed, rec, score):
        """Send embed describing taxa record matched."""
        embed.title = '{name} ({common})'.format_map(rec._asdict()) if rec.common else rec.name
        embed.url = f'https://www.inaturalist.org/taxa/{rec.taxon_id}'
        if rec.thumbnail:
            embed.set_thumbnail(url=rec.thumbnail)
        matched = rec.term or rec.taxon_id
        if matched not in (rec.name, rec.common):
            embed.add_field(
                name='Matched:',
                value=matched,
                inline=False,
            )
        await ctx.send(embed=embed)
