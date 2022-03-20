"""Module for place command group."""

import re

from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..base_classes import WWW_BASE_URL
from ..checks import can_manage_places
from ..common import grouper
from ..embeds.common import apologize, make_embed
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..places import RESERVED_PLACES
from ..utils import get_valid_user_config


class CommandsPlace(INatEmbeds, MixinMeta):
    """Mixin providing place command group."""

    @commands.group(invoke_without_command=True)
    async def place(self, ctx, *, query):
        """Show iNat place or abbreviation.

        **query** may contain:
        - *id#* of the iNat place
        - *words* in the iNat place name
        - *abbreviation* defined with `[p]place add`
        """
        try:
            place = await self.place_table.get_place(ctx.guild, query, ctx.author)
            embed = make_embed(title=place.display_name, url=place.url)
            embed.add_field(name="Place number", value=place.place_id)
            if ctx.guild:
                guild_config = self.config.guild(ctx.guild)
                places = await guild_config.places()
                place_abbrevs = [
                    abbrev for abbrev in places if places[abbrev] == place.place_id
                ]
                if place_abbrevs:
                    abbrevs = ",".join(place_abbrevs)
                else:
                    abbrevs = "*none*"
                    try:
                        can_add_places = bool(
                            await get_valid_user_config(
                                self, ctx.author, anywhere=False
                            )
                        )
                    except LookupError:
                        can_add_places = False
                    if can_add_places:
                        embed.set_footer(
                            text=f"Add an abbreviation with {ctx.clean_prefix}place add"
                        )
                embed.add_field(
                    name=self.p.plural("Abbreviation", len(place_abbrevs)),
                    value=abbrevs,
                )
            await ctx.send(embed=embed)
        except LookupError as err:
            await ctx.send(err)

    @can_manage_places()
    @place.command(name="add")
    async def place_add(self, ctx, abbrev: str, place_number: int):
        """Add place abbreviation for server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        places = await config.places()
        abbrev_lowered = abbrev.lower()
        if abbrev_lowered in RESERVED_PLACES:
            await ctx.send(
                f"Place abbreviation '{abbrev_lowered}' cannot be added as it is reserved."
            )

        if abbrev_lowered in places:
            url = f"{WWW_BASE_URL}/places/{places[abbrev_lowered]}"
            await ctx.send(
                f"Place abbreviation '{abbrev_lowered}' is already defined as: {url}"
            )
            return

        places[abbrev_lowered] = place_number
        await config.places.set(places)
        await ctx.send("Place abbreviation added.")

    @place.command(name="list")
    @checks.bot_has_permissions(embed_links=True)
    async def place_list(self, ctx, *, match=""):
        """List places with abbreviations on this server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        places = await config.places()
        result_pages = []

        # Prefetch all uncached places, 500 at a time
        # - 500 is a maximum determined by testing. beyond that, iNat API
        #   will respond with:
        #
        #      Unprocessable Entity (422)
        #
        place_id_groups = [
            list(filter(None, results))
            for results in grouper(
                [
                    places[abbrev]
                    for abbrev in places
                    if int(places[abbrev]) not in self.api.places_cache
                ],
                500,
            )
        ]
        for place_id_group in place_id_groups:
            await self.api.get_places(place_id_group)

        # Iterate over places and do a quick cache lookup per place:
        for abbrev in sorted(places):
            place_id = int(places[abbrev])
            place_str_text = ""
            if place_id in self.api.places_cache:
                try:
                    place = await self.place_table.get_place(ctx.guild, place_id)
                    place_str = f"{abbrev}: [{place.display_name}]({place.url})"
                    place_str_text = f"{abbrev} {place.display_name}"
                except LookupError:
                    # In the unlikely case of the deletion of a place that is cached:
                    place_str = f"{abbrev}: {place_id} not found."
                    place_str_text = abbrev
            else:
                # Uncached places are listed by id (prefetch above should prevent this!)
                place_str = f"{abbrev}: [{place_id}]({WWW_BASE_URL}/places/{place_id})"
                place_str_text = abbrev
            if match:
                words = match.split(" ")
                if all(
                    re.search(pat, place_str_text)
                    for pat in [
                        re.compile(r"\b%s" % re.escape(word), re.I) for word in words
                    ]
                ):
                    result_pages.append(place_str)
            else:
                result_pages.append(place_str)
        pages = [
            "\n".join(filter(None, results)) for results in grouper(result_pages, 10)
        ]
        if pages:
            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            embeds = [
                make_embed(
                    title=f"Place abbreviations (page {index} of {pages_len})",
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            # menu() does not support lazy load of embeds iterator.
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await apologize(ctx, "Nothing found")

    @can_manage_places()
    @place.command(name="remove")
    async def place_remove(self, ctx, abbrev: str):
        """Remove place abbreviation for server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        places = await config.places()
        abbrev_lowered = abbrev.lower()

        if abbrev_lowered not in places:
            await ctx.send("Place abbreviation not defined.")
            return

        del places[abbrev_lowered]
        await config.places.set(places)
        await ctx.send("Place abbreviation removed.")
