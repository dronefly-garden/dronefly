"""Module for obs command group."""

import re
from typing import Optional

from redbot.core import commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import start_adding_reactions

from inatcog.base_classes import PAT_OBS_LINK, WWW_BASE_URL
from inatcog.converters import ContextMemberConverter, NaturalCompoundQueryConverter
from inatcog.embeds import apologize, make_embed
from inatcog.inat_embeds import INatEmbeds
from inatcog.interfaces import MixinMeta
from inatcog.obs import get_obs_fields, maybe_match_obs
from inatcog.taxa import PAT_TAXON_LINK


class CommandsObs(INatEmbeds, MixinMeta):
    """Mixin providing obs command group."""

    @commands.group(invoke_without_command=True, aliases=["observation"])
    async def obs(self, ctx, *, query: str):
        """Show observation matching query, link, or number.

        **query** may contain:
        - `by [name]` to match the named resgistered user (or `me`)
        - `from [place]` to match the named place
        - `with [term] [value]` to matched the controlled term with the
          given value
        **Examples:**
        ```
        [p]obs by benarmstrong
           -> most recently added observation by benarmstrong
        [p]obs insecta by benarmstrong
           -> most recent insecta by benarmstrong
        [p]obs insecta from canada
           -> most recent insecta from Canada
        [p]obs insecta with life larva
           -> most recent insecta with life stage = larva
        [p]obs https://inaturalist.org/observations/#
           -> display the linked observation
        [p]obs #
           -> display the observation for id #
        ```
        - Use `[p]search obs` to find more than one observation.
        - See `[p]help taxon` for help specifying optional taxa.
        """

        id_or_link = None
        if query.isnumeric():
            id_or_link = query
        else:
            mat = re.search(PAT_OBS_LINK, query)
            if mat and mat["url"]:
                id_or_link = query
        if id_or_link:
            obs, url = await maybe_match_obs(ctx, self, id_or_link, id_permitted=True)
            # Note: if the user specified an invalid or deleted id, a url is still
            # produced (i.e. should 404).
            if url:
                await ctx.send(
                    embed=await self.make_obs_embed(ctx.guild, obs, url, preview=False)
                )
                if obs and obs.sounds:
                    await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
                return
            else:
                await apologize(ctx, "I don't understand")
                return

        try:
            compound_query = await NaturalCompoundQueryConverter.convert(ctx, query)
            obs = await self.obs_query.query_single_obs(ctx, compound_query)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

        url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
        await ctx.send(
            embed=await self.make_obs_embed(ctx.guild, obs, url, preview=True)
        )
        if obs and obs.sounds:
            await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])

    @commands.group(invoke_without_command=True, aliases=["tab"])
    async def tabulate(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Show a table from iNaturalist data matching the query.

        • Only taxa can be tabulated. More kinds of table
          to be supported in future releases.
        • The row contents can be `from` or `by`. If both
          are given, what to tabulate is filtered by the
          `from` place, and the `by` person is the first row.
        • The `not by` qualifier counts observations / species
          unobserved by each user in the table. It may be combined
          with `from`, but not `by`.
        e.g.
        ```
        ,tab fish from home
             -> per place (home listed; others react to add)
        ,tab fish by me
             -> per user (self listed; others react to add)
        ,tab fish not by me
             -> per unobserved by (self listed; others react to add)
        ,tab fish from canada by me
             -> per user (self listed; others react to add)
                but only fish from canada are tabulated
        ```
        """
        if query.controlled_term or not query.main:
            await apologize(ctx, "I can't tabulate that yet.")
            return

        try:
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
            msg = await ctx.send(embed=await self.make_obs_counts_embed(filtered_taxon))
            start_adding_reactions(msg, ["#️⃣", "📝", "🏠", "📍"])
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

    @tabulate.command()
    async def maverick(self, ctx, *, query: Optional[NaturalCompoundQueryConverter]):
        """Show maverick identifications.

        • By default, if your iNat login is known, your own maverick
          identifications are displayed.
        • The `by` qualifier can be used to display mavericks for
          another known user.
        """
        if query and (
            query.place
            or query.controlled_term
            or query.main
            or query.unobserved_by
            or query.per
        ):
            await apologize(ctx, "I can't tabulate that yet.")
            return
        try:
            query_user = None
            if query and query.user:
                query_user = query.user
            else:
                query_me = await NaturalCompoundQueryConverter.convert(ctx, "by me")
                query_user = query_me.user
            who = await ContextMemberConverter.convert(ctx, query_user)
            user = await self.user_table.get_user(who.member)
            embed = make_embed()
            embed.title = f"Maverick identifications by {user.display_name()}"
            embed.url = (
                "https://www.inaturalist.org/identifications?category=maverick"
                f"&user_id={user.user_id}"
            )
            await ctx.send(embed=embed)
        except (BadArgument, LookupError) as err:
            await apologize(ctx, err.args[0])
            return

    @commands.command()
    async def link(self, ctx, *, query):
        """Show summary for iNaturalist link.

        e.g.
        ```
        [p]link https://inaturalist.org/observations/#
           -> an embed summarizing the observation link
        ```
        """
        mat = re.search(PAT_OBS_LINK, query)
        if mat:
            obs_id = int(mat["obs_id"])
            url = mat["url"]

            home = await self.get_home(ctx)
            results = (
                await self.api.get_observations(
                    obs_id, include_new_projects=1, preferred_place_id=home
                )
            )["results"]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(ctx.guild, obs, url))
            if obs and obs.sounds:
                await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
            return

        mat = re.search(PAT_TAXON_LINK, query)
        if mat:
            query = await NaturalCompoundQueryConverter.convert(ctx, mat["taxon_id"])
            await (self.bot.get_command("taxon")(ctx, query=query))
            return

        await apologize(ctx)
