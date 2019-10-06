"""Module to access iNaturalist API."""
import logging
import re
from collections import namedtuple
from redbot.core import commands
import discord
import requests
from pyparsing import ParseException
from .parsers import TaxonQueryParser, RANKS

Taxon = namedtuple('Taxon', 'name, taxon_id, common, term, thumbnail, rank')
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
            record['rank'],
        )
        return rec
    return list(map(get_fields, results))

def score_match(query, record, exact=None):
    """Score a matched record. A higher score is a better match."""
    score = 0
    matched = (None, None, None)
    if exact:
        try:
            # Every pattern must match at least one field:
            for pat in exact:
                this_match = (
                    re.search(pat, record.term),
                    re.search(pat, record.name),
                    re.search(pat, record.common) if record.common else None,
                )
                if this_match == (None, None, None):
                    matched = this_match
                    raise ValueError('At least one field must match.')
                matched = (
                    matched[0] or this_match[0],
                    matched[1] or this_match[1],
                    matched[2] or this_match[2],
                )
        except ValueError:
            pass

    # TODO: parser should comprehend a code as a separate entity
    if not exact and len(query.terms) == 4 and query.terms.upper() == record.term:
        score = 300
    elif matched[1] or matched[2]:
        score = 210
    elif matched[0]:
        score = 200
    else:
        score = 100

    LOG.info('Final score: %d', score)
    return score

def match_taxon(query, records):
    """Match a single taxon for the given query among records returned by API."""
    exact = []
    if query.phrases:
        for phrase in query.phrases:
            pat = re.compile(r'\b%s\b' % re.escape(' '.join(phrase)), re.I)
            LOG.info('Pat: %s', repr(pat))
            exact.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(query, record, exact=exact)

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    return best_record if (not exact) or (best_score >= 200) else None

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
        self.taxon_query_parser = TaxonQueryParser()

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass # pylint: disable=unnecessary-pass

    @inat.command()
    async def taxon(self, ctx, *, query):
        """Looks up the taxon best matching the query. It will:

        - Match the taxon with the given iNat id#.
        - Match words that start with the terms typed.
        - Exactly match words enclosed in double-quotes.
        - Match a taxon 'in' an ancestor taxon.
        - Filter matches by rank keywords before or after other terms.
        - Match the AOU 4-letter code (if it's in iNat's Taxonomy).
        **Examples:**
        ```
        [p]inat taxon bear family
           -> Ursidae (Bears)
        [p]inat taxon prunella
           -> Prunella (self-heals)
        [p]inat taxon prunella in animals
           -> Prunella
        [p]inat taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        Also, `[p]sp`, `[p]ssp`, `[p]family`, `[p]subfamily`, etc. are
        shortcuts for the corresponding `[p]inat taxon` *rank* commands
        (provided the bot owner has created those aliases).
        """

        if not query:
            await ctx.send_help()
            return

        embed = discord.Embed(color=0x90ee90)
        try:
            queries = self.taxon_query_parser.parse(query)
        except ParseException:
            await self.sorry(ctx, discord.Embed(color=0x90ee90))
            return

        rec = None
        if queries.ancestor:
            rec = await self.maybe_match_taxon(ctx, embed, queries.ancestor)
            if rec:
                index = RANKS.index(rec.rank)
                ancestor_ranks = set(RANKS[index:len(RANKS)])
                child_ranks = set(queries.main.ranks)
                if not child_ranks.intersection(ancestor_ranks):
                    await self.sorry(
                        ctx,
                        discord.Embed(color=0x90ee90),
                        'Child ranks must be below ancestor rank: %s' % rec.rank
                    )
                    return
                rec = await self.maybe_match_taxon(ctx, embed, queries.main, ancestor=rec.taxon_id)
        else:
            rec = await self.maybe_match_taxon(ctx, embed, queries.main)
        if rec:
            await self.send_taxa_embed(ctx, embed, rec)

    async def maybe_match_taxon(self, ctx, embed, query, ancestor=None):
        """Get taxa and return a match, if any."""
        if query.taxon_id:
            records = get_taxa(query.taxon_id)
        else:
            kwargs = {}
            kwargs["q"] = ' '.join(query.terms)
            if query.ranks:
                kwargs["rank"] = ','.join(query.ranks)
            if ancestor:
                kwargs["taxon_id"] = ancestor
            records = get_taxa(**kwargs)
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
