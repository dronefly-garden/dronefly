"""Module for last command group."""
from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from ..base_classes import Taxon
from ..converters.base import NaturalQueryConverter
from ..core.models.taxon import RANK_EQUIVALENTS, RANK_KEYWORDS
from ..core.query.query import Query, TaxonQuery
from ..embeds.common import apologize
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..last import INatLinkMsg
from ..taxa import get_taxon


class CommandsLast(INatEmbeds, MixinMeta):
    """Mixin providing last command group."""

    @commands.group()
    @checks.bot_has_permissions(embed_links=True)
    async def last(self, ctx):
        """iNat info for the last message.

        The subcommands of this group show iNat info for the last matching message from the channel history. See the help for each subcommand for additional info displays that can be shown.
        """  # noqa: E501

    async def get_last_obs_from_history(self, ctx):
        """Get last obs from history."""
        msgs = await ctx.history(limit=100).flatten()
        inat_link_msg = INatLinkMsg(self)
        return await inat_link_msg.get_last_obs_msg(ctx, msgs)

    async def get_last_taxon_from_history(self, ctx):
        """Get last taxon from history."""
        msgs = await ctx.history(limit=100).flatten()
        inat_link_msg = INatLinkMsg(self)
        return await inat_link_msg.get_last_taxon_msg(ctx, msgs)

    @last.group(name="obs", aliases=["observation"], invoke_without_command=True)
    async def last_obs(self, ctx):
        """Last iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs):
            await apologize(ctx, "Nothing found")
            return

        embed = await self.make_last_obs_embed(last)
        await self.send_obs_embed(ctx, embed, last.obs)

    @last_obs.command(name="img", aliases=["image", "photo"])
    async def last_obs_img(self, ctx, number=None):
        """Image for last iNat observation.

        An optional image *number* indicates which image to show if the taxon has more than one. The first is shown by default.

        Look for the number to the right of the :camera: emoji on the observation display to see how many images it has.

        For example:
        `[p]last obs img` first image of the last observation
        `[p]last obs img 2` second image of the last observation
        """  # noqa: E501
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs:
            try:
                num = 1 if number is None else int(number)
            except ValueError:
                num = 0
            embed = await self.make_obs_embed(last.obs, last.url, preview=num)
            await self.send_obs_embed(ctx, embed, last.obs)
        else:
            await apologize(ctx, "Nothing found")

    async def query_from_last_taxon(self, ctx, taxon: Taxon, query: Query):
        """Query constructed from last taxon and arguments."""
        taxon_id = taxon.id
        if query.main:
            raise BadArgument("Taxon search terms can't be used here.")
        if query.controlled_term:
            raise BadArgument("A `with` filter can't be used here.")
        last_query = Query(
            main=TaxonQuery(taxon_id, [], [], [], ""),
            ancestor=None,
            user=query.user,
            place=query.place,
            controlled_term="",
            unobserved_by=query.unobserved_by,
            id_by=query.id_by,
            per=query.per,
            project=query.project,
            options=query.options,
        )
        return await self.query.get(ctx, last_query)

    @last_obs.group(name="taxon", aliases=["t"], invoke_without_command=True)
    async def last_obs_taxon(self, ctx, *, query: NaturalQueryConverter = None):
        """Taxon for last iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        taxon = None
        if last and last.obs and last.obs.taxon:
            taxon = last.obs.taxon
            if query:
                try:
                    taxon = await self.query_from_last_taxon(ctx, taxon, query)
                except (BadArgument, LookupError) as err:
                    await apologize(ctx, err.args[0])
                    return
        if taxon:
            await self.send_embed_for_taxon(ctx, taxon)
        else:
            await apologize(ctx, "Nothing found")

    @last_obs_taxon.command(name="img", aliases=["image"])
    async def last_obs_taxon_image(self, ctx, number=1):
        """Default taxon images for last iNat observation.

        Like `[p]last taxon image` except for the taxon of the last observation.

        See also `[p]help last taxon image`"""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await self.send_embed_for_taxon_image(ctx, last.obs.taxon, number)
        else:
            await apologize(ctx, "Nothing found")

    @last_obs.command(name="map", aliases=["m"])
    async def last_obs_map(self, ctx):
        """Taxon range map for last iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await ctx.send(embed=await self.make_map_embed([last.obs.taxon]))
        else:
            await apologize(ctx, "Nothing found")

    @last_obs.command(name="<rank>", aliases=RANK_KEYWORDS)
    async def last_obs_rank(self, ctx):
        """Taxon `<rank>` for last obs (e.g. `[p]last obs family`).

        For example:
        `[p]last obs family`      show family of last obs
        `[p]last obs superfamily` show superfamily of last obs
        """
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs):
            await apologize(ctx, "Nothing found")
            return

        rank = ctx.invoked_with
        if rank == "<rank>":
            await ctx.send_help()
            return

        rank_keyword = RANK_EQUIVALENTS.get(rank) or rank
        if last.obs.taxon:
            if last.obs.taxon.rank == rank_keyword:
                await self.send_embed_for_taxon(ctx, last.obs.taxon)
            else:
                full_record = await get_taxon(self, last.obs.taxon.id)
                ancestor = await self.taxon_query.get_taxon_ancestor(
                    full_record, rank_keyword
                )
                if ancestor:
                    await self.send_embed_for_taxon(ctx, ancestor)
                else:
                    await apologize(
                        ctx, f"The last observation has no {rank_keyword} ancestor."
                    )
        else:
            await apologize(ctx, "The last observation has no taxon.")

    @last.group(name="taxon", aliases=["t"], invoke_without_command=True)
    async def last_taxon(self, ctx, *, query: NaturalQueryConverter = None):
        """Last iNat taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        taxon = None
        if last and last.taxon:
            taxon = last.taxon
            if query:
                try:
                    taxon = await self.query_from_last_taxon(ctx, taxon, query)
                except (BadArgument, LookupError) as err:
                    await apologize(ctx, err.args[0])
                    return
        if taxon:
            await self.send_embed_for_taxon(ctx, taxon, include_ancestors=False)
        else:
            await apologize(ctx, "Nothing found")

    @last_taxon.command(name="map", aliases=["m"])
    async def last_taxon_map(self, ctx):
        """Range map of last iNat taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await apologize(ctx, "Nothing found")
            return

        await ctx.send(embed=await self.make_map_embed([last.taxon]))

    @last_taxon.command(name="image", aliases=["img"])
    async def last_taxon_image(self, ctx, number=1):
        """Default image for last taxon.

        An optional image *number* indicates which image to show if the taxon has more than one default image.

        For example:
        `[p]last t img` default image for the last taxon
        `[p]last t img 2` 2nd default image for the last taxon
        """  # noqa: E501
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await apologize(ctx, "Nothing found")
            return

        await self.send_embed_for_taxon_image(ctx, last.taxon, number)

    @last_taxon.command(name="<rank>", aliases=RANK_KEYWORDS)
    async def last_taxon_rank(self, ctx):
        """Taxon `<rank>` for last taxon (e.g. `[p]last t family`).

        For example:
        `[p]last t family` family of last taxon
        `[p]last t superfamily` superfamily of last taxon
        """
        rank = ctx.invoked_with
        if rank == "<rank>":
            await ctx.send_help()
            return

        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await apologize(ctx, "Nothing found")
            return

        rank_keyword = RANK_EQUIVALENTS.get(rank) or rank
        if last.taxon.rank == rank_keyword:
            await self.send_embed_for_taxon(ctx, last.taxon)
        else:
            full_record = await get_taxon(self, last.taxon.id)
            ancestor = await self.taxon_query.get_taxon_ancestor(
                full_record, rank_keyword
            )
            if ancestor:
                await self.send_embed_for_taxon(ctx, ancestor)
            else:
                await apologize(ctx, f"The last taxon has no {rank} ancestor.")
