"""iNat menus."""
import contextlib
from math import ceil, floor
import re
from typing import Any, Optional

import discord
from discord.ext import commands
from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.formatters.generic import LifeListFormatter
from dronefly.core.utils import lifelists_url_from_query_response
from redbot.vendored.discord.ext import menus
from pyinaturalist import Taxon
from pyinaturalist.constants import ROOT_TAXON_ID

from ..embeds.common import make_embed
from ..taxa import get_taxon

LETTER_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
MAX_LETTER_EMOJIS = 10
ENTRY_EMOJIS = [chr(ord(LETTER_A) + i) for i in range(0, MAX_LETTER_EMOJIS - 1)]
INAT_LOGO = "https://static.inaturalist.org/sites/1-logo_square.png"


class StopButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{HEAVY MULTIPLICATION X}\N{VARIATION SELECTOR-16}"

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        if interaction.message.flags.ephemeral:
            await interaction.response.edit_message(view=None)
            return
        await interaction.message.delete()


class ForwardButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_checked_page(self.view.current_page + 1, interaction)


class BackButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_checked_page(self.view.current_page - 1, interaction)


class LastItemButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"  # noqa: E501

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_page(self.view._source.get_max_pages() - 1, interaction)


class FirstItemButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"  # noqa: E501

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_page(0, interaction)


class PerRankButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{UP DOWN ARROW}"

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        formatter = view.source._life_list_formatter
        if formatter.per_rank == "leaf":
            per_rank = "main"
        elif formatter.per_rank == "main":
            per_rank = "any"
        elif formatter.per_rank == "any":
            current_taxon = view.select_taxon.taxon()
            if current_taxon:
                per_rank = current_taxon.rank
            else:
                per_rank = "main"
        else:
            per_rank = "main"
        await view.update_source(interaction, per_rank=per_rank)


class LeafButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{LEAF FLUTTERING IN WIND}"

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        formatter = view.source._life_list_formatter
        per_rank = "any" if formatter.per_rank == "leaf" else "leaf"
        await view.update_source(interaction, per_rank=per_rank)


class RootButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{TOP WITH UPWARDS ARROW ABOVE}"

    async def callback(self, interaction: discord.Interaction):
        await self.view.update_source(interaction, toggle_taxon_root=True)


class DirectButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{REGIONAL INDICATOR SYMBOL LETTER D}"

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        formatter = view.source._life_list_formatter
        await view.update_source(interaction, with_direct=not formatter.with_direct)


class CommonButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row)
        self.style = style
        self.emoji = "\N{REGIONAL INDICATOR SYMBOL LETTER C}"

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        formatter = view.source._life_list_formatter
        await view.update_source(interaction, with_common=not formatter.with_common)


class SelectTaxonOption(discord.SelectOption):
    def __init__(
        self,
        value: int,
        taxon: Taxon,
        default: int,
    ):
        super().__init__(label=taxon.full_name, value=str(value), default=default)


class SelectLifeListTaxon(discord.ui.Select):
    def __init__(
        self,
        view: discord.ui.View,
        placeholder: Optional[str] = "Select a taxon",
        selected: Optional[int] = 0,
    ):
        super().__init__(min_values=1, max_values=1, placeholder=placeholder)
        page = view.current_page
        formatter = view.source._life_list_formatter
        self.taxa = formatter.get_page_of_taxa(page)
        view.ctx.selected = selected
        for (value, taxon) in enumerate(self.taxa):
            self.append_option(
                SelectTaxonOption(value, taxon, default=(value == selected))
            )

    async def callback(self, interaction: discord.Interaction):
        self.view.ctx.selected = self.values[0]
        await self.view.update_source(interaction)

    def taxon(self):
        return self.taxa[int(self.view.ctx.selected)]


