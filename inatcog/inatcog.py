"""Module to access iNaturalist API."""
import functools
import logging
import re
from collections import namedtuple
from redbot.core import commands
import discord
import requests

Taxon = namedtuple('Taxon', 'name, inat_id, common, term, thumbnail')
LOG = logging.getLogger('red.quaggagriff.inatcog')

def get_fields_from_results(results):
    """Map get_taxa results into namedtuples of selected fields."""
    def get_fields(record):
        photo = record.get('default_photo')
        rec = Taxon(
            record['name'],
            record['id'],
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
    def terms_wrapper(query, **kwargs):
        if query.isdigit():
            terms = query
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

            terms = ''
            kwargs['q'] = ' '.join(query_words)
            if ranks:
                kwargs['rank'] = ','.join(ranks)
        return function(terms, **kwargs)
    return terms_wrapper

def score_match(terms, record, phrase=None):
    """Score a matched record. A higher score is a better match."""
    score = 0
    if phrase:
        phrase_matched_name = re.search(phrase, record.name)
        phrase_matched_common = re.search(phrase, record.common) if record.common else False
        if not phrase_matched_name or phrase_matched_common:
            phrase_matched = re.search(phrase, record.term)
        else:
            phrase_matched = None
    else:
        phrase_matched = phrase_matched_name = phrase_matched_common = False

    if not phrase and len(terms) == 4 and terms.upper() == record.term:
        score = 300
    elif phrase_matched_name:
        score = 220
    elif phrase_matched_common:
        score = 210
    elif phrase_matched:
        score = 200
    elif record.term == record.name:
        score = 120
    elif record.term == record.common:
        score = 110
    else:
        score = 100

    LOG.info('Final score: %d', score)
    return score

def match_taxon(terms, records):
    """Match a single taxon for the given terms among records returned by API."""
    if re.match(r'".*"$', terms):
        exact_terms = terms.replace('"', '')
        LOG.info('Matching exact terms: %s', exact_terms)
    else:
        exact_terms = None

    phrase = re.compile(r'\b%s\b' % (exact_terms or terms), re.I)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(terms, record, phrase=phrase)

    if scores[0] == 0:
        scores[0] = 10

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    return (best_record, best_score) if (not exact_terms) or (best_score >= 200) else (None, None)

@get_taxa_from_user_args
def get_taxa(*args, **kwargs):
    """Query /taxa for taxa matching terms."""
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
        embed.url = f'https://www.inaturalist.org/taxa/{rec.inat_id}'
        if rec.thumbnail:
            embed.set_thumbnail(url=rec.thumbnail)
        if score <= 200:
            embed.add_field(
                name='Matched:',
                value=rec.term,
                inline=False,
            )
        await ctx.send(embed=embed)
