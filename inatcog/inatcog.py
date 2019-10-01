"""Module to access iNaturalist API."""
import functools
import logging
import re
from collections import namedtuple
from abc import ABC, abstractmethod
from redbot.core import commands
import discord
import requests
from pyparsing import Word, alphanums, Group, Forward, Suppress


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
    elif phrase_matched_name or phrase_matched_common:
        score = 210
    elif phrase_matched:
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
        phrase = re.compile(r'\b%s\b' % query, re.I)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(query, record, phrase=phrase)

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    return best_record if (not exact_query) or (best_score >= 200) else None

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

class BaseTaxonQueryParser(ABC):
    # pylint: disable=no-self-use
    """Abstract base parser for taxon queries."""
    def __init__(self):
        self._methods = {
            # TODO: 'in': self.evaluate_in,
            'and': self.evaluate_and,
            'quotes': self.evaluate_quotes,
            'word': self.evaluate_word,
            # TODO: 'id': self.evaluate_id,
        }
        self._parser = self.parser()

    def parser(self):
        # pylint: disable=pointless-statement
        # pylint: disable=expression-not-assigned
        """Return a parser."""
        op_word = Group(Word(alphanums)).setResultsName('word')

        op_quotes_content = Forward()
        op_quotes_content << ((op_word + op_quotes_content) | op_word)

        op_quotes = Group(
            Suppress('"') + op_quotes_content + Suppress('"')
        ).setResultsName("quotes") | op_word

        op_and = Forward()
        op_and << (op_quotes + op_and).setResultsName("and") | op_quotes

        return op_and.parseString

    def evaluate_and(self, argument):
        """Evaluate intersection of arguments."""
        return self.evaluate(argument[0]).intersection(self.evaluate(argument[1]))

    def evaluate_quotes(self, argument):
        """Evaluate quoted strings

        First it does an 'and' on the individual search terms, then it asks the
        function get_quoted to only return the subset of ID's that contain the
        literal string.
        """
        result = set()
        search_terms = []
        for item in argument:
            search_terms.append(item[0])
            if result:
                result = result.intersection(self.evaluate(item))
            else:
                result = self.evaluate(item)
        return self.get_quotes(' '.join(search_terms), result)

    def evaluate_word(self, argument):
        """Evaluate word."""
        return self.get_word(argument[0])

    def evaluate(self, argument):
        """Evaluate."""
        return self._methods[argument.getName()](argument)

    def parse(self, query):
        """Parse."""
        #print self._parser(query)[0]
        return self.evaluate(self._parser(query)[0])

    @abstractmethod
    def get_word(self, word):
        """Abstract get word. Returns a set matching the word (empty if unmatched)."""
        return set()

    @abstractmethod
    def get_quotes(self, search_string, tmp_result):
        """Abstract get quoted phrase. Returns a set matching the phrase (empty if unmatched)."""
        return set()

class TaxonQueryParser(BaseTaxonQueryParser):
    """Parser for taxon queries."""
    def get_word(self, word):
        """Abstract get word. Returns a set matching the word (empty if unmatched)."""
        # FIXME: does not match any words.
        return set()

    def get_quotes(self, search_string, tmp_result):
        """Abstract get quoted phrase. Returns a set matching the phrase (empty if unmatched)."""
        # FIXME: does not match any phrases.
        return set()

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
        rec = await self.maybe_match_taxon(ctx, embed, query)
        if rec:
            await self.send_taxa_embed(ctx, embed, rec)

    async def maybe_match_taxon(self, ctx, embed, query):
        """Get taxa and return a match, if any."""
        records = get_taxa(query)
        if not records:
            await self.sorry(ctx, embed, 'Nothing found')
            return
        rec = match_taxon(query, get_fields_from_results(records))
        if not rec:
            await self.sorry(ctx, embed, 'No exact match')
            return
        return rec

    async def sorry(self, ctx, embed, message="I don't understand"):
        """Notify user their request could not be satisfied."""
        embed.add_field(
            name='Sorry',
            value=message,
            inline=False,
        )
        await ctx.send(embed=embed)

    async def send_taxa_embed(self, ctx, embed, rec):
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
