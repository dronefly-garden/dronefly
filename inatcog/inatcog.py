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

def get_taxa_from_user_args(function):
    """Map taxon subcommand arguments to /taxa API call arguments."""
    @functools.wraps(function)
    def terms_wrapper(terms, **kwargs):
        treat_as_id = terms.isdigit()
        if not treat_as_id:
            kwargs['q'] = terms
            terms = ''
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
    async def taxon(self, ctx, *, terms):
        """Show taxon by id or unique code or name."""
        if not terms:
            await ctx.send_help()
            return

        embed = discord.Embed(color=0x90ee90)
        records = get_taxa(terms)

        if not records:
            embed.add_field(
                name='Sorry',
                value='Nothing found',
                inline=False,
            )
            await ctx.send(embed=embed)
            return

        (rec, score) = match_taxon(terms, get_fields_from_results(records))

        if not rec:
            embed.add_field(
                name='Sorry',
                value='No exact match',
                inline=False,
            )
            await ctx.send(embed=embed)
            return

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
