"""Module to access iNaturalist API."""
from redbot.core import commands
import discord
from pyparsing import ParseException
from .common import EM_COLOR
from .api import WWW_BASE_URL
from .last import get_last_obs_msg, last_obs_embed
from .maps import get_map_coords_for_taxa
from .taxa import maybe_match_taxa, TAXON_QUERY_PARSER

class INatCog(commands.Cog):
    """An iNaturalist commands cog."""
    def __init__(self, bot):
        self.bot = bot

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

        if query.lower() in ('obs', 'observation'):
            try:
                msgs = await ctx.history(limit=1000).flatten()
                last = get_last_obs_msg(msgs)
            except StopIteration:
                await ctx.send('Nothing found')
                return None
        else:
            await ctx.send_help()
            return

        await ctx.send(embed=last_obs_embed(last))

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

        embed = discord.Embed(color=EM_COLOR)
        try:
            queries = list(map(TAXON_QUERY_PARSER.parse, query.split(',')))
        except ParseException:
            await self.sorry(ctx, embed)
            return

        taxa = {}
        for compound_query in queries:
            rec = maybe_match_taxa(compound_query)
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

        embed = discord.Embed(color=EM_COLOR)
        try:
            compound_query = TAXON_QUERY_PARSER.parse(query)
        except ParseException:
            await self.sorry(ctx)
            return

        try:
            rec = maybe_match_taxa(compound_query)
        except LookupError as err:
            await self.sorry(err.args)
        if rec:
            await self.send_taxa_embed(ctx, embed, rec)

    async def sorry(self, ctx, embed=discord.Embed(color=EM_COLOR), message="I don't understand"):
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
