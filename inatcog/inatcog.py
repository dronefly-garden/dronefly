"""Module to access iNaturalist API."""
import logging
import re
import math
from collections import namedtuple
from datetime import datetime
import timeago
from redbot.core import commands
import discord
from pyparsing import ParseException
from .parsers import TaxonQueryParser, RANKS
from .api import get_taxa, get_observations, get_observation_bounds, WWW_BASE_URL

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

def score_match(query, record, all_terms, exact=None):
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

    if query.taxon_id:
        all_terms_matched = (None, None, None)
    else:
        all_terms_matched = (
            re.search(all_terms, record.term),
            re.search(all_terms, record.name),
            re.search(all_terms, record.common) if record.common else None,
        )

    if query.code and (query.code == record.term):
        score = 300
    elif matched[1] or matched[2]:
        score = 210
    elif matched[0]:
        score = 200
    elif all_terms_matched[1] or all_terms_matched[2]:
        score = 120
    elif all_terms_matched[0]:
        score = 110
    else:
        score = 100

    return score

def match_taxon(query, records):
    """Match a single taxon for the given query among records returned by API."""
    exact = []
    all_terms = re.compile(r'^%s$' % re.escape(' '.join(query.terms)), re.I)
    if query.phrases:
        for phrase in query.phrases:
            pat = re.compile(r'\b%s\b' % re.escape(' '.join(phrase)), re.I)
            exact.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(query, record, all_terms=all_terms, exact=exact)

    best_score = max(scores)
    LOG.info('Best score: %d', best_score)
    best_record = records[scores.index(best_score)]
    min_score_met = (not exact) or (best_score >= 200)
    LOG.info('Best match: %s%s', repr(best_record), '' if min_score_met else ' (score too low)')
    return best_record if min_score_met else None

PAT_OBS = re.compile(
    r'\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/observations/(?P<obs_id>\d+))\b',
    re.I,
)

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
    async def last(self, ctx, *, query):
        """Lookup iNat links contained in recent messages.

        `[p]inat last obs` -> A brief summary of the last mentioned observation.
        Also, `[p]last` is an alias for `[p]inat last`, *provided the bot owner has added it*.
        """

        found = None
        if query.lower() in ('obs', 'observation'):
            msgs = await ctx.history(limit=1000).flatten()
            try:
                found = next(m for m in msgs if not m.author.bot and re.search(PAT_OBS, m.content))
            except StopIteration:
                await ctx.send('Nothing found')
                return

        LOG.info(repr(found))
        mat = re.search(PAT_OBS, found.content)
        obs_id = int(mat["obs_id"])
        url = mat["url"]
        obs = get_observations(obs_id)["results"]

        ago = timeago.format(found.created_at, datetime.utcnow())
        name = found.author.nick or found.author.name
        embed = discord.Embed(color=0x90ee90)
        embed.url = url
        summary = None
        if obs:
            community_taxon = obs[0].get("community_taxon")
            taxon = community_taxon or obs[0].get("taxon")
            if taxon:
                sci_name = taxon["name"]
                common = taxon.get("preferred_common_name")
                embed.title = '%s (%s)' % (sci_name, common) if common else sci_name
            else:
                embed.title = str(obs_id)
            photos = obs[0].get("photos")
            if photos:
                thumbnail = photos[0].get("url")
            else:
                thumbnail = None
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            observed_on = obs[0].get("observed_on_string")
            user = obs[0]["user"]
            by_name = user.get("name")
            by_login = user.get("login")
            observed_by = by_name or by_login or "Somebody"
            if observed_on:
                summary = 'Observed by %s on %s' % (observed_by, observed_on)
        else:
            LOG.info('Deleted observation: %d', obs_id)
            embed.title = 'Deleted'

        embed.add_field(name=summary or '\u200B', value='shared %s by @%s' % (ago, name))
        await ctx.send(embed=embed)

    @inat.command()
    async def map(self, ctx, *, query):
        """Generate an observation range map of one or more species.

        **Examples:**
        ```
        [p]inat map polar bear
        [p]inat map 24255,24267
        [p]inat map boreal chorus frog,western chorus frog
        ```
        """

        def calc_distance(lat1, lon1, lat2, lon2):
            # pylint: disable=invalid-name
            r = 6371
            p1 = lat1 * math.pi / 180
            p2 = lat2 * math.pi / 180
            d1 = (lat2 - lat1) * math.pi / 180
            d2 = (lon2 - lon1) * math.pi / 180
            a = math.sin(d1 / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d2 / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

            return r * c

        def get_zoom_level(swlat, swlng, nelat, nelng):
            # pylint: disable=invalid-name
            d1 = calc_distance(swlat, swlng, nelat, swlng)
            d2 = calc_distance(swlat, nelng, nelat, nelng)

            arc_size = max(d1, d2)

            if arc_size == 0:
                return 10

            result = int(math.log2(20000 / arc_size) + 2)
            if result > 10:
                result = 10
            if result < 2:
                result = 2
            return result

        if not query:
            await ctx.send_help()
            return

        embed = discord.Embed(color=0x90ee90)
        try:
            queries = list(map(self.taxon_query_parser.parse, query.split(',')))
        except ParseException:
            await self.sorry(ctx, embed)
            return

        taxa = {}
        for qry in queries:
            rec = await self.maybe_match_taxon(ctx, embed, qry.main)
            if rec:
                taxa[str(rec.taxon_id)] = rec

        taxon_ids = list(taxa.keys())

        bounds = get_observation_bounds(taxon_ids)
        if not bounds:
            center_lat = 0
            center_lon = 0
            zoom_level = 2
        else:
            swlat = bounds["swlat"]
            swlng = bounds["swlng"]
            nelat = bounds["nelat"]
            nelng = bounds["nelng"]
            center_lat = (swlat + nelat) / 2
            center_lon = (swlng + nelng) / 2

            zoom_level = get_zoom_level(swlat, swlng, nelat, nelng)

        await self.send_map_embed(
            ctx,
            embed,
            taxa,
            zoom_level,
            center_lat,
            center_lon,
        )

    @inat.command()
    async def taxon(self, ctx, *, query):
        """Look up the taxon best matching the query.

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
                if child_ranks != set():
                    if ancestor_ranks.intersection(child_ranks) == set():
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
            LOG.info('Nothing found')
            await self.sorry(ctx, embed, 'Nothing found')
            return
        rec = match_taxon(query, get_fields_from_results(records))
        if not rec:
            LOG.info('No exact match')
            await self.sorry(ctx, embed, 'No exact match')
            return
        LOG.info('Matched')
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

    async def send_map_embed(self, ctx, embed, taxa, zoom_level, centerlat, centerlon):
        """Send embed linking to range map."""
        names = ', '.join([rec.name for rec in taxa.values()])
        embed.title = f"Range map for {names}"
        taxa = ','.join(list(taxa.keys()))
        embed.url = f'{WWW_BASE_URL}/taxa/map?taxa={taxa}#{zoom_level}/{centerlat}/{centerlon}'
        await ctx.send(embed=embed)
