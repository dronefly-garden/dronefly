"""Module for last command group."""
from redbot.core import checks, commands
from redbot.core.commands import BadArgument

from inatcog.base_classes import (
    CompoundQuery,
    SimpleQuery,
    Taxon,
    RANK_EQUIVALENTS,
    RANK_KEYWORDS,
)
from inatcog.converters import NaturalCompoundQueryConverter
from inatcog.embeds import apologize
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.last import INatLinkMsg
from inatcog.taxa import get_taxon


class CommandsLast(INatEmbeds, MixinMeta):
    """Mixin providing last command group."""

    @commands.group()
    @checks.bot_has_permissions(embed_links=True)
    async def last(self, ctx):
        """Show info for recently mentioned iNat page."""

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
        """Show recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs):
            await apologize(ctx, "Nothing found")
            return

        await ctx.send(embed=await self.make_last_obs_embed(ctx, last))
        if last.obs.sounds:
            await self.maybe_send_sound_url(ctx.channel, last.obs.sounds[0])

    @last_obs.command(name="img", aliases=["image", "photo"])
    async def last_obs_img(self, ctx, number=None):
        """Show image for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            try:
                num = 1 if number is None else int(number)
            except ValueError:
                num = 0
            await ctx.send(
                embed=await self.make_obs_embed(
                    ctx.guild, last.obs, last.url, preview=num
                )
            )
        else:
            await apologize(ctx, "Nothing found")

    async def query_from_last_taxon(self, ctx, taxon: Taxon, query: CompoundQuery):
        """Query constructed from last taxon and arguments."""
        taxon_id = taxon.taxon_id
        if query.main:
            raise BadArgument("Taxon search terms can't be used here.")
        if query.controlled_term:
            raise BadArgument("A `with` filter can't be used here.")
        last_query = CompoundQuery(
            main=SimpleQuery(taxon_id, [], [], [], ""),
            ancestor=None,
            user=query.user,
            place=query.place,
            controlled_term="",
            unobserved_by=query.unobserved_by,
            id_by=query.id_by,
            per=query.per,
        )
        return await self.taxon_query.query_taxon(ctx, last_query)

    @last_obs.group(name="taxon", aliases=["t"], invoke_without_command=True)
    async def last_obs_taxon(self, ctx, *, query: NaturalCompoundQueryConverter = None):
        """Show taxon for recently mentioned iNat observation."""
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
        """Show default taxon image for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await self.send_embed_for_taxon_image(ctx, last.obs.taxon, number)
        else:
            await apologize(ctx, "Nothing found")

    @last_obs.command(name="map", aliases=["m"])
    async def last_obs_map(self, ctx):
        """Show map for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await ctx.send(embed=await self.make_map_embed([last.obs.taxon]))
        else:
            await apologize(ctx, "Nothing found")

    @last_obs.command(name="<rank>", aliases=RANK_KEYWORDS)
    async def last_obs_rank(self, ctx):
        """Show the `<rank>` of the last observation (e.g. `family`).

        `[p]last obs family`      show family of last obs
        `[p]last obs superfamily` show superfamily of last obs

        Any rank known to iNat can be specified.
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
                full_record = await get_taxon(self, last.obs.taxon.taxon_id)
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
    async def last_taxon(self, ctx, *, query: NaturalCompoundQueryConverter = None):
        """Show recently mentioned iNat taxon."""
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
        """Show map for recently mentioned taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await apologize(ctx, "Nothing found")
            return

        await ctx.send(embed=await self.make_map_embed([last.taxon]))

    @last_taxon.command(name="image", aliases=["img"])
    async def last_taxon_image(self, ctx, number=1):
        """Show image for recently mentioned taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await apologize(ctx, "Nothing found")
            return

        await self.send_embed_for_taxon_image(ctx, last.taxon, number)

    @last_taxon.command(name="<rank>", aliases=RANK_KEYWORDS)
    async def last_taxon_rank(self, ctx):
        """Show the `<rank>` of the last taxon (e.g. `family`).

        `[p]last taxon family`      show family of last taxon
        `[p]last taxon superfamily` show superfamily of last taxon

        Any rank known to iNat can be specified.
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
            full_record = await get_taxon(self, last.taxon.taxon_id)
            ancestor = await self.taxon_query.get_taxon_ancestor(
                full_record, rank_keyword
            )
            if ancestor:
                await self.send_embed_for_taxon(ctx, ancestor)
            else:
                await apologize(ctx, f"The last taxon has no {rank} ancestor.")
