"""Module for search command group."""

from math import ceil
import re
from typing import Optional, Union
import urllib.parse

from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.parsers.url import (
    PAT_PLACE_LINK,
    PAT_PROJECT_LINK,
    PAT_TAXON_LINK,
    PAT_USER_LINK,
)
from dronefly.core.query.query import Query
from dronefly.discord.embeds import make_embed
from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..common import grouper
from ..converters.base import NaturalQueryConverter
from ..converters.reply import TaxonReplyConverter
from ..embeds.common import apologize
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..utils import use_client


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

        async def _display_selected(ctx, result):
            mat = re.search(PAT_TAXON_LINK, result)
            if mat:
                query = await NaturalQueryConverter.convert(ctx, mat["taxon_id"])
                try:
                    query_response = await self.query.get(ctx, query)
                except LookupError as err:
                    await apologize(ctx, str(err))
                    return
                await self.bot.get_command("taxon")(
                    ctx, query=str(query_response.taxon.id)
                )
                return
            mat = re.search(PAT_USER_LINK, result)
            if mat:
                await ctx.send(
                    f"{WWW_BASE_URL}/people/{mat['user_id'] or mat['login']}"
                )
                return
            mat = re.search(PAT_PROJECT_LINK, result)
            if mat:
                await self.bot.get_command("project")(ctx, query=mat["project_id"])
                return
            mat = re.search(PAT_PLACE_LINK, result)
            if mat:
                await self.bot.get_command("place")(ctx, query=mat["place_id"])

        async def display_selected_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):  # pylint: disable=too-many-arguments
            result = get_result(page, results, selected_index[0])
            if result:
                await _display_selected(ctx, result)
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
                    url, kwargs = get_inactive_query_args(query)
                else:
                    kwargs["sources"] = kw_lowered
                    url += f"&sources={keyword}"
            return (kw_lowered, query_title, url, kwargs)

        async def query_formatted_results(query, kwargs):
            thumbnails = []
            results, total_results, per_api_page = await self.site_search.search(
                ctx, query, **kwargs
            )
            per_embed_page = 10
            return (total_results, results, thumbnails, per_api_page, per_embed_page)

        def get_button_controls(results):
            all_buttons = [
                "\U0001f1e6",  # :regional_indicator_a:
                "\U0001f1e7",  # :regional_indicator_b:
                "\U0001f1e8",  # :regional_indicator_c:
                "\U0001f1e9",  # :regional_indicator_d:
                "\U0001f1ea",  # :regional_indicator_e:
                "\U0001f1eb",  # :regional_indicator_f:
                "\U0001f1ec",  # :regional_indicator_g:
                "\U0001f1ed",  # :regional_indicator_h:
                "\U0001f1ee",  # :regional_indicator_i:
                "\U0001f1ef",  # :regional_indicator_j:
            ][:per_embed_page]
            buttons_count = min(len(results), len(all_buttons))
            buttons = all_buttons[:buttons_count]
            controls = DEFAULT_CONTROLS.copy()
            letter_button_reaction = update_and_display_selected_reaction
            for button in buttons:
                controls[button] = letter_button_reaction
            return (buttons, controls)

        def format_page(buttons, group, selected=0):
            def text_style(i):
                if query_type != "obs":
                    return ""

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
                _query = query
                query_type, query_title, url, kwargs = await get_query_args(
                    _query, keyword
                )
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
                buttons, controls = get_button_controls(results)
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

    @commands.group(
        aliases=["s"], invoke_without_command=True
    )  # deprecated ,search group
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
        await self.bot.get_command("obs search")(ctx, query=query)

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

        **1.** Use the arrow buttons and menu to select a specific observation.
        **2.** *Reply* to the menu with [p]obs to show just the selected observation.
        **3.** You can continue to select and show other observations until the menu times out.
        """
        await self.bot.get_command("obs search")(ctx, query=query)
