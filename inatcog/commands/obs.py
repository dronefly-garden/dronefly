"""Module for obs command group."""
import re
from collections import namedtuple
from contextlib import asynccontextmanager
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
from ..embeds.inat import INatEmbed, INatEmbeds
from ..interfaces import MixinMeta
from ..obs import get_obs_fields, get_formatted_user_counts, maybe_match_obs
from ..taxa import TAXON_COUNTS_HEADER
from ..utils import get_home, obs_url_from_v1

ObsResult = namedtuple("Singleobs", "obs url preview")


class CommandsObs(INatEmbeds, MixinMeta):
    """Mixin providing obs command group."""

    @asynccontextmanager
    async def _single_obs(self, ctx, query):
        """Return a single observation, its URL, and whether to preview it.

        Image preview is only desired if it wasn't already auto-previewed
        by Discord itself (i.e. the user pasted a URL).
        """
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
                    yield ObsResult(obs, url, False)
                    return
                else:
                    await apologize(ctx, "I don't understand")
                    yield
                    return

        try:
            ref = ctx.message.reference
            if ref:
                # It's a reply. Try to get an observation from the message.
                # TODO: Lifted from TaxonReplyConverter; don't know where this belongs yet.
                msg = ref.cached_message
                if not msg:
                    if (
                        ctx.guild
                        and not ctx.channel.permissions_for(
                            ctx.guild.me
                        ).read_message_history
                    ):
                        raise LookupError(
                            "I need Read Message History permission to read that message."
                        )
                    msg = await ctx.channel.fetch_message(ref.message_id)
                if msg and msg.embeds:
                    inat_embed = INatEmbed.from_discord_embed(msg.embeds[0])
                    # pylint: disable=no-member, assigning-non-slot
                    # - See https://github.com/PyCQA/pylint/issues/981
                    # Replying to observation display:
                    if inat_embed.obs_url:
                        mat = re.search(PAT_OBS_LINK, inat_embed.obs_url)
                        # Try to get single observation for the display:
                        if mat and mat["url"]:
                            obs, url = await maybe_match_obs(
                                self, ctx, inat_embed.obs_url, id_permitted=False
                            )
                            if url:
                                yield ObsResult(obs, url, False)
                                return
            # Otherwise try to get other usable info from reply
            # to make a new observation query.
            _query = await TaxonReplyConverter.convert(ctx, query)
            obs = await self.obs_query.query_single_obs(ctx, _query)
        except EmptyArgument:
            await ctx.send_help()
            yield
            return
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            yield
            return

        url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
        yield ObsResult(obs, url, True)

    @commands.group(invoke_without_command=True, aliases=["observation"])
    @checks.bot_has_permissions(embed_links=True)
    async def obs(self, ctx, *, query: Optional[str] = ""):
        """Observation matching query, link, or number.

        - See `[p]help query` and `[p]help taxon_query` for help with *query* terms.
        - Use `[p]search obs` to find more than one observation.
        - Normally just pasting a *link* will suffice in a channel where *autoobs* is on. See `[p]help autoobs` for details.
        """  # noqa: E501
        async with self._single_obs(ctx, query) as res:
            if res:
                embed = await self.make_obs_embed(
                    ctx, res.obs, res.url, preview=res.preview
                )
                await self.send_obs_embed(ctx, embed, res.obs)

    @obs.command(name="img", aliases=["image", "photo"])
    @checks.bot_has_permissions(embed_links=True)
    async def obs_img(self, ctx, number: Optional[int], *, query: Optional[str] = ""):
        """Image for observation.

        - Shows the image indicated by `number`, or if number is omitted, the first image.
        - Command may be a *Reply* to an observation display instead of a query.
        - See `[p]help query` and `[p]help taxon_query` for help with *query* terms.
        """  # noqa: E501
        async with self._single_obs(ctx, query) as res:
            if res:
                embed = await self.make_obs_embed(
                    ctx, res.obs, res.url, preview=number or 1
                )
                await self.send_obs_embed(ctx, embed, res.obs)

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
            return await self.add_obs_reaction_emojis(ctx, msg, query_response)
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
        def format_pages(user_links, users_count, entity_counted, view):
            pages = []
            pages_len = int((len(user_links) - 1) / 10) + 1
            for page, links in enumerate(grouper(user_links, 10), start=1):
                header = "**{} top {}{}{}**".format(
                    "First 500" if users_count > 500 else users_count,
                    entity_counted,
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
            # We count identifications when we tabulate identifiers, but link
            # to the observations tab on the web to show the observations
            # they identified, as there's no tidy way to link directly
            # to the identifications instead.
            if view == "ids":
                obs_opt_view = "observations"
            users_count = users.get("total_results")
            if not users_count:
                raise LookupError(
                    f"No observations found {query_response.obs_query_description()}"
                )
        except (BadArgument, LookupError) as err:
            await apologize(ctx, str(err))
            return

        obs_opt["view"] = obs_opt_view
        url = obs_url_from_v1(obs_opt)
        taxon = query_response.taxon
        species_only = taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]
        user_links = get_formatted_user_counts(users, url, species_only, view)
        query_description = query_response.obs_query_description()
        if view == "ids":
            entity_counted = "identifiers"
        else:
            entity_counted = obs_opt_view
        full_title = f"{entity_counted.capitalize()} {query_description}"
        pages = format_pages(user_links, users_count, entity_counted, view)

        summary_counts = await self.summarize_obs_spp_counts(taxon, obs_opt)
        embeds = [
            make_embed(
                title=full_title, url=url, description=f"{summary_counts}\n{page}"
            )
            for page in pages
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

            home = await get_home(ctx)
            results = (
                await self.api.get_observations(
                    obs_id, include_new_projects=1, preferred_place_id=home
                )
            )["results"]
            obs = get_obs_fields(results[0]) if results else None
            embed = await self.make_obs_embed(ctx, obs, url)
            await self.send_obs_embed(ctx, embed, obs)
            return

        mat = re.search(PAT_TAXON_LINK, query)
        if mat:
            query = await NaturalQueryConverter.convert(ctx, mat["taxon_id"])
            await (self.bot.get_command("taxon")(ctx, query=query))
            return

        await apologize(ctx)
