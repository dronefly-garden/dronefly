"""Module to access iNaturalist API."""
from io import BytesIO
import re
import aiohttp
from discord import File
from redbot.core import commands, Config
from pyparsing import ParseException
from .api import WWW_BASE_URL, get_observations, get_taxa
from .common import LOG
from .embeds import make_embed, sorry
from .inat_embeds import EMOJI, format_taxon_names_for_embed
from .last import get_last_obs_msg
from .maps import get_map_url_for_taxa
from .obs import get_obs_fields, PAT_OBS_LINK
from .taxa import (
    get_taxon_fields,
    format_taxon_name,
    format_taxon_names,
    query_taxa,
    query_taxon,
)


class INatCog(commands.Cog):
    """An iNaturalist commands cog."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1607)
        self.config.register_guild(project_emojis={15232: ":poop:"})

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
            obs_id = int(mat["obs_id"])
            url = mat["url"]

            results = get_observations(obs_id)["results"]
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
            obs_id = int(mat["obs_id"])
            url = mat["url"]

        try:
            obs_id = int(query)
        except ValueError:
            pass
        if obs_id:
            results = get_observations(obs_id)["results"]
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

    async def make_last_obs_embed(self, ctx, last):
        """Return embed for recent observation link."""
        if last.obs:
            obs = last.obs
            embed = await self.make_obs_embed(ctx, obs, url=last.url, preview=False)
        else:
            embed = make_embed(url=last.url)
            mat = re.search(PAT_OBS_LINK, last.url)
            obs_id = int(mat["obs_id"])
            LOG.info("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        embed.description = (
            f"{embed.description}\n\n· shared {last.ago} by @{last.name}"
        )
        return embed

    def make_map_embed(self, taxa):
        """Return embed for an observation link."""
        title = format_taxon_names_for_embed(
            taxa, with_term=True, names_format="Range map for %s"
        )
        url = get_map_url_for_taxa(taxa)
        return make_embed(title=title, url=url)

    async def maybe_send_sound_url(self, ctx, url):
        """Given a URL to a sound, send it if it can be retrieved."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                try:
                    sound = BytesIO(await response.read())
                except OSError:
                    sound = None
        if sound:
            await ctx.send(file=File(sound, filename=response.url.name))

    async def make_obs_embed(self, ctx, obs, url, preview=True):
        """Return embed for an observation link."""
        embed = make_embed(url=url)

        if obs:
            taxon = obs.taxon
            user = obs.user
            project_emojis = await self.config.guild(ctx.guild).project_emojis()
            if taxon:
                title = format_taxon_name(taxon)
            else:
                title = "Unknown"
            title += " " + EMOJI[obs.quality_grade]

            def format_count(label, count):
                return f", {EMOJI[label]}" + (str(count) if count > 1 else "")

            if obs.faves_count:
                title += format_count("fave", obs.faves_count)
            if obs.comments_count:
                title += format_count("comment", obs.comments_count)
            if preview and obs.thumbnail:
                embed.set_image(url=re.sub("/square", "/large", obs.thumbnail))
            summary = "Observed by " + user.profile_link()
            if obs.obs_on:
                summary += " on " + obs.obs_on
            if obs.obs_at:
                summary += " at " + obs.obs_at
            if obs.description:
                summary += "\n> %s\n" % obs.description.replace("\n", "\n> ")
            idents_count = ""
            if obs.idents_count:
                idents_count = (
                    f"{EMOJI['community']} ({obs.idents_agree}/{obs.idents_count})"
                )
            summary += f" [obs#: {obs.obs_id}]"
            if (
                obs.community_taxon
                and obs.community_taxon.taxon_id != obs.taxon.taxon_id
            ):
                summary = (
                    f"{format_taxon_name(obs.community_taxon)} {idents_count}\n\n"
                    + summary
                )
            else:
                title += " " + idents_count
            if project_emojis:
                for obs_id in obs.project_ids:
                    if obs_id in project_emojis:
                        title += project_emojis[obs_id]

            embed.title = title
            embed.description = summary
        else:
            mat = re.search(PAT_OBS_LINK, url)
            obs_id = int(mat["obs_id"])
            LOG.info("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        return embed

    def make_taxa_embed(self, rec):
        """Make embed describing taxa record."""
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}")

        title = format_taxon_name(rec)
        matched = rec.term
        if matched not in (rec.name, rec.common):
            title += f" ({matched})"

        observations = rec.observations
        url = get_map_url_for_taxa([rec])
        if url:
            observations = "[%d](%s)" % (observations, url)
        description = f"is a {rec.rank} with {observations} observations"

        full_record = get_taxa(rec.taxon_id)
        ancestors = [
            get_taxon_fields(ancestor)
            for ancestor in full_record["results"][0]["ancestors"]
        ]
        if ancestors:
            description += " in: " + format_taxon_names(ancestors, hierarchy=True)
        else:
            description += "."

        embed.title = title
        embed.description = description
        if rec.thumbnail:
            embed.set_thumbnail(url=rec.thumbnail)

        return embed
