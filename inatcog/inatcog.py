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

def get_fields(record):
    """Deserialize just the fields we need from JSON record."""
    photo = record.get('default_photo')
    rec = Taxon(
        record['name'],
        record['id'],
        record.get('preferred_common_name'),
        record.get('matched_term'),
        photo.get('square_url') if photo else None,
    )
    return rec

def get_taxa_from_user_args(function):
    """Decorator to map user arguments into get_taxa iNat api wrapper arguments."""
    @functools.wraps(function)
    def terms_wrapper(terms, **kwargs):
        treat_as_id = terms.isdigit()
        if not treat_as_id:
            kwargs['q'] = terms
            terms = ''
        return function(terms, **kwargs)
    return terms_wrapper

def match_taxon(terms, records):
    """Match a single taxon for the given terms among recorgs returned by API."""
    matched_term_is_a_name = False
    treat_term_as_code = len(terms) == 4

    treat_terms_as_phrase = bool(re.match(r'".*"$', terms))
    if treat_terms_as_phrase:
        phrase = re.compile(r'\b%s\b' % terms.replace('"', ''), re.I)
    code = terms.upper() if treat_term_as_code else None

    # Find first record matching name, common name, or code
    rec = None
    # Initial candidate record if no more suitable record is found is just the
    # first record returned (i.e. topmost taxon that matches).
    first_record = first_phrase_record = None
    for record in records:
        rec = get_fields(record)
        if not first_record:
            first_record = rec
        matched_term_is_a_name = rec.term in (rec.name, rec.common)
        LOG.info('terms: %s', terms)
        LOG.info('treat_terms_as_phrase: %s', treat_terms_as_phrase)
        LOG.info('matched_term_is_a_name: %s', matched_term_is_a_name)
        if matched_term_is_a_name or (code and rec.term == code):
            if not matched_term_is_a_name:
                LOG.info('matched term is a code')
            if treat_terms_as_phrase and matched_term_is_a_name:
                if re.search(phrase, rec.term):
                    LOG.info('matched phrase in name')
                    break
            else:
                break
        else:
            if treat_terms_as_phrase:
                # If non-code, non-name, non-common-name, phrase match will pick
                # the first matching term as a candidate_record in case no later
                # records match on the code or name.
                if not first_phrase_record and re.search(phrase, rec.term):
                    first_phrase_record = rec
            rec = None

    if not rec:
        if first_phrase_record:
            LOG.info('matched phrase in another term')
            rec = first_phrase_record
        else:
            LOG.info('matched first record (no better match)')
            rec = first_record
    return rec

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

        rec = match_taxon(terms, records)

        embed.title = '{name} ({common})'.format_map(rec._asdict()) if rec.common else rec.name
        embed.url = f'https://www.inaturalist.org/taxa/{rec.inat_id}'
        if rec.thumbnail:
            embed.set_thumbnail(url=rec.thumbnail)

        if rec.term and rec.term not in (rec.name, rec.common):
            embed.add_field(
                name='Matched:',
                value=rec.term,
                inline=False,
            )

        await ctx.send(embed=embed)
