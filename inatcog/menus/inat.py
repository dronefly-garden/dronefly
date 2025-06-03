"""iNat menus."""
import contextlib
from math import ceil, floor
import re
from typing import Any, Optional

import discord
from redbot.vendored.discord.ext import menus
from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.discord.menus import TaxonMenu as DiscordTaxonMenu

from ..utils import get_valid_user_config

LETTER_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
MAX_LETTER_EMOJIS = 10
ENTRY_EMOJIS = [chr(ord(LETTER_A) + i) for i in range(0, MAX_LETTER_EMOJIS - 1)]
INAT_LOGO = "https://static.inaturalist.org/sites/1-logo_square.png"


# TODO: provide base validators in core that can use the bot config
# instead. Then move UserButton and QueryUserButton back down a layer.
class UserButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row, custom_id="user")
        self.style = style
        self.emoji = "\N{BUST IN SILHOUETTE}"

    async def callback(self, interaction: discord.Interaction):
        # await self.view.show_checked_page(self.view.current_page + 1, interaction)
        pass

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to check if owner is registered here."""
        cog = self.view.cog
        try:
            interaction.valid_user = await get_valid_user_config(
                cog, interaction.user, anywhere=False
            )
        except LookupError:
            await interaction.response.send_message(
                content="You are not known here.", ephemeral=True
            )
            return False
        return True


class QueryUserButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        row: Optional[int],
    ):
        super().__init__(style=style, row=row, custom_id="query_user")
        self.style = style
        self.emoji = "\N{BUSTS IN SILHOUETTE}"

    async def callback(self, interaction: discord.Interaction):
        # await self.view.show_checked_page(self.view.current_page + 1, interaction)
        pass


class TaxonMenu(DiscordTaxonMenu):
    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.user_button = UserButton(discord.ButtonStyle.grey, 0)
        # self.query_user_button = QueryUserButton(discord.ButtonStyle.grey, 0)
        self.add_item(self.user_button)
        # Aself.add_item(self.query_user_button)


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
