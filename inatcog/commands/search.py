"""Module for search command group."""

from math import ceil
import re
from typing import Optional
import urllib.parse

from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from inatcog.common import grouper
from inatcog.converters import NaturalCompoundQueryConverter
from inatcog.places import PAT_PLACE_LINK
from inatcog.projects import PAT_PROJECT_LINK
from inatcog.taxa import format_taxon_name, PAT_TAXON_LINK
from inatcog.users import PAT_USER_LINK

from inatcog.base_classes import (
    PAT_OBS_LINK,
    WWW_BASE_URL,
)
from inatcog.embeds import apologize, make_embed
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.obs import get_obs_fields


class CommandsSearch(INatEmbeds, MixinMeta):
    """Mixin providing search command group."""

    async def _search(self, ctx, query, keyword: Optional[str]):
        async def cancel_timeout(
            ctx, pages, controls, message, page, _timeout, _reaction
        ):
            await menu(ctx, pages, controls, message, page, 0.1)

        async def display_selected(result):
            mat = re.search(PAT_OBS_LINK, result)
            if mat:
                home = await self.get_home(ctx)
                results = (
                    await self.api.get_observations(
                        mat["obs_id"], include_new_projects=1, preferred_place_id=home
                    )
                )["results"]
                obs = get_obs_fields(results[0]) if results else None
                if obs:
                    embed = await self.make_obs_embed(
                        ctx.guild, obs, f"{WWW_BASE_URL}/observations/{obs.obs_id}"
                    )
                    if obs and obs.sounds:
                        await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
                    controls = {"❌": DEFAULT_CONTROLS["❌"], "✅": cancel_timeout}
                    await menu(ctx, [embed], controls)
                    return
                await apologize(ctx, "Not found")
                return
            mat = re.search(PAT_TAXON_LINK, result)
            if mat:
                query = await NaturalCompoundQueryConverter.convert(
                    ctx, mat["taxon_id"]
                )
                await (self.bot.get_command("taxon")(ctx, query=query))
                return
            mat = re.search(PAT_USER_LINK, result)
            if mat:
                await ctx.send(
                    f"{WWW_BASE_URL}/people/{mat['user_id'] or mat['login']}"
                )
                return
            mat = re.search(PAT_PROJECT_LINK, result)
            if mat:
                await (self.bot.get_command("project")(ctx, query=mat["project_id"]))
                return
            mat = re.search(PAT_PLACE_LINK, result)
            if mat:
                await (self.bot.get_command("place")(ctx, query=mat["place_id"]))

        async def select_result_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            number = buttons.index(reaction)
            selected_result_offset = number + page * per_embed_page
            if selected_result_offset > len(results) - 1:
                return
            result = results[number + page * per_embed_page]
            await display_selected(result)
            await menu(ctx, pages, controls, message, page, timeout)

        def make_search_embed(
            query_title, page, thumbnails, index, per_embed_page, pages_len
        ):  # pylint: disable=too-many-arguments
            embed = make_embed(
                title=f"Search: {query_title} (page {index + 1} of {pages_len})",
                url=url,
                description=page,
            )
            try:
                thumbnail = thumbnails[index * per_embed_page]
                embed.set_thumbnail(url=thumbnail)
            except IndexError:
                pass
            return embed

        def get_inactive_query_args(query):
            kwargs = {}
            url = f"{WWW_BASE_URL}/taxa/search?q={urllib.parse.quote_plus(query)}"
            url += f"&sources={keyword}"
            kwargs["is_active"] = "any"
            return (url, kwargs)

        async def get_obs_query_args(query):
            (
                kwargs,
                filtered_taxon,
                _term,
                _value,
            ) = await self.obs_query.get_query_args(ctx, query)
            if filtered_taxon.taxon:
                query_title = format_taxon_name(filtered_taxon.taxon, with_term=True)
            else:
                query_title = "Observations"
            if filtered_taxon.user:
                query_title += f" by {filtered_taxon.user.login}"
            if filtered_taxon.unobserved_by:
                query_title += f" unobserved by {filtered_taxon.unobserved_by.login}"
            if filtered_taxon.id_by:
                query_title += f" identified by {filtered_taxon.id_by.login}"
            if filtered_taxon.place:
                query_title += f" from {filtered_taxon.place.display_name}"
            url = f"{WWW_BASE_URL}/observations?{urllib.parse.urlencode(kwargs)}"
            kwargs["per_page"] = 200
            return (query_title, url, kwargs)

        async def get_query_args(query):
            kwargs = {}
            kw_lowered = ""
            query_title = ""
            if isinstance(query, str):
                query_title = query
                url = f"{WWW_BASE_URL}/search?q={urllib.parse.quote_plus(query)}"
            if keyword:
                kw_lowered = keyword.lower()
                if kw_lowered == "inactive":
                    (url, kwargs) = get_inactive_query_args(query)
                elif kw_lowered == "obs":
                    (query_title, url, kwargs) = await get_obs_query_args(query)
                else:
                    kwargs["sources"] = kw_lowered
                    url += f"&sources={keyword}"
            return (kw_lowered, query_title, url, kwargs)

        async def query_formatted_results(query, query_type, kwargs):
            results = []
            thumbnails = []
            if query_type == "obs":
                (
                    observations,
                    total_results,
                    per_page,
                ) = await self.obs_query.query_observations(ctx, query)
                for obs in observations:
                    results.append(
                        " ".join(
                            await self.format_obs(
                                obs,
                                with_description=False,
                                with_link=True,
                                compact=True,
                            )
                        )
                    )
                    thumbnails.append(obs.thumbnail)
                per_embed_page = 4
            else:
                (results, total_results, per_page) = await self.site_search.search(
                    ctx, query, **kwargs
                )
                per_embed_page = 10
            return (total_results, results, thumbnails, per_page, per_embed_page)

        def get_button_controls(results):
            all_buttons = [
                "\U0001F1E6",  # :regional_indicator_a:
                "\U0001F1E7",  # :regional_indicator_b:
                "\U0001F1E8",  # :regional_indicator_c:
                "\U0001F1E9",  # :regional_indicator_d:
                "\U0001F1EA",  # :regional_indicator_e:
                "\U0001F1EB",  # :regional_indicator_f:
                "\U0001F1EC",  # :regional_indicator_g:
                "\U0001F1ED",  # :regional_indicator_h:
                "\U0001F1EE",  # :regional_indicator_i:
                "\U0001F1EF",  # :regional_indicator_j:
            ][:per_embed_page]
            buttons_count = min(len(results), len(all_buttons))
            buttons = all_buttons[:buttons_count]
            controls = DEFAULT_CONTROLS.copy()
            for button in buttons:
                controls[button] = select_result_reaction
            return (buttons, controls)

        def format_embeds(results, total_results, per_page, per_embed_page, buttons):
            pages = []
            for group in grouper(results, per_embed_page):
                lines = [
                    (
                        ("**" if i == 0 else "")
                        + " ".join((buttons[i], result))
                        + ("**" if i == 0 else "")
                    )
                    for i, result in enumerate(filter(None, group), 0)
                ]
                page = "\n".join(lines)
                pages.append(page)

            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            if len(results) < total_results:
                pages_len = (
                    f"{pages_len}; "
                    f"{ceil((total_results - per_page)/per_embed_page)} more not shown"
                )
            embeds = [
                make_search_embed(
                    query_title, page, thumbnails, index, per_embed_page, pages_len
                )
                for index, page in enumerate(pages, start=0)
            ]
            return embeds

        try:
            query_type, query_title, url, kwargs = await get_query_args(query)
        except LookupError as err:
            await apologize(ctx, err.args[0])
            return
        (
            total_results,
            results,
            thumbnails,
            per_page,
            per_embed_page,
        ) = await query_formatted_results(query, query_type, kwargs)
        if not results:
            await apologize(
                ctx,
                "Nothing matches that query. "
                "Check for mistakes in spelling or syntax.\n"
                f"Type `{ctx.clean_prefix}help search` for help.",
            )
            return

        (buttons, controls) = get_button_controls(results)
        embeds = format_embeds(
            results, total_results, per_page, per_embed_page, buttons
        )
        await menu(ctx, embeds, controls)

    @commands.group(aliases=["s"], invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    async def search(self, ctx, *, query):
        """Search iNat.

        `Aliases: [p]s`

        • The results are similar to entering a query in the `Search`
          textbox on the website, matching taxa, places, projects, or users.
        • Use one of the subcommands listed below to only match one kind of
          result, up to 100 results instead of 30.
        • Use the arrow reaction buttons to see more pages.
        • Press a lettered reaction button to display the result in more
          detail.
        • See subcommand help topics for more information on each kind
          of result, e.g. `[p]help search taxa` describes taxa results,
          whether from `[p] search` or `[p]search taxa`.
        """
        await self._search(ctx, query, None)

    @search.command(name="places", aliases=["place"])
    async def search_places(self, ctx, *, query):
        """Search iNat places.

        `Aliases: [p]search place, [p]s place`

        • The results are similar to entering a query in the website's `Search`
          textbox, then clicking the `Places` tab.
        • Place matches are indicated with the :round_pushpin: emoji to
          distinguish places from other kinds of `[p]search` result.
        """
        await self._search(ctx, query, "places")

    @search.command(name="projects", aliases=["project"])
    async def search_projects(self, ctx, *, query):
        """Search iNat projects.

        `Aliases: [p]search project, [p]s project`

        • The results are similar to entering a query into the website's `Search`
          textbox, then clicking the `Projects` tab.
        • Project matches are indicated with the :briefcase: emoji to
          distinguish projects from other kinds of `[p]search` result.
        """
        await self._search(ctx, query, "projects")

    @search.command(name="taxa", aliases=["taxon"])
    async def search_taxa(self, ctx, *, query):
        """Search iNat taxa.

        `Aliases: [p]search taxon, [p]s taxon`

        • The results are similar to entering a query into the website's `Search`
          textbox, then clicking the `Taxa` tab.
        • Taxa matches are indicated with :green_circle: emoji to distinguish
          taxa from other kinds of `[p]search` result.
        • *Note: If you need `in` to find a matching taxon within another taxon,
          or want to list user/place stats with `from` or `by`, use `[p]taxon`.*
        """
        await self._search(ctx, query, "taxa")

    @search.command(name="inactive")
    async def search_inactive(self, ctx, *, query):
        """Search iNat taxa (includes inactive).

        `Aliases: [p]s inactive`

        • The results are similar to entering a query into
          `More > Taxa Info > Search` textbox on the website,
          then clicking `Show active and inactive taxa`.
        • This subcommand can be used instead of `[p]search taxa` if you need
          to see more pages of results (up to 500 results instead of 100).
        • *Note: just as on the website, the search engine ranks the results
          differently from `[p]search taxa`, so you may find the order in
          which they are listed differs from that command.*
        """
        await self._search(ctx, query, "inactive")

    @search.command(name="users", aliases=["user", "person", "people"])
    async def search_users(self, ctx, *, query):
        """Search iNat users.

        `Aliases: [p]search user, [p]s user` (also `person` or `people`)

        • The results are similar to typing a query into the website's `Search`
          textbox, then clicking the `Users` tab.
        • User matches are indicated with :bust_in_silhouette: emoji to
          distinguish users from other kinds of `[p]search` result.

        • *Note: only iNat login IDs and names can be searched with this command.
        To find an iNat login ID for a registered Discord user, use the
        `[p]user` command instead. See `[p]help user` for more information.*
        """
        await self._search(ctx, query, "users")

    @search.command(name="obs", aliases=["observation", "observations"])
    async def search_obs(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Search iNat observations.

        `Aliases: [p]s obs`

        • Command operation is similar to `[p]obs`, except multiple results are
          returned; see `[p]help obs` for more details and examples.
        • The mechanic for selecting observations is slightly different from
          the main command and other subcommands:

        **1.** Use the lettered reaction buttons to select an observation.
        **2.** Use :white_check_mark: reaction on the selected observation to
          keep it or :x: reaction to dismiss it.
        **3.** Continue to select more observations if you wish. Once every
          observation is either kept or dismissed, then you can react with
          :x: on the search display to dismiss it.
        """
        await self._search(ctx, query, "obs")