class BaseMenu(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        cog: commands.Cog,
        timeout: int = 60,
        message: discord.Message = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            timeout=timeout,
        )
        self.cog = cog
        self.bot = None
        self.message = message
        self._source = source
        self.ctx = None
        self.author: Optional[discord.Member] = None
        self.current_page = kwargs.get("page_start", 0)
        self.forward_button = ForwardButton(discord.ButtonStyle.grey, 0)
        self.back_button = BackButton(discord.ButtonStyle.grey, 0)
        self.first_item = FirstItemButton(discord.ButtonStyle.grey, 0)
        self.last_item = LastItemButton(discord.ButtonStyle.grey, 0)
        self.stop_button = StopButton(discord.ButtonStyle.red, 0)
        if isinstance(self._source, LifeListSource):
            # Late bind these as which buttons are shown depends on page content:
            self.leaf_button = None
            self.per_rank_button = None
            self.direct_button = None
            self.common_button = None
            self.select_taxon = None
            self.root_button = None
            self.root_taxon_id_stack = []
        self.add_item(self.stop_button)
        self.add_item(self.first_item)
        self.add_item(self.back_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_item)

    @property
    def source(self):
        return self._source

    async def on_timeout(self):
        await self.message.edit(view=None)

    async def start(self, ctx: commands.Context):
        ctx.selected = 0
        self.ctx = ctx
        self.bot = self.cog.bot
        self.author = ctx.author
        # await self.source._prepare_once()
        self.message = await self.send_initial_message(ctx)

    async def _get_kwargs_from_page(self, page):
        selected = None
        if isinstance(self.source, LifeListSource):
            selected = self.ctx.selected
        value = await discord.utils.maybe_coroutine(
            self._source.format_page, self, page, selected
        )
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}

    async def send_initial_message(self, ctx: commands.Context):
        """|coro|
        The default implementation of :meth:`Menu.send_initial_message`
        for the interactive pagination session.
        This implementation shows the first page of the source.
        """
        self.ctx = ctx
        source = self.source
        page = await source.get_page(self.current_page)
        kwargs = await self._get_kwargs_from_page(page)
        if isinstance(source, LifeListSource):
            # Source modifier buttons:
            self.leaf_button = LeafButton(discord.ButtonStyle.grey, 1)
            self.per_rank_button = PerRankButton(discord.ButtonStyle.grey, 1)
            self.root_button = RootButton(discord.ButtonStyle.grey, 1)
            self.direct_button = DirectButton(discord.ButtonStyle.grey, 1)
            self.add_item(self.leaf_button)
            self.add_item(self.per_rank_button)
            self.add_item(self.root_button)
            self.add_item(self.direct_button)
            if source._life_list_formatter.query_response.user:
                self.common_button = CommonButton(discord.ButtonStyle.grey, 1)
                self.add_item(self.common_button)
            self.select_taxon = SelectLifeListTaxon(view=self, selected=0)
            self.add_item(self.select_taxon)
        self.message = await ctx.send(**kwargs, view=self)
        return self.message

    async def show_page(
        self, page_number: int, interaction: discord.Interaction, selected: int = 0
    ):
        page = await self._source.get_page(page_number)
        self.current_page = page_number
        self.ctx.selected = selected
        kwargs = await self._get_kwargs_from_page(page)
        if isinstance(self._source, LifeListSource):
            self.remove_item(self.select_taxon)
            self.select_taxon = SelectLifeListTaxon(view=self, selected=selected)
            self.add_item(self.select_taxon)
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs, view=self)
        else:
            await interaction.response.edit_message(**kwargs, view=self)

    async def show_checked_page(
        self, page_number: int, interaction: discord.Interaction
    ) -> None:
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number, interaction)
            elif page_number >= max_pages:
                await self.show_page(0, interaction)
            elif page_number < 0:
                await self.show_page(max_pages - 1, interaction)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number, interaction)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to use owner_ids"""
        if interaction.user.id not in (
            *interaction.client.owner_ids,
            getattr(self.author, "id", None),
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        return True

    async def update_source(self, interaction: discord.Interaction, **formatter_kwargs):
        if isinstance(self.source, LifeListSource):
            await interaction.response.defer()
            formatter = self.source._life_list_formatter
            # Replace the source with a new source, preserving the currently
            # selected taxon
            per_rank = formatter_kwargs.get("per_rank") or formatter.per_rank
            with_direct = formatter_kwargs.get("with_direct")
            if with_direct is None:
                with_direct = formatter.with_direct
            with_common = formatter_kwargs.get("with_common")
            if with_common is None:
                with_common = formatter.with_common
            toggle_taxon_root = formatter_kwargs.get("toggle_taxon_root")
            per_page = formatter.per_page
            life_list = formatter.life_list
            query_response = formatter.query_response
            current_taxon = self.select_taxon.taxon()
            root_taxon_id = (
                self.root_taxon_id_stack[-1] if self.root_taxon_id_stack else None
            )
            if toggle_taxon_root:
                if current_taxon.id in self.root_taxon_id_stack:
                    self.root_taxon_id_stack.pop()
                    root_taxon_id = (
                        self.root_taxon_id_stack[-1]
                        if self.root_taxon_id_stack
                        else None
                    )
                else:
                    query_taxon = query_response.taxon
                    # If at the top of the stack, and a taxon was specified in
                    # the query, generate a new life list for its immediate
                    # ancestor.
                    if (
                        query_taxon
                        and query_taxon.id != ROOT_TAXON_ID
                        and not self.root_taxon_id_stack
                        and self.current_page == 0
                        and self.ctx.selected == 0
                    ):
                        if query_taxon.parent_id == ROOT_TAXON_ID:
                            # Simplify the request by removing the taxon filter
                            # if we hit the top (Life)
                            query_response.taxon = None
                        else:
                            query_response.taxon = await get_taxon(
                                self.ctx, query_taxon.parent_id
                            )
                        # And in either case, get a new life_list for the updated query response:
                        life_list = await self.ctx.inat_client.observations.life_list(
                            **query_response.obs_args()
                        )
                        # The first taxon on page 0 is selected:
                        root_taxon_id = None
                        current_taxon = None
                    else:
                        root_taxon_id = current_taxon.id
                        self.root_taxon_id_stack.append(root_taxon_id)
            # Replace the formatter; TODO: support updating existing formatter
            formatter = LifeListFormatter(
                life_list,
                per_rank,
                query_response,
                with_taxa=True,
                per_page=per_page,
                with_direct=with_direct,
                with_common=with_common,
                root_taxon_id=root_taxon_id,
            )
            self._life_list_formatter = formatter
            # Replace the source
            self._source = LifeListSource(formatter)
            # Find the current taxon
            if current_taxon:
                # Find the taxon or the first taxon that is a descendant of it (e.g.
                # "leaf" case may have dropped the taxon if was above all of the taxa
                # in the new display)
                taxon_index = next(
                    (
                        i
                        for i, taxon in enumerate(formatter.taxa)
                        if current_taxon.id == taxon.id
                        or current_taxon.id in (t.id for t in taxon.ancestors)
                    ),
                    None,
                )

                # Or the lowest ancestor of the taxon e.g. the "main" case may have
                # dropped the taxon if it was below all of the taxa in the new display
                if taxon_index is None:
                    ancestor_indices = reversed(
                        list(
                            i
                            for i, taxon in enumerate(formatter.taxa)
                            if taxon.id in (t.id for t in current_taxon.ancestors)
                        )
                    )
                    taxon_index = next(ancestor_indices, 0)

                # Show the page with the matched taxon on it
                page = floor(taxon_index / per_page)
                selected = taxon_index % per_page
            else:
                # Should never get here as we require the select to always have a value
                page = 0
                selected = 0
            await self.show_page(page, interaction, selected)


class LifeListSource(menus.ListPageSource):
    def __init__(self, life_list_formatter: LifeListFormatter):
        self._life_list_formatter = life_list_formatter
        query_response = self._life_list_formatter.query_response
        self._url = (
            lifelists_url_from_query_response(query_response)
            if query_response.user
            else None
        )
        pages = list(page for page in self._life_list_formatter.generate_pages())
        super().__init__(pages, per_page=1)

    def is_paginating(self):
        return True

    def format_page(self, menu: BaseMenu, page, selected: Optional[int] = None):
        formatter = self._life_list_formatter
        ctx = menu.ctx
        ctx.selected = selected
        query_response = formatter.query_response
        embed = make_embed(title=f"Life list {query_response.obs_query_description()}")
        if self._url:
            embed.url = self._url
        embed.description = formatter.format_page(menu.current_page, ctx.selected)
        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")
        return embed


# TODO: derive a base class from this that:
# - wraps a dronefly-core (pyinat-based) get method for the entity being paged
#   (obs, taxa, users, etc.)
# - featuring:
#   - page formatting w. current entry cursor highlighting
#   - single/default/max #entries modes
#   - preview image show/hide and single/multi modes
class SearchObsSource(menus.AsyncIteratorPageSource):
    """Paged (both UI & API) observation search results source."""

    async def generate_obs(self, observations):
        _observations = observations
        api_page = 1
        while _observations:
            for obs in _observations:
                yield obs
            if (api_page - 1) * self._per_api_page + len(
                _observations
            ) < self._total_results:
                api_page += 1
                # TODO: use dronefly-core (pyinat-based) get_observations
                # - top level should handle mapping dronefly query parts
                #   to iNat id#s to send to pyinat (`me`, Discord user mapping,
                #   place abbrevs, `home` place, user's `lang` setting, etc.)
                # - do pyinat at the lowest level to take advantage of
                #   caching, paginator, etc.
                # - eliminates reliance on computing our own API page
                _observations = await self._cog.obs_query.query_observations(
                    self._ctx, self._query, page=api_page
                )
            else:
                _observations = None

    def __init__(
        self,
        cog,
        ctx,
        query,
        observations,
        total_results,
        per_page,
        per_api_page,
        url,
        query_title,
    ):
        self._cog = cog
        self._ctx = ctx
        self._query = query
        self._total_results = total_results
        self._per_api_page = per_api_page
        self._url = url
        self._query_title = query_title
        self._single_entry = False
        self._multi_images = True
        self._show_images = True
        self._current_entry = 0
        super().__init__(self.generate_obs(observations), per_page=per_page)

    async def _format_obs(self, obs):
        # TODO: use core formatter for markdown-formatted individual observation
        formatted_obs = await self._cog.format_obs(
            self._ctx,
            obs,
            with_description=False,
            with_link=True,
            compact=True,
            with_user=not self._query.user,
        )
        return "".join(formatted_obs)

    def is_paginating(self):
        """Always paginate so non-paging buttons work."""
        return True

    async def format_page(self, menu, entries):
        # TODO: move out to core classes
        def get_image_url(obs):
            return (
                next(
                    iter(
                        [
                            image.original_url
                            for image in obs.photos
                            if not re.search(r"\.gif$", image.original_url, re.I)
                        ]
                    ),
                    None,
                )
                or INAT_LOGO
            )

        start = menu.current_page * self.per_page
        embeds = []
        if self._single_entry:
            obs = next(
                obs
                for i, obs in enumerate(entries, start=start)
                if i % self.per_page == self._current_entry
            )
            # TODO: use core formatter for embed-format page of observations
            embed = await self._cog.make_obs_embed(
                menu.ctx, obs, f"{WWW_BASE_URL}/observations/{obs.id}"
            )
            embeds = [embed]
        else:
            title = (
                f"Search: {self._query_title} (page {menu.current_page + 1} "
                f"of {ceil(self._total_results / self.per_page)})"
            )
            fmt_entries = []
            for i, obs in enumerate(entries, start=start):
                fmt_entry = await self._format_obs(obs)
                index = i
                if i + 1 > self._total_results:
                    index = self._total_results - 1
                # cursor highlighting for currently selected entry:
                # - markdown **bold** style
                if index % self.per_page == self._current_entry:
                    fmt_entry = f"**{fmt_entry}**"
                fmt_entries.append(f"{ENTRY_EMOJIS[i % self.per_page]} {fmt_entry}")
                embed = discord.Embed(url=self._url)
                # add embeds for all images when cursor is on 1st image, otherwise just
                # set the image of the 1st embed to be for the corresponding entry.
                if self._show_images:
                    if self._current_entry == index % self.per_page or (
                        self._multi_images and self._current_entry == 0
                    ):
                        embed.set_image(url=get_image_url(obs))
                        embeds.append(embed)
                else:
                    if not embeds:
                        embeds.append(embed)
            if embeds:
                embeds[0].description = "\n".join(fmt_entries)
                embeds[0].title = title
        # Only dpy2 and higher supports multi images via multiple embeds with
        # matching url per embed.
        if self._multi_images:
            message = {"embeds": embeds}
        else:
            # Fallback single image provided for legacy 1.7 dpy
            message = {"embed": embeds[0]}
        return message


class SearchTaxonSource(menus.AsyncIteratorPageSource):
    """Paged (both UI & API) taxon search results source."""

    async def generate_taxa(self, taxa):
        _taxa = taxa
        api_page = 1
        while _taxa:
            for taxon in _taxa:
                yield taxon
            if (api_page - 1) * self._per_api_page + len(_taxa) < self._total_results:
                api_page += 1
                # TODO: use dronefly-core (pyinat-based) get_observations
                # - top level should handle mapping dronefly query parts
                #   to iNat id#s to send to pyinat (`me`, Discord user mapping,
                #   place abbrevs, `home` place, user's `lang` setting, etc.)
                # - do pyinat at the lowest level to take advantage of
                #   caching, paginator, etc.
                # - eliminates reliance on computing our own API page
                (_taxa, _missing_taxa) = await self._cog.taxon_query.query_taxa(
                    self._ctx, self._query, page=api_page
                )
                _taxa = _taxa[0] if _taxa else None
            else:
                _taxa = None

    def __init__(
        self,
        cog,
        ctx,
        query,
        taxa,
        total_results,
        per_page,
        per_api_page,
        url,
        query_title,
    ):
        self._cog = cog
        self._ctx = ctx
        self._query = query
        self._total_results = total_results
        self._per_api_page = per_api_page
        self._url = url
        self._query_title = query_title
        self._single_entry = False
        self._multi_images = True
        self._show_images = True
        self._current_entry = 0
        super().__init__(self.generate_taxa(taxa), per_page=per_page)

    async def _format_taxon(self, taxon):
        # TODO: use core formatter for markdown-formatted individual taxon
        formatted_taxon = await self._cog.format_taxon(
            taxon,
            with_description=False,
            with_link=True,
            compact=True,
            with_user=not self._query.user,
        )
        return "".join(formatted_taxon)

    def is_paginating(self):
        """Always paginate so non-paging buttons work."""
        return True

    async def format_page(self, menu, entries):
        # TODO: move out to core classes
        def get_image_url(taxon):
            return (
                next(
                    iter(
                        [
                            image.original_url
                            for image in taxon.photos
                            if not re.search(r"\.gif$", image.original_url, re.I)
                        ]
                    ),
                    None,
                )
                or INAT_LOGO
            )

        start = menu.current_page * self.per_page
        embeds = []
        if self._single_entry:
            taxon = next(
                taxon
                for i, taxon in enumerate(entries, start=start)
                if i % self.per_page == self._current_entry
            )
            # TODO: use core formatter for embed-format page of observations
            embed = await self._cog.make_taxon_embed(
                menu.ctx, taxon, f"{WWW_BASE_URL}/taxon/{taxon.taxon_id}"
            )
            embeds = [embed]
        else:
            title = (
                f"Search: {self._query_title} (page {menu.current_page + 1} "
                f"of {ceil(self._total_results / self.per_page)})"
            )
            fmt_entries = []
            for i, taxon in enumerate(entries, start=start):
                fmt_entry = await self._format_taxon(taxon)
                index = i
                if i + 1 > self._total_results:
                    index = self._total_results - 1
                # cursor highlighting for currently selected entry:
                # - markdown **bold** style
                if index % self.per_page == self._current_entry:
                    fmt_entry = f"**{fmt_entry}**"
                fmt_entries.append(f"{ENTRY_EMOJIS[i % self.per_page]} {fmt_entry}")
                embed = discord.Embed(url=self._url)
                # add embeds for all images when cursor is on 1st image, otherwise just
                # set the image of the 1st embed to be for the corresponding entry.
                if self._show_images:
                    if self._current_entry == index % self.per_page or (
                        self._multi_images and self._current_entry == 0
                    ):
                        embed.set_image(url=get_image_url(taxon))
                        embeds.append(embed)
                else:
                    if not embeds:
                        embeds.append(embed)
            if embeds:
                embeds[0].description = "\n".join(fmt_entries)
                embeds[0].title = title
        # Only dpy2 and higher supports multi images via multiple embeds with
        # matching url per embed.
        if self._multi_images:
            message = {"embeds": embeds}
        else:
            # Fallback single image provided for legacy 1.7 dpy
            message = {"embed": embeds[0]}
        return message


class SearchMenuPages(menus.MenuPages, inherit_buttons=False):
    """Navigate search results."""

    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
        self._max_per_page = 8
        if self._source.per_page > self._max_per_page:
            self._source.per_page = self._max_per_page
        self._original_per_page = self._source.per_page
        self._max_buttons_added = self._source.per_page == self._max_per_page
        for i, emoji in enumerate(ENTRY_EMOJIS[: self._max_per_page]):
            if i >= self._source.per_page:
                break
            self.add_button(menus.Button(emoji, self.show_entry))

    async def send_initial_message(self, ctx, channel):
        """Send first page of menu

        - use ctx.send to be comaptible with hybrid commands
        - channel is ignored
        - a temporary measure until we convert to views
        """
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        return await ctx.send(**kwargs)

    @staticmethod
    async def show_entry(menu, payload):
        index = ENTRY_EMOJIS.index(str(payload.emoji))
        if (
            menu.current_page * menu._source.per_page + index
            < menu._source._total_results
        ):
            menu._source._current_entry = index
            menu._source._single_entry = False
            await menu.show_page(menu.current_page)

    @menus.button("\N{UP-POINTING SMALL RED TRIANGLE}")
    async def on_prev_result(self, payload):
        # don't run off the start
        if self._source._current_entry == 0 and self.current_page == 0:
            return
        self._source._current_entry -= 1
        page_offset = 0
        # back up to the last entry on the previous page
        if self._source._current_entry < 0:
            self._source._current_entry = self._source.per_page - 1
            page_offset = 1
        await self.show_page(self.current_page - page_offset)

    @menus.button("\N{DOWN-POINTING SMALL RED TRIANGLE}")
    async def on_next_result(self, payload):
        # don't run off the end
        if (
            self._source._current_entry + 2 + self.current_page * self._source.per_page
            > self._source._total_results
        ):
            return
        self._source._current_entry += 1
        page_offset = 0
        # advance to the first entry on the next page
        if self._source._current_entry > self._source.per_page - 1:
            self._source._current_entry = 0
            page_offset = 1
        await self.show_page(self.current_page + page_offset)

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}")
    async def go_to_previous_page(self, payload):
        """Go to the top of the previous page."""
        self._source._current_entry = 0
        self._source._single_entry = False
        await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}")
    async def go_to_next_page(self, payload):
        """Go to the top of the next page."""
        self._source._current_entry = 0
        self._source._single_entry = False
        await self.show_checked_page(self.current_page + 1)

    @menus.button("\N{WHITE HEAVY CHECK MARK}")
    async def on_select(self, payload):
        """Select this entry to view the full entry."""
        if self._source._single_entry:
            ctx = self.ctx
            current_page = self.current_page
            pages = SearchMenuPages(
                source=self._source,
                clear_reactions_after=True,
            )
            self.stop()
            self._source._single_entry = False
            pages.current_page = current_page
            await pages.start(ctx)
            await pages.show_checked_page(current_page)
        else:
            self._source._single_entry = True
            await self.show_checked_page(self.current_page)

    @menus.button("\N{CROSS MARK}")
    async def on_cancel(self, payload):
        """Cancel viewing full entry or stop menu and delete."""
        if self._source._single_entry:
            self._source._single_entry = False
            await self.show_checked_page(self.current_page)
        else:
            self.stop()
            with contextlib.suppress(discord.HTTPException):
                await self.message.delete()

    @menus.button("\N{CAMERA}")
    async def on_show_image(self, payload):
        """Toggle images / more entries per page.."""
        per_page = self._source.per_page
        current_page = self.current_page
        current_entry = current_page * per_page + self._source._current_entry
        if self._source._show_images:
            if not self._max_buttons_added:
                for i, emoji in enumerate(
                    ENTRY_EMOJIS[:8], start=self._source.per_page
                ):
                    await self.add_button(
                        menus.Button(emoji, self.show_entry), react=True
                    )
                self._max_buttons_added = True
            self._source._show_images = False
            self._original_per_page = self._source.per_page
            per_page = self._max_per_page
        else:
            self._source._show_images = True
            per_page = self._original_per_page
        self._source.per_page = per_page
        current_page = floor(current_entry / per_page)
        self._source._current_entry = current_entry - (current_page * per_page)
        await self.show_checked_page(current_page)
