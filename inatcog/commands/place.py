"""Module for place command group."""

import logging
import re

from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.discord.embeds import make_embed

from ..checks import can_manage_places
from ..common import grouper
from ..embeds.common import apologize
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..places import RESERVED_PLACES
from ..utils import has_valid_user_config

logger = logging.getLogger("red.dronefly." + __name__)


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
            embed.add_field(name="Place number", value=place.id)
            if ctx.guild:
                guild_config = self.config.guild(ctx.guild)
                places = await guild_config.places()
                place_abbrevs = [
                    abbrev for abbrev in places if places[abbrev] == place.id
                ]
                if place_abbrevs:
                    abbrevs = ", ".join(place_abbrevs)
                else:
                    abbrevs = "*none*"
                    can_add_places = await has_valid_user_config(
                        self, ctx.author, anywhere=False
                    )
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
    @checks.bot_has_permissions(embed_links=True, read_message_history=True)
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
            try:
                async with ctx.typing():
                    await self.api.get_places(place_id_group)
            except LookupError as err:
                # Deleted places should not raise here, but should simply be dropped
                # from the results, so this is something else (e.g. API failed to
                # respond)
                logger.warn(
                    "%s (places: %s, guild: %d)",
                    err,
                    ",".join(place_id_group),
                    ctx.guild.id,
                )

        # Iterate over places and do a quick cache lookup per place:
        for abbrev in sorted(places):
            place_id = int(places[abbrev])
            place_str_text = ""
            if place_id in self.api.places_cache:
                try:
                    place = await self.place_table.get_place(ctx.guild, place_id)
                    place_str = f"{abbrev}: [{place.display_name}]({place.url})"
                    place_str_text = f"{abbrev} {place.display_name}"
                except LookupError as err:
                    # Shouldn't ever happen. The cache should've been filled with
                    # any existing place entries from place_id_groups above. If
                    # the place is in the cache, then it should be retrievable by
                    # get_place(). If the place doesn't exist, it should not raise
                    # a LookupError, but should just fall through below and be
                    # listed by its id.
                    logger.error(
                        "Place in cache could not be retrieved: %s (place: %d, guild: %d)",
                        err,
                        place_id,
                        ctx.guild.id,
                    )
            # Most likely this is a deleted place. Show the abbrev, id, and link. The
            # user can check by clicking the link if it 404's and take action as
            # needed.
            if not place_str_text:
                logger.info(
                    "Place deleted? %s: %d (guild: %d)",
                    abbrev,
                    place_id,
                    ctx.guild.id,
                )
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
