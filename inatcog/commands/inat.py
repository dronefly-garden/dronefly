"""Module for inat command group."""

import json
import pprint
from typing import Optional, Union

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.chat_formatting import pagify

from inatcog.converters.base import InheritableBoolConverter, ServerScopeConverter
from inatcog.embeds.common import make_embed
from inatcog.embeds.inat import INatEmbed, INatEmbeds
from inatcog.interfaces import MixinMeta

LISTEN_VALUE = { True: "enabled in channels and threads", False: "disabled", None: "enabled in threads only" }


class CommandsInat(INatEmbeds, MixinMeta):
    """Mixin providing inat command group."""

    @commands.group()
    async def inat(self, ctx):
        """Show/change iNat settings.

        See also `[p]help iNat` to list available `iNat` *commands* and other *Help* topics.
        """

    @commands.command(name="autoobs")
    async def topic_autoobs(self, ctx):
        """\u200b*Automatic observation* link preview feature.

        When `autoobs` is on for the channel/server:

        Just include a link to an observation in your message, and it will be looked up as if you typed `[p]obs <link>`

        Only the first link per message is looked up.

        Server mods and owners can set this up. See:
        `[p]help inat set autoobs server` and
        `[p]help inat set autoobs` (channel).

        In DM with the bot, `autoobs` is always on and cannot be changed.
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="cheatsheet", aliases=["commands"])
    async def topic_cheatsheet(self, ctx):
        """\u200b*Common commands.*

        **Taxon:**
        `,t birds` -> *the birds taxon*
        `,s taxa sparrow` -> *any named: sparrow*
        **Observer counts:**
        `,t my birds` -> *count mine*
        `,t birds by kueda` -> *count theirs*
        `,tab my birds` -> *just count; no taxon*
        **Place counts:**
        `,t home birds` -> *home place counts*
        `,t birds from peru` -> *peru counts*
        **Search observations:**
        `,s my birds` -> *my birds*
        `,s obs home birds` -> *from my home*
        `,s obs birds from peru` -> *from peru*
        **Match one observation:**
        `,obs my birds` -> *my latest bird*
        **Use filters:**
        `,obs my rg birds` -> *a bird that is RG*
        `,obs my nid birds` -> *one that needs id*
        `,s my nid birds` -> *any that need id*
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="dates", aliases=["date"])
    async def topic_dates(self, ctx):
        """\u200b*Date filters* and *sort order*.

        See also: `[p]query`, `[p]macros`, `[p]advanced`.

        **Date filters:**
        • `since <date>` - observed on or after the date
        • `until <date>` - observed on or before the date
        • `on <date>` - observed on the date
        • `added since <date>` - added on or after the date
        • `added until <date>` - added on or before the date
        • `added on <date>` - added on the date
        • `opt month=#` `opt year=#` `opt day=#` - observed this month, year, or day of month (use commas if more than one)

        **Sort order:**
        • newest to oldest added is the default
        • `reverse` - oldest to newest added
        • `newest` - newest to oldest observed
        • `oldest` - oldest to newest observed

        **Examples:**
        ```
        [p]obs my gcki on march 13
        -> My Golden-crowned kinglet observed March 13
        [p]obs gcki since jan 2021 newest
        -> First GCKI of the year
        [p]s obs gcki until mar
        -> On or before the month end
        [p]s obs gcki since feb until mar
        -> From Feb through Mar
        [p]s obs gcki added since tue
        -> Added on or after Tue
        [p]s obs gcki opt month=2,3
        -> Observed in Feb or Mar of any year
        ```
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="dot_taxon")
    async def topic_dot_taxon(self, ctx):
        """\u200b*Automatic `.taxon.` lookup* feature.

        When `dot_taxon` is on for the channel/server:

        • Surround taxon to lookup with `.`
        • Separate from other text with blanks
        • Only one lookup will be performed per message
        • Taxonomy tree is omitted for `by` or `from` lookups
        • Show the setting with `[p]inat show dot_taxon`

        **Examples:**
        ```
        It's .rwbl. for sure.
        ```
        • behaves like  `[p]taxon rwbl`
        ```
        Check out these .lacebugs by me. , please.
        ```
        • behaves like `[p]tab lacebugs by me`

        Server mods and owners can set this up. See:
        `[p]help inat set dot_taxon server` and
        `[p]help inat set dot_taxon` (channel).

        In DM with the bot, `dot_taxon` is always on and cannot be changed.
        """
        await ctx.send_help()

    @commands.command(name="macros", aliases=["macro"])
    async def topic_macros(self, ctx):
        """\u200b*Macro* query terms.

        A *query* or *taxon query* may include *macros* which are expanded to other query terms described below.

        See also: `[p]query`, `[p]taxon_query`, and `[p]groups`.

        __**`Macro`**__`  `__`Expands to`__
        **`my`**`      by me`
        **`home`**`    from home`
        **`rg`**`      opt quality_grade=research`
        **`nid`**`     opt quality_grade=needs_id`
        **`oldest`**`  opt order=asc`
        **`      `**`      order_by=observed_on`
        **`newest`**`  opt order=desc`
        **`      `**`      order_by=observed_on`
        **`reverse`**` opt order_by=asc`
        **`faves`**`   opt popular order_by=votes`
        **`spp`**`     opt hrank=species` (alias `species`)
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="groups", aliases=["group"])
    async def topic_groups(self, ctx):
        """\u200b*Query* macros that are *taxonomic groups*.

        See also: `[p]macros`, and `[p]query`.

        **`herps`**`       opt taxon_ids=`
        **`       `**`       20978,26036`
        **`lichenish`**`   opt taxon_ids=`
        **`       `**`       152028,791197,54743,152030,`
        **`       `**`       175541,127378,117881,117869`
        **`       `**`       without_taxon_id=352459`
        **`mothsonly`**`   lepidoptera opt`
        **`       `**`       without_taxon_id=47224`
        **`unknown`**`     opt iconic_taxa=unknown`
        **`       `**`       without_taxon_id=`
        **`       `**`       67333,151817,131236`
        **`waspsonly`**`   apocrita opt`
        **`       `**`       without_taxon_id=`
        **`       `**`       47336,630955`
        **`nonflowering`**` plantae opt`
        **`       `**`       without_taxon_id=47125`
        **`nonvascular`**` plantae opt`
        **`       `**`       without_taxon_id=211194`
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="query", aliases=["queries"])
    async def topic_query(self, ctx):
        """\u200b*Observation query* terms.

        A *query* may contain *taxon query* terms, *macros*, and other *query* terms described below.

        See also: `[p]taxon_query`, `[p]dates`, `[p]advanced`, `[p]macros`.

        Aside from *taxon*, other *query* terms may be:
        - `by <name>` for named user's observations; also `by me` or just `my` (a *macro*) for yourself
        - `from <place>` for named place; also `from home` or just `home` (a *macro*) for your *home place*
        - `in prj <project>` for named *project*
        - `with <term> <value>` for *controlled term* with the given *value*
        - `not by <name>` for obs unobserved by the user
        - `id by <name>` for obs ided by the user
        - `[added] since <date>`, `[added] until <date>`, `[added] on <date>`; see `[p]dates` for details
        **Examples:**
        ```
        [p]obs by benarmstrong
        -> most recently added observation by benarmstrong
        [p]obs insecta by benarmstrong
        -> most recent insecta by benarmstrong
        [p]s obs insecta from canada
        -> search for any insecta from Canada
        [p]s obs insecta with life larva
        -> search for insecta with life stage = larva
        ```
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="advanced")
    async def topic_advanced(self, ctx):
        """\u200b*Advanced* query options via `opt`.

        Shortcuts for the most commonly used `opt` options are provided as *macros*, e.g. use `rg` instead of `opt quality_grade=research`.

        See also: `[p]macros`, and `[p]query`.

        **Boolean options:**

        `captive` `endemic` `identified` `introduced` `native` `out_of_range` `pcid` `photos` `popular` `sounds` `threatened` `verifiable`

        Boolean options without a parameter default to `=true`, e.g. `,tab my opt verifiable` means `,tab my opt verifiable=true`. Other values can be `=false` or `=any`.

        **Options that always require a parameter:**

        `csi` `day` `month` `year` `hrank` `lrank` `id` `not_id` `quality_grade` `order` `order_by` `page` `rank` `iconic_taxa` `taxon_ids` `without_taxon_id`

        **Documentation & limitations:**

        See the [get observations API documentation](https://api.inaturalist.org/v1/docs/#!/Observations/get_observations) for detailed descriptions of these options and what parameter values are allowed. Not all options make sense for all queries/commands.
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="taxon_query", aliases=["taxon_queries", "query_taxon"])
    async def topic_taxon_query(self, ctx):
        """\u200b*Taxon query* terms.

        See also: `[p]query` and `[p]macros` to specify what is also shown about a taxon.

        A *taxon query* matches a single taxon. It may contain the following:
        - *id#* of the iNat taxon
        - *initial letters* of scientific or common names
        - *double-quotes* around exact words in the name
        - `rank` *keyword* filter by rank (`rank subspecies`, etc.)
        - *4-letter AOU codes* for birds
        - *taxon* `in` *an ancestor taxon*
        **Examples:**
        ```
        [p]taxon family bear
           -> Ursidae (Bears)
        [p]taxon prunella
           -> Prunella (self-heals)
        [p]taxon prunella in animals
           -> Prunella (Accentors)
        [p]taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(
        name="glossary", aliases=["term", "terms", "abbrevation", "abbreviations"]
    )
    async def topic_counts(self, ctx):
        """\u200b*Glossary* of terms and abbreviations.

        __**Obs.** = observations__
        __**Leaf taxa** = distinct taxa counted__ (per observer, place, etc.)
        - This is the default way that iNaturalist counts taxa. It is explained here: https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        __**Spp.** = species *or* leaf taxa__ depending on how they are counted on the related website page.
        - In leaderboard commands like `,topobs`, actual species are counted.
        - In commands counting just a single user like `,my`, *Spp* (species) and *Leaf taxa* are shown.
        - But otherwise, when a display has a *#spp* heading, it refers to *leaf taxa* by default.
        """  # noqa: E501
        await ctx.send_help()

    @commands.command(name="reactions", aliases=["reaction"])
    async def topic_reactions(self, ctx):
        """\u200bTaxon *reaction* buttons.

        Taxon reaction buttons appear on many different displays.  You may use them only if your iNat account is known in the server.
        - :bust_in_silhouette: to count your observations and species
        - :busts_in_silhouette: to write in another user to count
        - :house: to count your home place obs and species
        - :earth_africa: to write in another place to count
        - :regional_indicator_t: to toggle the taxonomy tree

        See `[p]help user set known` if you're already known in a server and want to be known on other servers.  Otherwise, ask a mod to add you.

        See `[p]help user add` if you're a server owner or mod.
        """  # noqa: E501

    @inat.group(name="set")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_set(self, ctx):
        """Change `iNat` settings (mods)."""

    @inat.command(name="test", hidden=True)
    async def inat_test(self, ctx):
        """Test command."""
        msg = await ctx.send(
            embed=make_embed(title="Test", description="Reactions test.")
        )
        start_adding_reactions(msg, ["\N{THREE BUTTON MOUSE}"])

    @inat_set.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_bot_prefixes(self, ctx, *prefixes):
        """Set server ignored bot prefixes.

        All messages starting with one of these *prefixes* will be ignored by
        [botname].

        - If *prefixes* is empty, current setting is shown.
        - You particularly need to set *bot_prefixes* if your server has more than one bot with `inatcog` loaded, otherwise it's unlikely you need to set this.
        - Set this to all prefixes of other bots separated by spaces to ensure [botname] ignores commands sent to them, especially when *autoobs* is enabled.
        - You don't need to include any prefixes of [botname] itself.
        """  # noqa: E501
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if prefixes:
            await config.bot_prefixes.set(prefixes)
        else:
            prefixes = await config.bot_prefixes()

        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @inat_set.command(name="listen")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_listen(self, ctx, scope: ServerScopeConverter):
        """Set message listen server scope.

        The `scope` parameter may be:
        - `on` (listen enabled in channels and threads on this server)
        - `off` (listen disabled)
        - `threads` (listen enabled only in threads on this server)

        When `listen` is `on` (default), the `autoobs` and `dot_taxon` message listeners operate both in a server's channels and in its threads when enabled. They can be disabled both at once with `[p]inat set listen off` or restricted to listen only in threads with `[p]inat set listen threads`.

        Changing the `listen` server scope does not enable or manage server-wide or per-channel listener features on its own. It is more of a "kill switch" to turn off listening entirely, or selectively for main channel conversations, leaving them active only in threads.

        See also: `[p]autoobs` and `[p]dot_taxon` to learn about these message listener features.
        """  # noqa: E501
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        await config.listen.set(scope)
        await ctx.send(f"Message listening is {LISTEN_VALUE[scope]}.")

    async def _set_role(self, ctx, config_item: str, role: Union[discord.Role, str]):
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if role:
            if isinstance(role, str):
                if role.lower() == "none":
                    await config.clear_raw(config_item)
                    value = "not set"
                else:
                    await ctx.send_help()
                    return None
            else:
                value = role.mention
                await config.set_raw(config_item, value=role.id)
        else:
            find = await config.get_raw(config_item)
            if find:
                role = next(
                    (_role for _role in ctx.guild.roles if _role.id == find), None
                )
                value = role.mention if role else f"missing role: <@&{find}>"
            else:
                value = "not set"
        return value

    @inat_set.command(name="inactive_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_inactive_role(self, ctx, inactive_role: Optional[Union[discord.Role, str]]):
        """Set server inactive role.

        To unset the inactive role: `[p]inat set inactive_role none`
        """
        value = await self._set_role(ctx, "inactive_role", inactive_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Inactive role: {value}"))

    @inat_set.command(name="active_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_active_role(self, ctx, active_role: Optional[Union[discord.Role, str]]):
        """Set server active role.

        To unset the active role: `[p]inat set active_role none`
        """
        value = await self._set_role(ctx, "active_role", active_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Active role: {value}"))

    @inat_set.command(name="manage_places_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_manage_places_role(
        self, ctx, manage_places_role: Optional[Union[discord.Role, str]]
    ):
        """Set server manage places role.

        To unset the manage places role: `[p]inat set manage_places_role none`
        """
        value = await self._set_role(ctx, "manage_places_role", manage_places_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Manage places role: {value}"))

    @inat_set.command(name="manage_projects_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_manage_projects_role(
        self, ctx, manage_projects_role: Optional[Union[discord.Role, str]]
    ):
        """Set server manage projects role.

        To unset the manage projects role: `[p]inat set manage_projects_role none`
        """
        value = await self._set_role(ctx, "manage_projects_role", manage_projects_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Manage projects role: {value}"))

    @inat_set.command(name="manage_users_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_manage_users_role(
        self, ctx, manage_users_role: Optional[Union[discord.Role, str]]
    ):
        """Set server manage users role.

        To unset the manage users role: `[p]inat set manage_users_role none`
        """
        value = await self._set_role(ctx, "manage_users_role", manage_users_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Manage users role: {value}"))

    @inat_set.command(name="beta_role")
    @checks.admin_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(embed_links=True)
    async def set_beta_role(self, ctx, beta_role: Optional[Union[discord.Role, str]]):
        """Set server beta role.

        Grant users with the role early access to unreleased features.

        To unset the manage users role: `[p]inat set manage_users_role none`
        """
        value = await self._set_role(ctx, "beta_role", beta_role)
        if value:
            await ctx.send(embed=make_embed(description=f"Beta role: {value}"))

    @inat.group(name="clear")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_clear(self, ctx):
        """Clear iNat settings (mods)."""

    @inat_clear.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def clear_bot_prefixes(self, ctx):
        """Clear server ignored bot prefixes."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.bot_prefixes.clear()

        await ctx.send("Server ignored bot prefixes cleared.")

    @inat_set.group(name="autoobs", invoke_without_command=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def set_autoobs(self, ctx, state: InheritableBoolConverter):
        """Set channel auto-observation mode.

        A separate subcommand sets this feature for the whole server. See `[p]help set autoobs server` for details.

        To set the mode for the channel:
        ```
        [p]inat set autoobs on
        [p]inat set autoobs off
        [p]inat set autoobs inherit
        ```
        When `inherit` is specified, channel mode inherits from the server setting.
        """  # noqa: E501
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.channel(ctx.channel)
        await config.autoobs.set(state)

        if state is None:
            server_state = await self.config.guild(ctx.guild).autoobs()
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if state else "off"
        await ctx.send(f"Channel observation auto-preview is {value}.")
        return

    @set_autoobs.command(name="server")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_autoobs_server(self, ctx, state: bool):
        """Set server auto-observation mode.

        ```
        [p]inat set autoobs server on
        [p]inat set autoobs server off
        ```

        See `[p]help autoobs` for usage of the feature.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.autoobs.set(state)
        await ctx.send(
            f"Server observation auto-preview is {'on' if state else 'off'}."
        )
        return

    @inat_set.group(invoke_without_command=True, name="dot_taxon")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_dot_taxon(self, ctx, state: InheritableBoolConverter):
        """Set channel .taxon. lookup.

        A separate subcommand sets this feature for the whole server. See `[p]help set dot_taxon server` for details.

        To set .taxon. lookup for the channel:
        ```
        [p]inat set dot_taxon on
        [p]inat set dot_taxon off
        [p]inat set dot_taxon inherit
        ```
        When `inherit` is specified, channel mode inherits from the server setting.

        See `[p]help dot_taxon` for usage of the feature.
        """  # noqa: E501
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.channel(ctx.channel)
        await config.dot_taxon.set(state)

        if state is None:
            server_state = await self.config.guild(ctx.guild).dot_taxon()
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if state else "off"
        await ctx.send(f"Channel .taxon. lookup is {value}.")
        return

    @set_dot_taxon.command(name="server")
    @checks.admin_or_permissions(manage_messages=True)
    async def dot_taxon_server(self, ctx, state: bool):
        """Set server .taxon. lookup.

        ```
        [p]inat set dot_taxon server on
        [p]inat set dot_taxon server off
        ```

        See `[p]help dot_taxon` for usage of the feature.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.dot_taxon.set(state)
        await ctx.send(f"Server .taxon. lookup is {'on' if state else 'off'}.")
        return

    @inat.group(name="show")
    @commands.bot_has_guild_permissions(read_messages=True)
    async def inat_show(self, ctx):
        """Show iNat settings."""

    # TODO: make this command work in DMs
    @inat.command(name="inspect")
    @commands.bot_has_guild_permissions(read_messages=True)
    async def inat_inspect(self, ctx, message_id: Optional[Union[int, str]]):
        """Inspect a message and show any iNat embed contents."""
        try:
            if message_id:
                if isinstance(message_id, str):
                    channel_id, message_id = (
                        int(id_num) for id_num in message_id.split("-")
                    )
                    if ctx.guild:
                        channel = ctx.guild.get_channel(channel_id)
                        if not channel:
                            raise LookupError
                else:
                    channel = ctx.channel
                message = await channel.fetch_message(message_id)
            else:
                ref = ctx.message.reference
                if ref:
                    message = ref.cached_message or await ctx.channel.fetch_message(
                        ref.message_id
                    )
                else:
                    await ctx.send_help()
                    return
        except discord.errors.NotFound:
            await ctx.send(f"Message not found: {message_id}")
            return
        except LookupError:
            await ctx.send(f"Channel not found: {channel_id}")
            return
        except ValueError:
            await ctx.send("Invalid argument")
            return

        if not message.embeds:
            await ctx.send(f"Message has no embed: {message.jump_url}")
            return

        embeds = []
        inat_embed = INatEmbed.from_discord_embed(message.embeds[0])
        embeds.append(inat_embed)
        # pylint: disable=no-member
        inat_inspect = (
            f"```py\n{pprint.pformat(inat_embed.inat_content_as_dict())}\n```"
        )
        inat_inspect_embed = make_embed(
            title="iNat object ids", description=inat_inspect
        )

        if inat_embed.description:
            embed_description = f"```md\n{inat_embed.description}\n```"
            description_embed = make_embed(
                title="Markdown formatted content",
                description=embed_description,
            )
            embeds.append(description_embed)

        embeds.append(inat_inspect_embed)

        embed_dict = inat_embed.to_dict()
        if "description" in embed_dict:
            del embed_dict["description"]
        attributes_inspect = (
            f"```json\n{json.dumps(embed_dict, indent=4, sort_keys=True)}\n```"
        )
        attributes_embed = make_embed(
            title="Embed attributes", description=attributes_inspect
        )
        embeds.append(attributes_embed)
        reactions = message.reactions
        if reactions:
            reactions_table = ""
            all_users = await self.config.all_users()
            for reaction in reactions:
                reactions_table += f"{reaction.emoji}: {reaction.count}\n"
                known_users = []
                unknown_users = []
                async for user in reaction.users():
                    if not user.bot:
                        if user.id in all_users:
                            known_users.append(f"`{user.id}`")
                        else:
                            unknown_users.append(f"`{user.id}`")
                if known_users:
                    reactions_table += "\n".join(known_users) + "\n"
                if unknown_users:
                    reactions_table += "*unknown:*\n" + "\n".join(unknown_users) + "\n"
            pages = [page for page in pagify(reactions_table, page_length=500)]
            page_number = 0
            for page in pages:
                page_number += 1
                reactions_embed = make_embed(
                    title=f"Message reactions (page {page_number} of {len(pages)})",
                    description=page,
                )
                embeds.append(reactions_embed)

        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @inat_show.command(name="autoobs")
    async def show_autoobs(self, ctx):
        """Show channel & server auto-observation mode.

        See `[p]help autoobs` to learn about the feature."""
        if ctx.author.bot or ctx.guild is None:
            return

        server_config = self.config.guild(ctx.guild)
        server_state = await server_config.autoobs()
        await ctx.send(
            f"Server observation auto-preview is {'on' if server_state else 'off'}."
        )
        channel_config = self.config.channel(ctx.channel)
        channel_state = await channel_config.autoobs()
        if channel_state is None:
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if channel_state else "off"
        await ctx.send(f"Channel observation auto-preview is {value}.")
        return

    @inat_show.command(name="dot_taxon")
    async def show_dot_taxon(self, ctx):
        """Show channel & server .taxon. lookup.

        See `[p]help dot_taxon` to learn about the feature."""
        if ctx.author.bot or ctx.guild is None:
            return

        server_config = self.config.guild(ctx.guild)
        server_state = await server_config.dot_taxon()
        await ctx.send(f"Server .taxon. lookup is {'on' if server_state else 'off'}.")
        channel_config = self.config.channel(ctx.channel)
        channel_state = await channel_config.dot_taxon()
        if channel_state is None:
            value = f"inherited from server ({'on' if server_state else 'off'})"
        else:
            value = "on" if channel_state else "off"
        await ctx.send(f"Channel .taxon. lookup is {value}.")
        return

    @inat_show.command(name="listen")
    async def show_listen(self, ctx):
        """Show message listen scope."""
        if ctx.author.bot or ctx.guild is None:
            return

        guild_config = self.config.guild(ctx.guild)
        listen_server_scope = await guild_config.listen()
        await ctx.send(f"Message listening is {LISTEN_VALUE[listen_server_scope]}.")

    @inat_show.command(name="bot_prefixes")
    async def show_bot_prefixes(self, ctx):
        """Show server ignored bot prefixes."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        prefixes = await config.bot_prefixes()
        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @inat_set.command(name="home")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_home(self, ctx, home: str):
        """Set server default home place."""
        config = self.config.guild(ctx.guild)
        try:
            place = await self.place_table.get_place(ctx.guild, home, ctx.author)
        except LookupError as err:
            await ctx.send(err)
            return
        await config.home.set(place.place_id)
        await ctx.send(f"iNat server default home set:\n{place.url}")

    @inat_show.command(name="home")
    async def show_home(self, ctx):
        """Show server default home place."""
        config = self.config.guild(ctx.guild)
        home = await config.home()
        await ctx.send("iNat server default home:")
        try:
            place = await self.place_table.get_place(ctx.guild, int(home), ctx.author)
            await ctx.send(place.url)
        except LookupError as err:
            await ctx.send(err)

    @staticmethod
    def format_event(abbrev, event):
        """Format an event description."""
        main = {True: " (main)", False: ""}[event["main"]]
        project_id = event["project_id"]
        line = f"**Abbrev:** {abbrev}{main} **Project id:** {project_id}"
        role = event["role"]
        if role:
            line += f" **Role:** <@&{role}>"
        teams = event["teams"]
        if teams:
            line += f" **Teams:** {teams}"
        return line

    @inat_set.command(name="event")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_event(
        self,
        ctx,
        project_abbrev: str,
        project_id: str,
        main: Optional[bool] = False,
        role: Optional[discord.Role] = None,
        teams: Optional[str] = None,
    ):
        """Add a server event project.

        - `project_abbrev` uniquely identifies this project.
        - `project_id` Use `[p]prj` or `[p]s prj` to look it up for the project.
        - `main` is a main event for the server, listed in the `[p]user` / `[p]me` display. Please define no more than two of these.
        - `role` identifies a user as a participant of the event project.
        - `teams` one or more *event project abbreviations* for other teams of this event, separated by commas.

        *Examples:*
        To define two main server projects:

        `[p]inat set event ever 48611 True`
        `[p]inat set event year 124254 True`

        To define "Team Crustaceans" vs. "Team Cetaceans" bioblitz event:

        `[p]inat set event crustaceans 122951 False "Team Crustaceans" cetaceans`
        `[p]inat set event cetaceans 122952 False "Team Cetaceans" crustaceans`
        """  # noqa: E501

        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()
        _event_project = event_projects.get(project_abbrev)
        event_project = _event_project or {}

        description = ""
        if _event_project:
            line = self.format_event(project_abbrev, event_project)
            description = f"was:\n{line}\n"

        event_project["project_id"] = project_id
        event_projects[project_abbrev] = event_project
        event_project["main"] = main
        if role or not _event_project:
            event_project["role"] = role.id if role else None
        if teams or not _event_project:
            event_project["teams"] = teams
        await config.event_projects.set(event_projects)
        line = self.format_event(project_abbrev, event_project)
        if _event_project:
            description += f"now:\n{line}"
        else:
            description = line
        embed = make_embed(title="Event project", description=description)
        await ctx.send(embed=embed)

    @inat_clear.command(name="event")
    @checks.admin_or_permissions(manage_roles=True)
    async def clear_event(self, ctx, project_abbrev: str):
        """Clear a server event project."""
        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()

        if project_abbrev not in event_projects:
            await ctx.send("event project not known.")
            return

        del event_projects[project_abbrev]
        await config.event_projects.set(event_projects)
        await ctx.send("event project removed.")

    @inat_show.command(name="events")
    async def show_events(self, ctx):
        """Show server event projects."""
        config = self.config.guild(ctx.guild)
        event_projects = await config.event_projects()
        embed = make_embed(title="Event projects")
        description = ""
        for abbrev in event_projects:
            event = event_projects[abbrev]
            line = self.format_event(abbrev, event)
            description += line + "\n"
        embed.description = description
        await ctx.send(embed=embed)
