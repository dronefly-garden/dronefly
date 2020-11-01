"""Module for place command group."""

from redbot.core import checks, commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from inatcog.base_classes import WWW_BASE_URL
from inatcog.checks import known_inat_user
from inatcog.common import grouper
from inatcog.embeds import apologize, make_embed
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.places import RESERVED_PLACES


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
            await ctx.send(place.url)
        except LookupError as err:
            await ctx.send(err)

    @known_inat_user()
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
    async def place_list(self, ctx):
        """List places with abbreviations on this server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        places = await config.places()
        result_pages = []
        for abbrev in places:
            # Only lookup cached places. Uncached places will just be shown by number.
            place_id = int(places[abbrev])
            if place_id in self.api.places_cache:
                try:
                    place = await self.place_table.get_place(ctx.guild, place_id)
                    place_str = f"{abbrev}: [{place.display_name}]({place.url})"
                except LookupError:
                    place_str = f"{abbrev}: {place_id} not found."
            else:
                place_str = f"{abbrev}: [{place_id}]({WWW_BASE_URL}/places/{place_id})"
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

    @known_inat_user()
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
