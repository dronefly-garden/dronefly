"""Module for obs command group."""

import re
from typing import Optional
import urllib.parse

from redbot.core import checks, commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from inatcog.base_classes import PAT_OBS_LINK, RANK_LEVELS, WWW_BASE_URL
from inatcog.common import grouper, LOG
from inatcog.converters import MemberConverter, NaturalQueryConverter
from inatcog.embeds.embeds import apologize, make_embed
from inatcog.embeds.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.obs import get_obs_fields, get_formatted_user_counts, maybe_match_obs
from inatcog.taxa import PAT_TAXON_LINK, TAXON_COUNTS_HEADER


class CommandsObs(INatEmbeds, MixinMeta):
    """Mixin providing obs command group."""

    @commands.group(invoke_without_command=True, aliases=["observation"])
    @checks.bot_has_permissions(embed_links=True)
    async def obs(self, ctx, *, query_str: str):
        """Observation matching query, link, or number.

        **query** may contain:
        - `by [name]` to match the named resgistered user (or `me`)
        - `from [place]` to match the named place
        - `with [term] [value]` to matched the controlled term with the
          given value
        **Examples:**
        ```
        [p]obs by benarmstrong
           -> most recently added observation by benarmstrong
        [p]obs insecta by benarmstrong
           -> most recent insecta by benarmstrong
        [p]obs insecta from canada
           -> most recent insecta from Canada
        [p]obs insecta with life larva
           -> most recent insecta with life stage = larva
        [p]obs https://inaturalist.org/observations/#
           -> display the linked observation
        [p]obs #
           -> display the observation for id #
        ```
        - Use `[p]search obs` to find more than one observation.
        - See `[p]help taxon` for help specifying optional taxa.
        """

        id_or_link = None
        if query_str.isnumeric():
            id_or_link = query_str
        else:
            mat = re.search(PAT_OBS_LINK, query_str)
            if mat and mat["url"]:
                id_or_link = query_str
        if id_or_link:
            obs, url = await maybe_match_obs(self, ctx, id_or_link, id_permitted=True)
            # Note: if the user specified an invalid or deleted id, a url is still
            # produced (i.e. should 404).
            if url:
                await ctx.send(embed=await self.make_obs_embed(obs, url, preview=False))
                if obs and obs.sounds:
                    await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
                return
            else:
                await apologize(ctx, "I don't understand")
                return

        try:
            query = await NaturalQueryConverter.convert(ctx, query_str)
            obs = await self.obs_query.query_single_obs(ctx, query)
            LOG.info(obs)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

        url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
        await ctx.send(embed=await self.make_obs_embed(obs, url, preview=True))
        if obs and obs.sounds:
            await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])

    @commands.group(invoke_without_command=True, aliases=["tab"])
    @checks.bot_has_permissions(embed_links=True)
    async def tabulate(self, ctx, *, query: NaturalQueryConverter):
        """Tabulate iNaturalist data.

        • Only observations can be tabulated. More kinds of table
          to be supported in future releases.
        • The row contents can be `from` or `by`. If both
          are given, what to tabulate is filtered by the
          `from` place, and the `by` person is the first row.
        • If no taxon is specified, all observations are searched.
        • The `not by` qualifier counts observations / species
          unobserved by each user in the table. It may be combined
          with `from`, but not `by` or `id by`.
        • The `id by` qualifier counts observations / species
          identified by each user in the table. It may be combined
          with `from`, but not `by` or `not by`.
        e.g.
        ```
        ,tab fish from home
             -> per place (home listed; others react to add)
        ,tab fish by me
             -> per user (self listed; others react to add)
        ,tab fish not by me
             -> per unobserved by (self listed; others react to add)
        ,tab fish id by me
             -> per identified by (self listed; others react to add)
        ,tab fish from canada by me
             -> per user (self listed; others react to add)
                but only fish from canada are tabulated
        ```
        """
        try:
            query_response = await self.query.get(ctx, query)
            msg = await ctx.send(embed=await self.make_obs_counts_embed(query_response))
            self.add_obs_reaction_emojis(msg)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

    @tabulate.command(name="maverick")
    async def tabulate_maverick(self, ctx, *, query: Optional[NaturalQueryConverter]):
        """Maverick identifications.

        • By default, if your iNat login is known, your own maverick
          identifications are displayed.
        • The `by` qualifier can be used to display mavericks for
          another known user.
        """
        if query and (
            query.place
            or query.controlled_term
            or query.main
            or query.unobserved_by
            or query.id_by
            or query.per
            or query.project
        ):
            await apologize(ctx, "I can't tabulate that yet.")
            return
        try:
            query_user = None
            if query and query.user:
                query_user = query.user
            else:
                query_me = await NaturalQueryConverter.convert(ctx, "by me")
                query_user = query_me.user
            who = await MemberConverter.convert(ctx, query_user)
            user = await self.user_table.get_user(who.member)
            embed = make_embed()
            embed.title = f"Maverick identifications by {user.display_name()}"
            embed.url = (
                "https://www.inaturalist.org/identifications?category=maverick"
                f"&user_id={user.user_id}"
            )
            await ctx.send(embed=embed)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

    async def _tabulate_query(self, ctx, query, view="obs"):
        async def get_observer_options(ctx, query, view):
            query_response = await self.query.get(ctx, query)
            obs_opt = query_response.obs_args()
            full_title = view.capitalize()
            full_title += query_response.obs_query_description()
            taxon = query_response.taxon
            species_only = taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]
            return (query_response, obs_opt, full_title, species_only)

        try:
            obs_opt_view = "identifiers" if view == "ids" else "observers"
            (
                query_response,
                obs_opt,
                full_title,
                species_only,
            ) = await get_observer_options(ctx, query, obs_opt_view)
            users = await self.api.get_observations(obs_opt_view, **obs_opt)
            obs_opt["view"] = obs_opt_view
            users_count = users["total_results"]
            if not users_count:
                await apologize(
                    ctx,
                    f"No observations found {query_response.obs_query_description()}",
                )
                return

            by_species = " by species" if view == "spp" else ""
            if view == "ids":
                ids_opt = obs_opt.copy()
                del ids_opt["view"]
                # TODO: there are a bunch more observations parameters that could be deleted:
                # - they'll just be ignored on this page.
                url = (
                    f"{WWW_BASE_URL}/identifications?{urllib.parse.urlencode(ids_opt)}"
                )
            else:
                url = f"{WWW_BASE_URL}/observations?{urllib.parse.urlencode(obs_opt)}"
            user_links = get_formatted_user_counts(users, url, species_only, view)
            if users_count > 10:
                if users_count > 500:
                    first = "First "
                    users_count = 500
                else:
                    first = ""
                pages_len = int((len(user_links) - 1) / 10) + 1
                pages = []
                for page, links in enumerate(grouper(user_links, 10), start=1):
                    formatted_counts = "\n".join(filter(None, links))
                    total = (
                        f"**{first}{users_count} top {obs_opt['view']}{by_species}"
                        f" (page {page} of {pages_len}):**"
                    )
                    pages.append(f"{total}\n{TAXON_COUNTS_HEADER}\n{formatted_counts}")
                embeds = [
                    make_embed(title=full_title, url=url, description=page)
                    for page in pages
                ]
                await menu(ctx, embeds, DEFAULT_CONTROLS)
            else:
                formatted_counts = "\n".join(user_links)
                total = f"**{users_count} {obs_opt['view']}{by_species}:**"
                description = f"{total}\n{TAXON_COUNTS_HEADER}\n{formatted_counts}"
                embed = make_embed(title=full_title, url=url, description=description)
                await ctx.send(embed=embed)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

    @tabulate.command(name="topids")
    async def tabulate_top_identifiers(self, ctx, *, query: NaturalQueryConverter):
        """Top observations IDed per IDer (alias `[p]topids`)."""
        await self._tabulate_query(ctx, query, view="ids")
        return

    @commands.command(name="topids")
    async def top_identifiers(self, ctx, *, query: NaturalQueryConverter):
        """Top observations IDed per IDer (alias `[p]tab topids`)."""
        await self._tabulate_query(ctx, query, view="ids")
        return

    @tabulate.command(name="topobs")
    async def tabulate_top_observers(self, ctx, *, query: NaturalQueryConverter):
        """Top observations per observer (alias `[p]topobs`)."""
        await self._tabulate_query(ctx, query)
        return

    @commands.command(name="topobs")
    async def top_observers(self, ctx, *, query: NaturalQueryConverter):
        """Top observations per observer (alias `[p]tab topobs`)."""
        await self._tabulate_query(ctx, query)
        return

    @tabulate.command(name="topspp", alias=["topsp"])
    async def tabulate_top_species(self, ctx, *, query: NaturalQueryConverter):
        """Top species per observer (alias `[p]topspp`)."""
        await self._tabulate_query(ctx, query, view="spp")
        return

    @commands.command(name="topspp", alias=["topsp"])
    async def top_species(self, ctx, *, query: NaturalQueryConverter):
        """Top species per observer (alias `[p]tab topspp`)."""
        await self._tabulate_query(ctx, query, view="spp")
        return

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def link(self, ctx, *, query):
        """Summary for iNaturalist link.

        e.g.
        ```
        [p]link https://inaturalist.org/observations/#
           -> an embed summarizing the observation link
        ```
        """
        mat = re.search(PAT_OBS_LINK, query)
        if mat:
            obs_id = int(mat["obs_id"])
            url = mat["url"]

            home = await self.get_home(ctx)
            results = (
                await self.api.get_observations(
                    obs_id, include_new_projects=1, preferred_place_id=home
                )
            )["results"]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(obs, url))
            if obs and obs.sounds:
                await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
            return

        mat = re.search(PAT_TAXON_LINK, query)
        if mat:
            query = await NaturalQueryConverter.convert(ctx, mat["taxon_id"])
            await (self.bot.get_command("taxon")(ctx, query=query))
            return

        await apologize(ctx)
