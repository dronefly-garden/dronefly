"""Module to access iNaturalist API."""

from abc import ABC
import re
from redbot.core import commands, Config
from pyparsing import ParseException
from .api import WWW_BASE_URL, get_observations
from .embeds import sorry
from .inat_embeds import INatEmbeds
from .last import get_last_obs_msg
from .obs import get_obs_fields, PAT_OBS_LINK
from .parsers import RANK_EQUIVALENTS, RANK_KEYWORDS
from .taxa import (
    get_taxa,
    get_taxon_ancestor,
    get_taxon_fields,
    query_taxa,
    query_taxon,
)


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    See https://github.com/mikeshardmind/SinbadCogs/blob/v3/rolemanagement/core.py
    """

    pass  # pylint: disable=unnecessary-pass


class INatCog(INatEmbeds, commands.Cog, metaclass=CompositeMetaClass):
    """An iNaturalist commands cog."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1607)
        # TODO: generalize & make configurable
        self.config.register_guild(
            project_emojis={33276: "<:discord:638537174048047106>", 15232: ":poop:"}
        )
        super().__init__()

    @commands.group()
    async def inat(self, ctx):
        """Access the iNat platform."""
        pass  # pylint: disable=unnecessary-pass

    @inat.command()
    async def last(self, ctx, kind, display=None):
        """Lookup iNat links contained in recent messages.

        `[p]inat last observation`
        `[p]inat last obs`
        > Displays a summary of the last mentioned observation.
        `[p]inat last obs map`
        `[p]inat last obs m`
        > Displays the map for the last mentioned observation.
        `[p]inat last obs taxon`
        `[p]inat last obs t`
        > Displays the taxon for last mentioned observation.

        Also, `[p]last` is an alias for `[p]inat last`, *provided the bot owner has added it*.
        """

        if kind in ("obs", "observation"):
            try:
                msgs = await ctx.history(limit=1000).flatten()
                last = get_last_obs_msg(msgs)
            except StopIteration:
                await ctx.send(embed=sorry(apology="Nothing found"))
                return None
        else:
            await ctx.send_help()
            return

        if display:
            if display in ("t", "taxon"):
                if last and last.obs and last.obs.taxon:
                    await ctx.send(embed=self.make_taxa_embed(last.obs.taxon))
            elif display in ("m", "map"):
                if last and last.obs and last.obs.taxon:
                    await ctx.send(embed=self.make_map_embed([last.obs.taxon]))
            elif display in RANK_KEYWORDS:
                rank = RANK_EQUIVALENTS.get(display) or display
                if last.obs.taxon.rank == rank:
                    await ctx.send(embed=self.make_taxa_embed(last.obs.taxon))
                    return
                if last.obs.taxon:
                    full_record = get_taxon_fields(
                        get_taxa(last.obs.taxon.taxon_id)["results"][0]
                    )
                    ancestor = get_taxon_ancestor(full_record, display)
                    if ancestor:
                        await ctx.send(embed=self.make_taxa_embed(ancestor))
                    else:
                        await ctx.send(
                            embed=sorry(
                                apology=f"The last observation has no {rank} ancestor."
                            )
                        )
                else:
                    await ctx.send(
                        embed=sorry(apology="The last observation has no taxon.")
                    )
            else:
                await ctx.send_help()
                return
        else:
            # By default, display the observation embed for the matched last obs.
            await ctx.send(embed=await self.make_last_obs_embed(ctx, last))
            if last and last.obs and last.obs.sound:
                await self.maybe_send_sound_url(ctx, last.obs.sound)

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
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            url = mat["url"]

            results = get_observations(obs_id, include_new_projects=True)["results"]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(ctx, obs, url))
            if obs.sound:
                await self.maybe_send_sound_url(ctx, obs.sound)
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

        await ctx.send(embed=self.make_map_embed(taxa))

    @inat.command()
    async def obs(self, ctx, *, query):
        """Look up an iNat observation and summarize its contents in an embed.

        e.g.
        ```
        [p]inat obs #
           -> an embed summarizing the numbered observation
        [p]inat obs https://inaturalist.org/observations/#
           -> an embed summarizing the observation link (minus the preview,
              which Discord provides itself)
        ```
        """
        mat = re.search(PAT_OBS_LINK, query)
        obs = url = obs_id = None
        if mat:
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)

        try:
            obs_id = int(query)
        except ValueError:
            pass
        if obs_id:
            results = get_observations(obs_id, include_new_projects=True)["results"]
            obs = get_obs_fields(results[0]) if results else None
        if not url:
            url = WWW_BASE_URL + "/observations/" + str(obs_id)

        if obs_id:
            await ctx.send(
                embed=await self.make_obs_embed(ctx, obs, url, preview=False)
            )
            if obs.sound:
                await self.maybe_send_sound_url(ctx, obs.sound)
            return

        await ctx.send(embed=sorry())
        return

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

        await ctx.send(embed=self.make_taxa_embed(taxon))
