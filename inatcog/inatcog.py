"""Module to access iNaturalist API."""
import re
from redbot.core import commands
from pyparsing import ParseException
from .api import get_observations
from .embeds import sorry, make_embed
from .last import get_last_obs_msg, make_last_obs_embed
from .maps import get_map_link_for_taxa
from .obs import get_obs_fields, make_obs_embed, PAT_OBS_LINK
from .taxa import query_taxa, query_taxon, make_taxa_embed


class INatCog(commands.Cog):
    """An iNaturalist commands cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass  # pylint: disable=unnecessary-pass

    @inat.command()
    async def last(self, ctx, *, query):
        """Lookup iNat links contained in recent messages.

        `[p]inat last obs` -> A brief summary of the last mentioned observation.
        Also, `[p]last` is an alias for `[p]inat last`, *provided the bot owner has added it*.
        """

        if query.lower() in ("obs", "observation"):
            try:
                msgs = await ctx.history(limit=1000).flatten()
                last = get_last_obs_msg(msgs)
            except StopIteration:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return None
        else:
            await ctx.send_help()
            return

        await ctx.send(embed=make_last_obs_embed(last))

    @inat.command()
    async def link(self, ctx, *, query):
        """Look up an iNat link and summarize its contents in an embed.

        e.g.
        ```
        [p]inat link https://inaturalist.org/observations/#
           -> an embed summarizing the observation link
        ```
        """
        mat = re.search(PAT_OBS_LINK, query)
        if mat:
            obs_id = int(mat["obs_id"])
            url = mat["url"]

            results = get_observations(obs_id)["results"]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=make_obs_embed(obs, url))
        else:
            await ctx.send(embed=sorry())

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

        try:
            taxa = query_taxa(query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        map_link = get_map_link_for_taxa(taxa)
        map_embed = make_embed(title=map_link.title, url=map_link.url)

        await ctx.send(embed=map_embed)

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

        try:
            taxon = query_taxon(query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        map_link = get_map_link_for_taxa([taxon])
        await ctx.send(embed=make_taxa_embed(taxon, map_link))
