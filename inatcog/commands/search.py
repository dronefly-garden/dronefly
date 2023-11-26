"""Module for search command group."""
from math import ceil
import re
from typing import Optional, Union
import urllib.parse

from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.formatters.generic import format_taxon_name
from dronefly.core.parsers.url import (
    PAT_OBS_LINK,
    PAT_PLACE_LINK,
    PAT_PROJECT_LINK,
    PAT_TAXON_LINK,
    PAT_USER_LINK,
)
from dronefly.core.query.query import EMPTY_QUERY, Query
from dronefly.core.utils import obs_url_from_v1
from dronefly.discord.embeds import make_embed
from pyinaturalist.models import Observation
from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..common import grouper
from ..converters.base import NaturalQueryConverter
from ..converters.reply import TaxonReplyConverter
from ..embeds.common import apologize
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..menus.inat import SearchMenuPages, SearchObsSource
from ..utils import get_home, use_client


class CommandsSearch(INatEmbeds, MixinMeta):
    """Mixin providing search command group."""

    async def _search(self, ctx, query: Union[Query, str], keyword: Optional[str]):
        async def cancel_timeout(
            ctx, pages, controls, message, page, _timeout, _reaction
        ):
            await menu(ctx, pages, controls, message, page, 0.1)

        def get_result(page, results, result_index):
            selected_result_offset = result_index + page * per_embed_page
            last_index = len(results) - 1
            if selected_result_offset > last_index:
                selected_result_offset = last_index
            return results[selected_result_offset]

        def get_thumbnail(page, thumbnails, result_index):
            selected_result_offset = result_index + page * per_embed_page
            last_index = len(results) - 1
            if selected_result_offset > last_index:
                selected_result_offset = last_index
            return thumbnails[selected_result_offset]

        def update_selected(pages, page, result_index):
            embed = pages[page]
            thumbnail = (
                get_thumbnail(page, thumbnails, result_index) if thumbnails else None
            )
            embed.set_image(url=thumbnail)
            results_page_start = page * per_embed_page
            results_page_end = results_page_start + per_embed_page
            page_of_results = results[results_page_start:results_page_end]
            last_index = len(page_of_results) - 1
            if result_index > last_index:
                result_index = last_index
            page = format_page(buttons, page_of_results, result_index)
            embed.description = page
            selected_index[0] = result_index
            return pages

        async def _display_selected(ctx, result):
            mat = re.search(PAT_OBS_LINK, result)
            if mat:
                home = await get_home(ctx)
                obs_results = None
                try:
                    obs_results = (
                        await self.api.get_observations(
                            mat["obs_id"],
                            include_new_projects=1,
                            preferred_place_id=home,
                        )
                    )["results"]
                except LookupError as err:
                    await apologize(ctx, str(err))
                    return
                obs = Observation.from_json(obs_results[0]) if obs_results else None
                if obs:
                    embed = await self.make_obs_embed(
                        ctx, obs, f"{WWW_BASE_URL}/observations/{obs.id}"
                    )
                    await self.send_obs_embed(
                        ctx, embed, obs, timeout=10, with_keep=True
                    )
                    return
                await apologize(ctx, "Not found")
                return
            mat = re.search(PAT_TAXON_LINK, result)
            if mat:
                query = await NaturalQueryConverter.convert(ctx, mat["taxon_id"])
                try:
                    query_response = await self.query.get(ctx, query)
                except LookupError as err:
                    await apologize(ctx, str(err))
                    return
                await self.send_embed_for_taxon(ctx, query_response, with_keep=True)
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

        async def next_page_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            pages = update_selected(pages, page, 0)
            await DEFAULT_CONTROLS["➡️"](
                ctx, pages, controls, message, page, timeout, reaction
            )

        async def prev_page_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            pages = update_selected(pages, page, 0)
            await DEFAULT_CONTROLS["⬅️"](
                ctx, pages, controls, message, page, timeout, reaction
            )

        async def prev_result_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            was_selected = selected_index[0]
            if was_selected == 0:
                # back to bottommost result on prev page:
                selected_index[0] = per_embed_page - 1
                target_page = (page - 1) % len(pages)
                pages = update_selected(pages, target_page, selected_index[0])
                if (
                    ctx.guild
                    and ctx.channel.permissions_for(ctx.guild.me).manage_messages
                ):
                    await message.remove_reaction(reaction, ctx.author)
                prev_reaction = DEFAULT_CONTROLS["⬅️"]
            else:
                selected_index[0] -= 1
                prev_reaction = update_selected_reaction
            await prev_reaction(ctx, pages, controls, message, page, timeout, reaction)

        async def next_result_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            was_selected = selected_index[0]
            page_len = (
                per_embed_page
                if (page + 1) < len(pages)
                else len(results) - ((len(pages) - 1) * per_embed_page)
            )
            if was_selected == page_len - 1:
                next_reaction = next_page_reaction
            else:
                selected_index[0] += 1
                pages = update_selected(pages, page, selected_index[0])
                next_reaction = update_selected_reaction
            await next_reaction(ctx, pages, controls, message, page, timeout, reaction)

        async def display_selected_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            result = get_result(page, results, selected_index[0])
            if result:
                await _display_selected(ctx, result)
            if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await message.remove_reaction(reaction, ctx.author)
            await menu(ctx, pages, controls, message, page, timeout)

        async def update_selected_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            result_index = selected_index[0]
            result = get_result(page, results, result_index)
            if result:
                pages = update_selected(pages, page, result_index)
            if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await message.remove_reaction(reaction, ctx.author)
            await menu(ctx, pages, controls, message, page, timeout)

        async def update_and_display_selected_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            selected_index[0] = buttons.index(reaction)
            await display_selected_reaction(
                ctx, pages, controls, message, page, timeout, reaction
            )

        async def select_result_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            result_index = buttons.index(reaction)
            result = get_result(page, results, result_index)
            if result:
                pages = update_selected(pages, page, result_index)
            if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await message.remove_reaction(reaction, ctx.author)
            await menu(ctx, pages, controls, message, page, timeout)

        def make_search_embeds(
            query_title, page, thumbnails, index, per_embed_page, pages_len
        ):  # pylint: disable=too-many-arguments
            embed = make_embed(
                title=f"Search: {query_title} (page {index + 1} of {pages_len})",
                url=url,
                description=page,
            )
            try:
                thumbnail = thumbnails[index * per_embed_page]
                embed.set_image(url=thumbnail)
            except IndexError:
                pass
            return embed

        def get_inactive_query_args(query):
            kwargs = {}
            url = (
                f"{WWW_BASE_URL}/taxa/search?"
                f"q={urllib.parse.quote_plus(query)}"
                "&is_active=any&sources=inactive"
            )
            kwargs["is_active"] = "any"
            return (url, kwargs)

        async def get_obs_query_args(query):
            query_response = await self.query.get(ctx, query)
            kwargs = query_response.obs_args()
            # TODO: determine why we don't just use QueryResponse.obs_query_description
            # and either use it directly or otherwise share code instead of duplicating
            # most of it here.
            if query_response.taxon:
                query_title = format_taxon_name(query_response.taxon, with_term=True)
            else:
                query_title = "Observations"
            if query_response.user:
                query_title += f" by {query_response.user.login}"
            if query_response.unobserved_by:
                query_title += f" unobserved by {query_response.unobserved_by.login}"
            if query_response.id_by:
                query_title += f" identified by {query_response.id_by.login}"
            if query_response.except_by:
                query_title += f" except by {query_response.except_by.login}"
            if query_response.project:
                query_title += f" in {query_response.project.title}"
            if query_response.place:
                query_title += f" from {query_response.place.display_name}"
            url = obs_url_from_v1(kwargs)
            kwargs["per_page"] = 200
            return (query_title, url, kwargs)

        async def get_query_args(query, keyword):
            kwargs = {}
            kw_lowered = ""
            query_title = ""
            url = ""
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

        async def query_formatted_results(query, kwargs):
            thumbnails = []
            (results, total_results, per_api_page) = await self.site_search.search(
                ctx, query, **kwargs
            )
            per_embed_page = 10
            return (total_results, results, thumbnails, per_api_page, per_embed_page)

        def get_button_controls(results, query_type):
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
            if query_type == "obs":
                controls = {
                    "⬆️": prev_result_reaction,
                    "⬇️": next_result_reaction,
                    "⬅️": prev_page_reaction,
                    "➡️": next_page_reaction,
                    "✅": display_selected_reaction,
                    "❌": DEFAULT_CONTROLS["❌"],
                }
            else:
                controls = DEFAULT_CONTROLS.copy()
            letter_button_reaction = (
                select_result_reaction
                if query_type == "obs"
                else update_and_display_selected_reaction
            )
            for button in buttons:
                controls[button] = letter_button_reaction
            return (buttons, controls)

        def format_page(buttons, group, selected=0):
            def text_style(i):
                if query_type != "obs":
                    return ""

                return "**" if i == selected else ""

            def format_result(result, i):
                return " ".join((buttons[i], result))

            lines = [
                (text_style(i) + format_result(result, i) + text_style(i))
                for i, result in enumerate(filter(None, group), 0)
            ]
            page = "\n".join(lines)
            return page

        def format_embeds(
            results, total_results, per_api_page, per_embed_page, buttons
        ):
            pages = []
            for group in grouper(results, per_embed_page):
                page = format_page(buttons, group)
                pages.append(page)

            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            if len(results) < total_results:
                pages_len = (
                    f"{pages_len}; "
                    f"{ceil((total_results - per_api_page)/per_embed_page)} more not shown"
                )
            embeds = [
                make_search_embeds(
                    query_title, page, thumbnails, index, per_embed_page, pages_len
                )
                for index, page in enumerate(pages, start=0)
            ]
            return embeds

        error_msg = None
        pages = []
        embeds = []
        controls = []
        async with ctx.typing():
            try:
                if keyword and keyword.lower() == "obs":
                    try:
                        _query = query or (await TaxonReplyConverter.convert(ctx, ""))
                    except commands.BadArgument:
                        _query = EMPTY_QUERY
                else:
                    _query = query
                query_type, query_title, url, kwargs = await get_query_args(
                    _query, keyword
                )
                if query_type == "obs":
                    (
                        results,
                        total_results,
                        per_api_page,
                    ) = await self.obs_query.query_observations(ctx, _query)
                else:
                    (
                        total_results,
                        results,
                        thumbnails,
                        per_api_page,
                        per_embed_page,
                    ) = await query_formatted_results(_query, kwargs)
                if not results:
                    if isinstance(_query, str) and "in" in _query.split():
                        raise LookupError(
                            "The `in` keyword is not supported by this command.\n"
                            f"Try `{ctx.clean_prefix}taxon` instead or omit the `in` clause.\n"
                            f"Type `{ctx.clean_prefix}help search` for help.",
                        )
                    else:
                        raise LookupError(
                            "Nothing matches that query. "
                            "Check for mistakes in spelling or syntax.\n"
                            f"Type `{ctx.clean_prefix}help search` for help.",
                        )
                if query_type == "obs":
                    per_page = 4
                    pages = SearchMenuPages(
                        source=SearchObsSource(
                            self,
                            ctx,
                            _query,
                            results,
                            total_results,
                            per_page,
                            per_api_page,
                            url,
                            query_title,
                        ),
                        clear_reactions_after=True,
                    )
                else:
                    (buttons, controls) = get_button_controls(results, query_type)
                    embeds = format_embeds(
                        results, total_results, per_api_page, per_embed_page, buttons
                    )

            except LookupError as err:
                error_msg = str(err)

        if error_msg:
            await apologize(ctx, error_msg)
        elif pages:
            await pages.start(ctx)
        else:
            # Track index in outer scope
            # - TODO: use a menu class (from vendored menu) and make this an attribute.
            selected_index = [0]
            await menu(ctx, embeds, controls, timeout=60)

    @commands.group(aliases=["s"], invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True, read_message_history=True)
    @use_client
    async def search(self, ctx, *, query: Optional[TaxonReplyConverter] = None):
        """Search iNat observations, taxa, places, projects.

        • Observations are searched by default.
        • Use the arrow reaction buttons to navigate through pages.
        • Press a lettered reaction button to display the result in more
          detail.
        • See subcommand help topics for more information on each kind
          of result, e.g. `[p]help search taxa` describes taxa results,
          whether from `[p]search` or `[p]search taxa`.
        """
        await (self.bot.get_command("search obs")(ctx, query=query))

    @search.command(name="site")
    @checks.bot_has_permissions(embed_links=True)
    @use_client
    async def search_site(self, ctx, *, query):
        """Search iNat.

        • The results are similar to entering a query in the `Search`
          textbox on the website, matching taxa, places, projects, or users.
        • Use one of the subcommands to match one kind of result, up to 100
          results instead of 30.
        • Matching a taxon within another taxon via `in` is only supported
          in `[p]search obs` and not in `[p]search site` or other subcommands.
          Use `[p]t` with `in` to match a single taxon within another taxon
          instead.
        """
        await self._search(ctx, query, None)

    @search.command(name="places", aliases=["place"])
    @use_client
    async def search_places(self, ctx, *, query):
        """Search iNat places.

        • The results are similar to entering a query in the website's `Search`
          textbox, then clicking the `Places` tab.
        • Place matches are indicated with the :round_pushpin: emoji to
          distinguish places from other kinds of `[p]search` result.
        """
        await self._search(ctx, query, "places")

    @search.command(name="projects", aliases=["prj", "project"])
    @use_client
    async def search_projects(self, ctx, *, query):
        """Search iNat projects.

        • The results are similar to entering a query into the website's `Search`
          textbox, then clicking the `Projects` tab.
        • Project matches are indicated with the :briefcase: emoji to
          distinguish projects from other kinds of `[p]search` result.
        """
        await self._search(ctx, query, "projects")

    @search.command(name="taxa", aliases=["taxon"])
    @use_client
    async def search_taxa(self, ctx, *, query):
        """Search iNat taxa.

        • The results are similar to entering a query into the website's `Search`
          textbox, then clicking the `Taxa` tab.
        • Taxa matches are indicated with :green_circle: emoji to distinguish
          taxa from other kinds of `[p]search` result.
        • *Note: If you need `in` to find a matching taxon within another taxon,
          or want to list user/place stats with `from` or `by`, use `[p]taxon`.*
        """
        await self._search(ctx, query, "taxa")

    @search.command(name="inactive")
    @use_client
    async def search_inactive(self, ctx, *, query):
        """Search iNat taxa (includes inactive).

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
    @use_client
    async def search_users(self, ctx, *, query):
        """Search iNat users.

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
    @use_client
    async def search_obs(self, ctx, *, query: Optional[TaxonReplyConverter] = None):
        """Search iNat observations.

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
