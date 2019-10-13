"""Module to access iNaturalist API."""
import logging
import re
from collections import namedtuple
from datetime import datetime
import timeago
from redbot.core import commands
import discord
from pyparsing import ParseException
from .parsers import TaxonQueryParser, RANKS
from .api import get_taxa, get_observations, WWW_BASE_URL
from .maps import get_map_coords_for_taxa
from .taxa import get_fields_from_results, match_taxon

LOG = logging.getLogger('red.quaggagriff.inatcog')

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

        ObsLinkMsg = namedtuple('ObsLinkMsg', 'url, obs, ago, name')
        async def last_observation_msg(ctx):
            found = None
            msgs = await ctx.history(limit=1000).flatten()

            found = next(m for m in msgs if not m.author.bot and re.search(PAT_OBS, m.content))
            LOG.info(repr(found))

            mat = re.search(PAT_OBS, found.content)
            obs_id = int(mat["obs_id"])
            url = mat["url"]
            ago = timeago.format(found.created_at, datetime.utcnow())
            name = found.author.nick or found.author.name
            results = get_observations(obs_id)["results"]
            obs = results[0] if results else None

            return ObsLinkMsg(url, obs, ago, name)

        def last_observation_embed(last):
            embed = discord.Embed(color=0x90ee90)
            embed.url = last.url
            summary = None

            if last:
                obs = last.obs
                community_taxon = obs.get("community_taxon")
                taxon = community_taxon or obs.get("taxon")
                if taxon:
                    sci_name = taxon["name"]
                    common = taxon.get("preferred_common_name")
                    embed.title = '%s (%s)' % (sci_name, common) if common else sci_name
                else:
                    embed.title = str(obs["obs_id"])
                photos = obs.get("photos")
                if photos:
                    thumbnail = photos[0].get("url")
                else:
                    thumbnail = None
                if thumbnail:
                    embed.set_thumbnail(url=thumbnail)
                observed_on = obs.get("observed_on_string")
                user = obs["user"]
                by_name = user.get("name")
                by_login = user.get("login")
                observed_by = by_name or by_login or "Somebody"
                if observed_on:
                    summary = 'Observed by %s on %s' % (observed_by, observed_on)
            else:
                LOG.info('Deleted observation: %d', obs["obs_id"])
                embed.title = 'Deleted'

            embed.add_field(
                name=summary or '\u200B', value='shared %s by @%s' % (last.ago, last.name)
            )
            return embed

        if query.lower() in ('obs', 'observation'):
            try:
                last = await last_observation_msg(ctx)
            except StopIteration:
                await ctx.send('Nothing found')
                return None
        else:
            await ctx.send_help()
            return

        await ctx.send(embed=last_observation_embed(last))

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
        for compound_query in queries:
            rec = await self.maybe_match_taxa(ctx, embed, compound_query)
            if rec:
                taxa[str(rec.taxon_id)] = rec
            else:
                return

        taxon_ids = list(taxa.keys())
        map_coords = get_map_coords_for_taxa(taxon_ids)
        await self.send_map_embed(ctx, embed, taxa, map_coords)

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

        rec = await self.maybe_match_taxa(ctx, embed, queries)
        if rec:
            await self.send_taxa_embed(ctx, embed, rec)

    async def maybe_match_taxa(self, ctx, embed, queries):
        """Get one or more taxon and return a match, if any.

        Currently the grammar supports only one ancestor taxon
        and one child taxon.
        """
        if queries.ancestor:
            rec = await self.maybe_match_taxon(ctx, embed, queries.ancestor)
            if rec:
                index = RANKS.index(rec.rank)
                ancestor_ranks = set(RANKS[index:len(RANKS)])
                child_ranks = set(queries.main.ranks)
                if child_ranks != set() and ancestor_ranks.intersection(child_ranks) == set():
                    await self.sorry(
                        ctx,
                        discord.Embed(color=0x90ee90),
                        'Child ranks must be below ancestor rank: %s' % rec.rank
                    )
                    return
                rec = await self.maybe_match_taxon(
                    ctx,
                    embed,
                    queries.main,
                    ancestor_id=rec.taxon_id
                )
        else:
            rec = await self.maybe_match_taxon(ctx, embed, queries.main)
        return rec

    async def maybe_match_taxon(self, ctx, embed, query, ancestor_id=None):
        """Get taxon and return a match, if any."""
        if query.taxon_id:
            records = get_taxa(query.taxon_id)
        else:
            kwargs = {}
            kwargs["q"] = ' '.join(query.terms)
            if query.ranks:
                kwargs["rank"] = ','.join(query.ranks)
            if ancestor_id:
                kwargs["taxon_id"] = ancestor_id
            records = get_taxa(**kwargs)
        if not records:
            LOG.info('Nothing found')
            await self.sorry(ctx, embed, 'Nothing found')
            return
        rec = match_taxon(query, get_fields_from_results(records), ancestor_id=ancestor_id)
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
        observations = rec.observations
        embed.add_field(
            name='Observations:',
            value=observations,
            inline=True,
        )
        if matched not in (rec.name, rec.common):
            embed.description = matched
        await ctx.send(embed=embed)

    async def send_map_embed(self, ctx, embed, taxa, map_coords):
        """Send embed linking to range map."""
        names = ', '.join([rec.name for rec in taxa.values()])
        embed.title = f"Range map for {names}"
        taxa = ','.join(list(taxa.keys()))
        zoom_lat_lon = '/'.join(map(str, map_coords))
        embed.url = f'{WWW_BASE_URL}/taxa/map?taxa={taxa}#{zoom_lat_lon}'
        await ctx.send(embed=embed)
