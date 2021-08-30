"""Module for obs command group."""
import re
from typing import Optional
import urllib.parse

from redbot.core import checks, commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..base_classes import WWW_BASE_URL
from ..common import grouper
from ..converters.base import NaturalQueryConverter
from ..converters.reply import EmptyArgument, TaxonReplyConverter
from ..core.models.taxon import RANK_LEVELS
from ..core.parsers.url import PAT_OBS_LINK, PAT_TAXON_LINK
from ..embeds.common import apologize, make_embed
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..obs import get_obs_fields, get_formatted_user_counts, maybe_match_obs
from ..taxa import TAXON_COUNTS_HEADER


class CommandsObs(INatEmbeds, MixinMeta):
    """Mixin providing obs command group."""

    @commands.group(invoke_without_command=True, aliases=["observation"])
    @checks.bot_has_permissions(embed_links=True)
    async def obs(self, ctx, *, query: Optional[str] = ""):
        """Observation matching query, link, or number.

        - See `[p]help query` and `[p]help query_taxon` for help with *query* terms.
        - Use `[p]search obs` to find more than one observation.
        - Normally just pasting a *link* will suffice in a channel where *autoobs* is on. See `[p]help autoobs` for details.
        """  # noqa: E501

        if query:
            id_or_link = None
            if query.isnumeric():
                id_or_link = query
            else:
                mat = re.search(PAT_OBS_LINK, query)
                if mat and mat["url"]:
                    id_or_link = query
            if id_or_link:
                obs, url = await maybe_match_obs(
                    self, ctx, id_or_link, id_permitted=True
                )
                # Note: if the user specified an invalid or deleted id, a url is still
                # produced (i.e. should 404).
                if url:
                    embed = await self.make_obs_embed(obs, url, preview=False)
                    await self.send_obs_embed(ctx, embed, obs)
                    return
                else:
                    await apologize(ctx, "I don't understand")
                    return

        try:
            _query = await TaxonReplyConverter.convert(ctx, query)
            obs = await self.obs_query.query_single_obs(ctx, _query)
        except EmptyArgument:
            await ctx.send_help()
            return
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

        url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
        embed = await self.make_obs_embed(obs, url, preview=True)
        await self.send_obs_embed(ctx, embed, obs)

    @commands.group(invoke_without_command=True, aliases=["tab"])
    @checks.bot_has_permissions(embed_links=True)
    async def tabulate(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Tabulate iNaturalist data.

        • Only observations can be tabulated. More kinds of table to be supported in future releases.
        • The *per row* can be: `from`, `id by`, `not by`, or `by`, and breaks down the count of observations in the table topic into per name (of place or user) in the table.
        • When more than one eligible filter is given, the first in order in the list above, is the table topic, and the second in order above is the *per row* count.
        • All remaining filters beyond those, including any that can't be used as *per row* values, e.g. `in prj`, `rg`, etc. are applied to the table topic.
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
             -> per user (self listed; others react to add) but only fish from canada are tabulated
        ```
        """  # noqa: E501
        _query = query or await TaxonReplyConverter.convert(ctx, "")
        try:
            query_response = await self.query.get(ctx, _query)
            msg = await ctx.send(embed=await self.make_obs_counts_embed(query_response))
            await self.add_obs_reaction_emojis(ctx, msg, query_response)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

    @tabulate.command(name="maverick")
    async def tabulate_maverick(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Maverick identifications.

        • By default, if your iNat login is known, your own maverick identifications are displayed.
        • The `by` qualifier can be used to display mavericks for another known user.
        """
        try:
            _query = query or await TaxonReplyConverter.convert(ctx, "")
            if not _query.user:
                _query.user = "me"
            query_response = await self.query.get(ctx, _query)
            if not query_response.user:
                raise BadArgument("iNat user not found")
            if _query and (
                _query.place
                or _query.controlled_term
                or _query.unobserved_by
                or _query.id_by
                or _query.per
                or _query.project
            ):
                await apologize(ctx, "I can't tabulate that yet.")
                return
            embed = make_embed()
            embed.title = (
                f"Maverick identifications {query_response.obs_query_description()}"
            )
            ids_opt = {"category": "maverick", "user_id": query_response.user.user_id}
            if query_response.taxon:
                ids_opt["taxon_id"] = query_response.taxon.id
            embed.url = f"{WWW_BASE_URL}/identifications?" + urllib.parse.urlencode(
                ids_opt
            )
            await ctx.send(embed=embed)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

    async def _tabulate_query(self, ctx, query, view="obs"):
        def get_view_url(obs_opt, view):
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
            return url

        def format_pages(user_links, users_count, obs_opt, view):
            pages = []
            pages_len = int((len(user_links) - 1) / 10) + 1
            for page, links in enumerate(grouper(user_links, 10), start=1):
                header = "**{} top {}{}{}**".format(
                    "First 500" if users_count > 500 else users_count,
                    obs_opt["view"],
                    " by species" if view == "spp" else "",
                    f" (page {page} of {pages_len})" if pages_len > 1 else "",
                )
                page = "\n".join([header, TAXON_COUNTS_HEADER, *filter(None, links)])
                pages.append(page)
            return pages

        _query = query or await TaxonReplyConverter.convert(ctx, "")
        try:
            query_response = await self.query.get(ctx, _query)
            obs_opt_view = "identifiers" if view == "ids" else "observers"
            obs_opt = query_response.obs_args()
            users = await self.api.get_observations(obs_opt_view, **obs_opt)
            users_count = users.get("total_results")
            if not users_count:
                raise LookupError(
                    f"No observations found {query_response.obs_query_description()}"
                )
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

        obs_opt["view"] = obs_opt_view
        url = get_view_url(obs_opt, view)
        taxon = query_response.taxon
        species_only = taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]
        user_links = get_formatted_user_counts(users, url, species_only, view)
        full_title = "{} {}".format(
            obs_opt_view.capitalize(), query_response.obs_query_description()
        )
        pages = format_pages(user_links, users_count, obs_opt, view)

        embeds = [
            make_embed(title=full_title, url=url, description=page) for page in pages
        ]
        if len(pages) > 1:
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(embed=embeds[0])

    @tabulate.command(name="topids")
    async def tabulate_top_identifiers(
        self, ctx, *, query: Optional[TaxonReplyConverter]
    ):
        """Top observations IDed per IDer (alias `[p]topids`)."""
        await self._tabulate_query(ctx, query, view="ids")

    @commands.command(name="topids")
    async def top_identifiers(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Top observations IDed per IDer (alias `[p]tab topids`)."""
        await self._tabulate_query(ctx, query, view="ids")

    @tabulate.command(name="topobs")
    async def tabulate_top_observers(
        self, ctx, *, query: Optional[TaxonReplyConverter]
    ):
        """Top observations per observer (alias `[p]topobs`)."""
        await self._tabulate_query(ctx, query)

    @commands.command(name="topobs")
    async def top_observers(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Top observations per observer (alias `[p]tab topobs`)."""
        await self._tabulate_query(ctx, query)

    @tabulate.command(name="topspp", alias=["topsp"])
    async def tabulate_top_species(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Top species per observer (alias `[p]topspp`)."""
        await self._tabulate_query(ctx, query, view="spp")

    @commands.command(name="topspp", alias=["topsp"])
    async def top_species(self, ctx, *, query: Optional[TaxonReplyConverter]):
        """Top species per observer (alias `[p]tab topspp`)."""
        await self._tabulate_query(ctx, query, view="spp")

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def link(self, ctx, *, query):
        """Information and image from iNaturalist link.

        For observation displays, the default observation image is shown, if it has one.

        Enclose the link in angle brackets to suppress the automatic Discord preview of the image to avoid the image being shown twice.

        e.g.
        ```
        [p]link <https://inaturalist.org/observations/12345>
        ```

        See also `[p]help obs` and `[p]help autoobs`.
        - Both of those methods for showing link info do not include the image, relying instead on the Discord to preview the link.
        - If channel permissions don't allow users to preview links, but do allow the bot to, or if you prefer the information on top, you may find this command preferable.
        """  # noqa: E501
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
            embed = await self.make_obs_embed(obs, url)
            await self.send_obs_embed(ctx, embed, obs)
            return

        mat = re.search(PAT_TAXON_LINK, query)
        if mat:
            query = await NaturalQueryConverter.convert(ctx, mat["taxon_id"])
            await (self.bot.get_command("taxon")(ctx, query=query))
            return

        await apologize(ctx)
