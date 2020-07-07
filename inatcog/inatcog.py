"""A cog for using the iNaturalist platform."""
from abc import ABC
from math import ceil
import re
from typing import Optional, Union
import urllib.parse
import asyncio
import discord
import inflect
from redbot.core import checks, commands, Config
from redbot.core.utils.menus import menu, start_adding_reactions, DEFAULT_CONTROLS
from pyparsing import ParseException
from .api import INatAPI, WWW_BASE_URL
from .checks import known_inat_user
from .common import DEQUOTE, grouper
from .controlled_terms import ControlledTerm, match_controlled_term
from .converters import (
    ContextMemberConverter,
    QuotedContextMemberConverter,
    InheritableBoolConverter,
)
from .embeds import make_embed, sorry
from .last import INatLinkMsg
from .obs import get_obs_fields, maybe_match_obs, PAT_OBS_LINK
from .parsers import RANK_EQUIVALENTS, RANK_KEYWORDS
from .places import INatPlaceTable, PAT_PLACE_LINK, RESERVED_PLACES
from .projects import INatProjectTable, UserProject, PAT_PROJECT_LINK
from .listeners import Listeners
from .search import INatSiteSearch
from .taxa import (
    FilteredTaxon,
    INatTaxaQuery,
    format_taxon_name,
    get_taxon,
    PAT_TAXON_LINK,
)
from .users import INatUserTable, PAT_USER_LINK, User

_SCHEMA_VERSION = 2
_DEVELOPER_BOT_IDS = [614037008217800707, 620938327293558794]
_INAT_GUILD_ID = 525711945270296587
SPOILER_PAT = re.compile(r"\|\|")
DOUBLE_BAR_LIT = "\\|\\|"


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    See https://github.com/mikeshardmind/SinbadCogs/blob/v3/rolemanagement/core.py
    """


# pylint: disable=too-many-ancestors
class INatCog(Listeners, commands.Cog, name="iNat", metaclass=CompositeMetaClass):
    """Commands provided by `inatcog`."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1607)
        self.api = INatAPI()
        self.p = inflect.engine()  # pylint: disable=invalid-name
        self.taxa_query = INatTaxaQuery(self)
        self.user_table = INatUserTable(self)
        self.place_table = INatPlaceTable(self)
        self.project_table = INatProjectTable(self)
        self.site_search = INatSiteSearch(self)
        self.user_cache_init = {}
        self.reaction_locks = {}
        self.predicate_locks = {}

        self.config.register_global(schema_version=1)
        self.config.register_guild(
            autoobs=False,
            dot_taxon=False,
            active_role=None,
            bot_prefixes=[],
            inactive_role=None,
            user_projects={},
            places={},
            projects={},
            project_emojis={},
        )
        self.config.register_channel(autoobs=None, dot_taxon=None)
        self.config.register_user(
            home=None, inat_user_id=None, known_in=[], known_all=False
        )
        self._cleaned_up = False
        self._init_task: asyncio.Task = self.bot.loop.create_task(self.initialize())
        self._ready_event: asyncio.Event = asyncio.Event()

    async def cog_before_invoke(self, ctx: commands.Context):
        await self._ready_event.wait()

    async def initialize(self) -> None:
        """Initialization after bot is ready."""
        await self.bot.wait_until_ready()
        await self._migrate_config(await self.config.schema_version(), _SCHEMA_VERSION)
        self._ready_event.set()

    async def _migrate_config(self, from_version: int, to_version: int) -> None:
        if from_version == to_version:
            return

        if from_version < 2 <= to_version:
            # Initial registrations via the developer's own bot were intended
            # to be for the iNat server only. Prevent leakage to other servers.
            # Any other servers using this feature with schema 1 must now
            # re-register each user, or the user must `[p]user set known
            # true` to be known in other servers.
            if self.bot.user.id in _DEVELOPER_BOT_IDS:
                all_users = await self.config.all_users()
                for (user_id, user_value) in all_users.items():
                    if user_value["inat_user_id"]:
                        await self.config.user_from_id(int(user_id)).known_in.set(
                            [_INAT_GUILD_ID]
                        )
            await self.config.schema_version.set(2)

    def cog_unload(self):
        """Cleanup when the cog unloads."""
        if not self._cleaned_up:
            self.api.session.detach()
            if self._init_task:
                self._init_task.cancel()
            self._cleaned_up = True

    @commands.group()
    async def inat(self, ctx):
        """Show/change iNat settings.

        See `[p]help iNat` for all `inatcog` help topics."""

    @inat.group(name="set")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_set(self, ctx):
        """Change iNat settings (mods)."""

    @inat_set.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_bot_prefixes(self, ctx, *prefixes):
        """Set server ignored bot prefixes (mods).

        All messages starting with one of these *prefixes* will be ignored by
        [botname].

        - If *prefixes* is empty, current setting is shown.
        - You particularly need to set *bot_prefixes* if your server has more
          than one bot with `inatcog` loaded, otherwise it's unlikely you
          need to set this.
        - Set this to all prefixes of other bots separated by spaces to
          ensure [botname] ignores commands sent to them, especially when
          *autoobs* is enabled.
        - You don't need to include any prefixes of [botname] itself.
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if prefixes:
            await config.bot_prefixes.set(prefixes)
        else:
            prefixes = await config.bot_prefixes()

        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @inat_set.command(name="inactive_role")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_inactive_role(self, ctx, inactive_role: Optional[discord.Role]):
        """Set server Inactive role."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if inactive_role:
            msg = inactive_role.mention
            await config.inactive_role.set(inactive_role.id)
        else:
            find = await config.inactive_role()
            if find:
                inactive_role = next(
                    (role for role in ctx.guild.roles if role.id == find), None
                )
                msg = (
                    inactive_role.mention
                    if inactive_role
                    else f"missing role: <@&{find}>"
                )
            else:
                msg = "not set"
        await ctx.send(embed=make_embed(description=f"Inactive role: {msg}"))

    @inat_set.command(name="active_role")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_active_role(self, ctx, active_role: Optional[discord.Role]):
        """Set server Active role."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)

        if active_role:
            msg = active_role.mention
            await config.active_role.set(active_role.id)
        else:
            find = await config.active_role()
            if find:
                active_role = next(
                    (role for role in ctx.guild.roles if role.id == find), None
                )
                msg = (
                    active_role.mention if active_role else f"missing role: <@&{find}>"
                )
            else:
                msg = "not set"
        await ctx.send(embed=make_embed(description=f"Active role: {msg}"))

    @inat.group(name="clear")
    @checks.admin_or_permissions(manage_messages=True)
    async def inat_clear(self, ctx):
        """Clear iNat settings (mods)."""

    @inat_clear.command(name="bot_prefixes")
    @checks.admin_or_permissions(manage_messages=True)
    async def clear_bot_prefixes(self, ctx):
        """Clear server ignored bot prefixes (mods)."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.bot_prefixes.clear()

        await ctx.send("Server ignored bot prefixes cleared.")

    @inat_set.group(invoke_without_command=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs(self, ctx, state: InheritableBoolConverter):
        """Set channel auto-observation mode (mods).

        To set the mode for the channel:
        ```
        [p]inat set autoobs on
        [p]inat set autoobs off
        [p]inat set autoobs inherit
        ```
        When `inherit` is specified, channel mode inherits from the server
        setting.
        """
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

    @autoobs.command(name="server")
    @checks.admin_or_permissions(manage_messages=True)
    async def autoobs_server(self, ctx, state: bool):
        """Set server auto-observation mode (mods).

        ```
        [p]inat set autoobs server on
        [p]inat set autoobs server off
        ```
        """
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        await config.autoobs.set(state)
        await ctx.send(
            f"Server observation auto-preview is {'on' if state else 'off'}."
        )
        return

    @commands.command()
    async def dot_taxon(self, ctx):
        """How to use the `.taxon.` lookup feature.

        • Surround taxon to lookup with `.`
        • Separate from other text with blanks
        • Only one lookup will be performed per message
        • Taxonomy tree is omitted for `by` or `from` lookups
        • Show the setting with `[p]inat show dot_taxon`
        • Set with `[p]inat set dot_taxon` (mods)

        **Examples:**
        ```
        It's .rwbl. for sure.
        ```
        • behaves like  `[p]taxon rwbl`
        ```
        Check out these .lace bugs by me. , please.
        ```
        • behaves like `[p]obs lace bugs by me`
        """
        await ctx.send_help()

    @inat_set.group(invoke_without_command=True, name="dot_taxon")
    @checks.admin_or_permissions(manage_messages=True)
    async def set_dot_taxon(self, ctx, state: InheritableBoolConverter):
        """Set channel .taxon. lookup (mods).

        To set .taxon. lookup for the channel:
        ```
        [p]inat set dot_taxon on
        [p]inat set dot_taxon off
        [p]inat set dot_taxon inherit
        ```
        When `inherit` is specified, channel mode inherits from the server
        setting.

        See `[p]help dot_taxon` for usage of the feature.
        """
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
        """Set server .taxon. lookup (mods).

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
    async def inat_show(self, ctx):
        """Show iNat settings."""

    @inat_show.command(name="autoobs")
    async def show_autoobs(self, ctx):
        """Show channel & server auto-observation mode."""
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

        See `[p]help dot_taxon` for how to use the feature."""
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

    @inat_show.command(name="bot_prefixes")
    async def show_bot_prefixes(self, ctx):
        """Show server ignored bot prefixes."""
        if ctx.author.bot or ctx.guild is None:
            return

        config = self.config.guild(ctx.guild)
        prefixes = await config.bot_prefixes()
        await ctx.send(f"Other bot prefixes are: {repr(list(prefixes))}")

    @commands.group()
    async def last(self, ctx):
        """Show info for recently mentioned iNat page."""

    async def get_last_obs_from_history(self, ctx):
        """Get last obs from history."""
        msgs = await ctx.history(limit=1000).flatten()
        inat_link_msg = INatLinkMsg(self.api)
        return await inat_link_msg.get_last_obs_msg(msgs)

    async def get_last_taxon_from_history(self, ctx):
        """Get last taxon from history."""
        msgs = await ctx.history(limit=1000).flatten()
        inat_link_msg = INatLinkMsg(self.api)
        return await inat_link_msg.get_last_taxon_msg(msgs)

    @last.group(name="obs", aliases=["observation"], invoke_without_command=True)
    async def last_obs(self, ctx):
        """Show recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        await ctx.send(embed=await self.make_last_obs_embed(ctx, last))
        if last.obs.sounds:
            await self.maybe_send_sound_url(ctx.channel, last.obs.sounds[0])

    @last_obs.command(name="img", aliases=["image"])
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
            await ctx.send(embed=sorry(apology="Nothing found"))

    @last_obs.group(name="taxon", aliases=["t"], invoke_without_command=True)
    async def last_obs_taxon(self, ctx):
        """Show taxon for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await self.send_embed_for_taxon(ctx, last.obs.taxon)
        else:
            await ctx.send(embed=sorry(apology="Nothing found"))

    @last_obs_taxon.command(name="img", aliases=["image"])
    async def last_obs_taxon_image(self, ctx):
        """Show default taxon image for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await self.send_embed_for_taxon_image(ctx, last.obs.taxon)
        else:
            await ctx.send(embed=sorry(apology="Nothing found"))

    @last_obs_taxon.command(name="by")
    async def last_obs_taxon_by(self, ctx, user: QuotedContextMemberConverter):
        """Show taxon for recently mentioned observation with counts for a user."""
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs and last.obs.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        inat_user = await self.user_table.get_user(user.member)
        filtered_taxon = FilteredTaxon(last.obs.taxon, inat_user, None, None)
        await self.send_embed_for_taxon(ctx, filtered_taxon)

    @last_obs_taxon.command(name="from")
    async def last_obs_taxon_from(self, ctx, place: str):
        """Show taxon for recently mentioned observation with counts for a place."""
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs and last.obs.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        try:
            place = await self.place_table.get_place(ctx.guild, place, ctx.author)
        except LookupError:
            place = None
        filtered_taxon = FilteredTaxon(last.obs.taxon, None, place, None)
        await self.send_embed_for_taxon(ctx, filtered_taxon)

    @last_obs.command(name="map", aliases=["m"])
    async def last_obs_map(self, ctx):
        """Show map for recently mentioned iNat observation."""
        last = await self.get_last_obs_from_history(ctx)
        if last and last.obs and last.obs.taxon:
            await ctx.send(embed=await self.make_map_embed([last.obs.taxon]))
        else:
            await ctx.send(embed=sorry(apology="Nothing found"))

    @last_obs.command(name="<rank>", aliases=RANK_KEYWORDS)
    async def last_obs_rank(self, ctx):
        """Show the `<rank>` of the last observation (e.g. `family`).

        `[p]last obs family`      show family of last obs
        `[p]last obs superfamily` show superfamily of last obs

        Any rank known to iNat can be specified.
        """
        last = await self.get_last_obs_from_history(ctx)
        if not (last and last.obs):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        rank = ctx.invoked_with
        if rank == "<rank>":
            await ctx.send_help()
            return

        rank_keyword = RANK_EQUIVALENTS.get(rank) or rank
        if last.obs.taxon.rank == rank_keyword:
            await self.send_embed_for_taxon(ctx, last.obs.taxon)
        elif last.obs.taxon:
            full_record = await get_taxon(self, last.obs.taxon.taxon_id)
            ancestor = await self.taxa_query.get_taxon_ancestor(
                full_record, rank_keyword
            )
            if ancestor:
                await self.send_embed_for_taxon(ctx, ancestor)
            else:
                await ctx.send(
                    embed=sorry(
                        apology=f"The last observation has no {rank_keyword} ancestor."
                    )
                )
        else:
            await ctx.send(embed=sorry(apology="The last observation has no taxon."))

    @last.group(name="taxon", aliases=["t"], invoke_without_command=True)
    async def last_taxon(self, ctx):
        """Show recently mentioned iNat taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        await self.send_embed_for_taxon(ctx, last.taxon)

    @last_taxon.command(name="by")
    async def last_taxon_by(self, ctx, user: QuotedContextMemberConverter):
        """Show recently mentioned taxon with observation counts for a user."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        inat_user = await self.user_table.get_user(user.member)
        filtered_taxon = FilteredTaxon(last.taxon, inat_user, None, None)
        await self.send_embed_for_taxon(ctx, filtered_taxon)

    @last_taxon.command(name="from")
    async def last_taxon_from(self, ctx, place: str):
        """Show recently mentioned taxon with observation counts for a place."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        try:
            place = await self.place_table.get_place(ctx.guild, place, ctx.author)
        except LookupError:
            place = None
        filtered_taxon = FilteredTaxon(last.taxon, None, place, None)
        await self.send_embed_for_taxon(ctx, filtered_taxon)

    @last_taxon.command(name="map", aliases=["m"])
    async def last_taxon_map(self, ctx):
        """Show map for recently mentioned taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        await ctx.send(embed=await self.make_map_embed([last.taxon]))

    @last_taxon.command(name="image", aliases=["img"])
    async def last_taxon_image(self, ctx):
        """Show image for recently mentioned taxon."""
        last = await self.get_last_taxon_from_history(ctx)
        if not (last and last.taxon):
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        await self.send_embed_for_taxon_image(ctx, last.taxon)

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
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        rank_keyword = RANK_EQUIVALENTS.get(rank) or rank
        if last.taxon.rank == rank_keyword:
            await self.send_embed_for_taxon(ctx, last.taxon)
        else:
            full_record = await get_taxon(self, last.taxon.taxon_id)
            ancestor = await self.taxa_query.get_taxon_ancestor(
                full_record, rank_keyword
            )
            if ancestor:
                await self.send_embed_for_taxon(ctx, ancestor)
            else:
                await ctx.send(
                    embed=sorry(apology=f"The last taxon has no {rank} ancestor.")
                )

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
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            url = mat["url"]

            results = (await self.api.get_observations(obs_id, include_new_projects=1))[
                "results"
            ]
            obs = get_obs_fields(results[0]) if results else None
            await ctx.send(embed=await self.make_obs_embed(ctx.guild, obs, url))
            if obs and obs.sounds:
                await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
            return

        mat = re.search(PAT_TAXON_LINK, query)
        if mat:
            await self.taxon(ctx, query=mat["taxon_id"])
            return

        await ctx.send(embed=sorry())

    @commands.command()
    async def map(self, ctx, *, taxa_list):
        """Show range map for a list of one or more taxa.

        **Examples:**
        ```
        [p]map polar bear
        [p]map 24255,24267
        [p]map boreal chorus frog,western chorus frog
        ```
        See `[p]help taxon` for help specifying taxa.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxa_query.query_taxa(taxa_list)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_map_embed(taxa))

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
            await ctx.send(embed=sorry(apology="Nothing found"))

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

    @commands.group(invoke_without_command=True)
    async def project(self, ctx, *, query):
        """Show iNat project or abbreviation.

        **query** may contain:
        - *id#* of the iNat project
        - *words* in the iNat project name
        - *abbreviation* defined with `[p]project add`
        """
        try:
            project = await self.project_table.get_project(ctx.guild, query)
            await ctx.send(project.url)
        except LookupError as err:
            await ctx.send(err)

    @known_inat_user()
    @project.command(name="add")
    async def project_add(self, ctx, abbrev: str, project_number: int):
        """Add project abbreviation for server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        projects = await config.projects()
        abbrev_lowered = abbrev.lower()
        if abbrev_lowered in RESERVED_PLACES:
            await ctx.send(
                f"Project abbreviation '{abbrev_lowered}' cannot be added as it is reserved."
            )

        if abbrev_lowered in projects:
            url = f"{WWW_BASE_URL}/projects/{projects[abbrev_lowered]}"
            await ctx.send(
                f"Project abbreviation '{abbrev_lowered}' is already defined as: {url}"
            )
            return

        projects[abbrev_lowered] = project_number
        await config.projects.set(projects)
        await ctx.send("Project abbreviation added.")

    @project.command(name="list")
    async def project_list(self, ctx):
        """List projects with abbreviations on this server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        projects = await config.projects()
        result_pages = []
        for abbrev in projects:
            # Only lookup cached projects. Uncached projects will just be shown by number.
            proj_id = int(projects[abbrev])
            if proj_id in self.api.projects_cache:
                try:
                    project = await self.project_table.get_project(ctx.guild, proj_id)
                    proj_str = f"{abbrev}: [{project.title}]({project.url})"
                except LookupError:
                    proj_str = f"{abbrev}: {proj_id} not found."
            else:
                proj_str = f"{abbrev}: [{proj_id}]({WWW_BASE_URL}/projects/{proj_id})"
            result_pages.append(proj_str)
        pages = [
            "\n".join(filter(None, results)) for results in grouper(result_pages, 10)
        ]
        if pages:
            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            embeds = [
                make_embed(
                    title=f"Project abbreviations (page {index} of {pages_len})",
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            # menu() does not support lazy load of embeds iterator.
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(embed=sorry(apology="Nothing found"))

    @known_inat_user()
    @project.command(name="remove")
    async def project_remove(self, ctx, abbrev: str):
        """Remove project abbreviation for server."""
        if not ctx.guild:
            return

        config = self.config.guild(ctx.guild)
        projects = await config.projects()
        abbrev_lowered = abbrev.lower()

        if abbrev_lowered not in projects:
            await ctx.send("Project abbreviation not defined.")
            return

        del projects[abbrev_lowered]
        await config.projects.set(projects)
        await ctx.send("Project abbreviation removed.")

    @project.command(name="stats")
    async def project_stats(self, ctx, project: str, user: str = "me"):
        """Show project stats for the named user.

        Observation & species count & rank of the user within the project
        are shown, as well as leaf taxa, which are not ranked. Leaf taxa
        are explained here:
        https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        """

        if project == "":
            await ctx.send_help()
        try:
            proj = await self.project_table.get_project(ctx.guild, project)
        except LookupError as err:
            await ctx.send(err)
            return

        try:
            ctx_member = await ContextMemberConverter.convert(ctx, user)
            member = ctx_member.member
            user = await self.user_table.get_user(member)
        except (commands.BadArgument, LookupError) as err:
            await ctx.send(err)
            return

        embed = await self.make_stats_embed(member, user, proj)
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True, aliases=["observation"])
    async def obs(self, ctx, *, query):
        """Show observation summary for link or number.

        e.g.
        ```
        [p]obs #
           -> an embed summarizing the numbered observation
        [p]obs https://inaturalist.org/observations/#
           -> an embed summarizing the observation link (minus the preview,
              which Discord provides itself)
        [p]obs insects by kueda
           -> an embed showing counts of insects by user kueda
        [p]obs insects from canada
           -> an embed showing counts of insects from Canada
        ```
        """

        obs, url = await maybe_match_obs(self.api, query, id_permitted=True)
        # Note: if the user specified an invalid or deleted id, a url is still
        # produced (i.e. should 404).
        if url:
            await ctx.send(
                embed=await self.make_obs_embed(ctx.guild, obs, url, preview=False)
            )
            if obs and obs.sounds:
                await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
            return

        try:
            filtered_taxon = await self.taxa_query.query_taxon(ctx, query)
            msg = await ctx.send(embed=await self.make_obs_counts_embed(filtered_taxon))
            start_adding_reactions(msg, ["#️⃣", "📝", "🏠", "📍"])
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

    @obs.command(name="with")
    async def obs_with(self, ctx, term_name, value_name, *, taxon_query):
        """Show first matching observation with term & value for taxon.

        Note: this is an experimental feature. The command may change form or
        be replaced with a different command before it is finalized."""
        controlled_terms_dict = await self.api.get_controlled_terms()
        controlled_terms = [
            ControlledTerm.from_dict(term, infer_missing=True)
            for term in controlled_terms_dict["results"]
        ]
        try:
            (term, value) = match_controlled_term(
                controlled_terms, term_name, value_name
            )
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        try:
            filtered_taxon = await self.taxa_query.query_taxon(ctx, taxon_query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        kwargs = {"term_id": term.id, "term_value_id": value.id}
        kwargs["taxon_id"] = filtered_taxon.taxon.taxon_id
        if filtered_taxon.user:
            kwargs["user_id"] = filtered_taxon.user.user_id
        if filtered_taxon.place:
            kwargs["place_id"] = filtered_taxon.place.place_id
        observations_results = await self.api.get_observations(**kwargs)
        if not observations_results["results"]:
            await ctx.send(embed=sorry(apology="Nothing found"))
            return

        obs = get_obs_fields(observations_results["results"][0])
        url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
        await ctx.send(
            embed=await self.make_obs_embed(ctx.guild, obs, url, preview=True)
        )
        if obs and obs.sounds:
            await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])

    @commands.command()
    async def related(self, ctx, *, taxa_list):
        """Relatedness of a list of taxa.

        **Examples:**
        ```
        [p]related 24255,24267
        [p]related boreal chorus frog,western chorus frog
        ```
        See `[p]help taxon` for help specifying taxa.
        """

        if not taxa_list:
            await ctx.send_help()
            return

        try:
            taxa = await self.taxa_query.query_taxa(taxa_list)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_related_embed(taxa))

    @commands.command(aliases=["img"])
    async def image(self, ctx, *, taxon_query):
        """Show default image for taxon query.

        `Aliases: [p]img`

        See `[p]help taxon` for `taxon_query` format."""
        try:
            filtered_taxon = await self.taxa_query.query_taxon(ctx, taxon_query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await self.send_embed_for_taxon_image(ctx, filtered_taxon.taxon)

    @commands.command(aliases=["t"])
    async def taxon(self, ctx, *, query):
        """Show taxon best matching the query.

        `Aliases: [p]t`
        **query** may contain:
        - *id#* of the iNat taxon
        - *initial letters* of scientific or common names
        - *double-quotes* around exact words in the name
        - *rank keywords* filter by ranks (`sp`, `family`, etc.)
        - *4-letter AOU codes* for birds
        - *taxon* `in` *an ancestor taxon*
        **Examples:**
        ```
        [p]taxon family bear
           -> Ursidae (Bears)
        [p]taxon prunella
           -> Prunella (self-heals)
        [p]taxon prunella in animals
           -> Prunella
        [p]taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        """

        try:
            filtered_taxon = await self.taxa_query.query_taxon(ctx, query)
        except ParseException:
            await ctx.send(embed=sorry())
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        if filtered_taxon.user and filtered_taxon.place:
            reason = (
                "I don't understand that query.\nPerhaps you meant:\n"
                f"`{ctx.clean_prefix}obs {query}`"
            )
            await ctx.send(embed=sorry(apology=reason))
        else:
            await self.send_embed_for_taxon(ctx, filtered_taxon)

    @commands.command()
    async def tname(self, ctx, *, query):
        """Show taxon name best matching the query.

        See `[p]help taxon` for help with the query.
        ```
        """

        try:
            filtered_taxon = await self.taxa_query.query_taxon(ctx, query)
        except ParseException:
            await ctx.send("I don't understand")
            return
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(reason)
            return

        await ctx.send(filtered_taxon.taxon.name)

    async def _search(self, ctx, query, keyword: Optional[str]):
        async def display_selected(result):
            mat = re.search(PAT_OBS_LINK, result)
            if mat:
                results = (
                    await self.api.get_observations(
                        mat["obs_id"], include_new_projects=1
                    )
                )["results"]
                obs = get_obs_fields(results[0]) if results else None
                if obs:
                    embed = await self.make_obs_embed(ctx.guild, obs, url)
                    if obs and obs.sounds:
                        await self.maybe_send_sound_url(ctx.channel, obs.sounds[0])
                    controls = {"❌": DEFAULT_CONTROLS["❌"]}
                    await menu(ctx, [embed], controls)
                    return
                else:
                    await ctx.send(embed=sorry(apology="Not found"))
                    return
            mat = re.search(PAT_TAXON_LINK, result)
            if mat:
                await self.taxon(ctx, query=mat["taxon_id"])
                return
            mat = re.search(PAT_USER_LINK, result)
            if mat:
                await ctx.send(
                    f"{WWW_BASE_URL}/people/{mat['user_id'] or mat['login']}"
                )
                return
            mat = re.search(PAT_PROJECT_LINK, result)
            if mat:
                await self.project(ctx, query=mat["project_id"])
                return
            mat = re.search(PAT_PLACE_LINK, result)
            if mat:
                await self.place(ctx, query=mat["place_id"])

        async def select_result_reaction(
            ctx, pages, controls, message, page, timeout, reaction
        ):
            number = buttons.index(reaction)
            selected_result_offset = number + page * per_embed_page
            if selected_result_offset > len(results) - 1:
                return
            result = results[number + page * per_embed_page]
            await display_selected(result)
            await menu(ctx, pages, controls, message, page, timeout)

        kwargs = {}
        kw_lowered = ""
        url = f"{WWW_BASE_URL}/search?q={urllib.parse.quote_plus(query)}"
        if keyword:
            kw_lowered = keyword.lower()
            if kw_lowered == "inactive":
                url = f"{WWW_BASE_URL}/taxa/search?q={urllib.parse.quote_plus(query)}"
                url += f"&sources={keyword}"
                kwargs["is_active"] = "any"
            elif kw_lowered == "obs":
                try:
                    filtered_taxon = await self.taxa_query.query_taxon(ctx, query)
                    kwargs["taxon_id"] = filtered_taxon.taxon.taxon_id
                    if filtered_taxon.user:
                        kwargs["user_id"] = filtered_taxon.user.user_id
                    if filtered_taxon.place:
                        kwargs["place_id"] = filtered_taxon.place.place_id
                    kwargs["verifiable"] = "any"
                    query = format_taxon_name(filtered_taxon.taxon)
                except ParseException:
                    await ctx.send(embed=sorry())
                    return
                except LookupError as err:
                    reason = err.args[0]
                    await ctx.send(embed=sorry(apology=reason))
                    return

                url = f"{WWW_BASE_URL}/observations?{urllib.parse.urlencode(kwargs)}"
                kwargs["include_new_projects"] = 1
                kwargs["per_page"] = 200
            else:
                kwargs["sources"] = kw_lowered
                url += f"&sources={keyword}"
        if kw_lowered == "obs":
            response = await self.api.get_observations(**kwargs)
            raw_results = response["results"]
            results = [
                "\n".join(
                    self.format_obs(
                        get_obs_fields(result),
                        with_description=False,
                        with_id=False,
                        with_link=True,
                    )
                )
                for result in raw_results
            ]
            total_results = response["total_results"]
            per_page = response["per_page"]
            per_embed_page = 5
        else:
            (results, total_results, per_page) = await self.site_search.search(
                query, **kwargs
            )
            per_embed_page = 10

        all_buttons = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯"][
            :per_embed_page
        ]
        buttons_count = min(len(results), len(all_buttons))
        buttons = all_buttons[:buttons_count]
        controls = DEFAULT_CONTROLS.copy()
        for button in buttons:
            controls[button] = select_result_reaction

        pages = []
        for group in grouper(results, per_embed_page):
            lines = [
                " ".join((buttons[i], result))
                for i, result in enumerate(filter(None, group), 0)
            ]
            page = "\n".join(lines)
            pages.append(page)

        if pages:
            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            if len(results) < total_results:
                pages_len = (
                    f"{pages_len}; "
                    f"{ceil((total_results - per_page)/per_embed_page)} more not shown"
                )
            embeds = [
                make_embed(
                    title=f"Search: {query} (page {index} of {pages_len})",
                    url=url,
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            await menu(ctx, embeds, controls)
        else:
            await ctx.send(embed=sorry(apology="Nothing found"))

    @commands.group(aliases=["s"], invoke_without_command=True)
    async def search(self, ctx, *, query):
        """Search iNat.

        `Aliases: [p]s`
        """
        await self._search(ctx, query, None)

    @search.command(name="places", aliases=["place"])
    async def search_places(self, ctx, *, query):
        """Search iNat places."""
        await self._search(ctx, query, "places")

    @search.command(name="projects", aliases=["project"])
    async def search_projects(self, ctx, *, query):
        """Search iNat projects."""
        await self._search(ctx, query, "projects")

    @search.command(name="taxa", aliases=["taxon"])
    async def search_taxa(self, ctx, *, query):
        """Search iNat taxa."""
        await self._search(ctx, query, "taxa")

    @search.command(name="inactive")
    async def search_inactive(self, ctx, *, query):
        """Search iNat taxa (includes inactive)."""
        await self._search(ctx, query, "inactive")

    @search.command(name="users", aliases=["user", "person", "people"])
    async def search_users(self, ctx, *, query):
        """Search iNat users."""
        await self._search(ctx, query, "users")

    @search.command(name="obs", aliases=["observation", "observations"])
    async def search_obs(self, ctx, *, query):
        """Search iNat observations."""
        await self._search(ctx, query, "obs")

    @commands.command(aliases=["sp"])
    async def species(self, ctx, *, query):
        """Show species best matching the query.

        `Aliases: [p]sp`
        See `[p]help taxon` for query help."""
        await self.taxon(ctx, query="species " + query)

    @inat_set.command(name="user_project")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_user_project(
        self, ctx, project_id: int, emoji: Union[str, discord.Emoji]
    ):
        """Add a server user project (mods)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)
        if project_id_str in user_projects:
            await ctx.send("iNat user project already known.")
            return

        user_projects[project_id_str] = str(emoji)
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project added.")

    @inat_clear.command(name="user_project")
    @checks.admin_or_permissions(manage_roles=True)
    async def clear_user_project(self, ctx, project_id: int):
        """Clear a server user project (mods)."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        project_id_str = str(project_id)

        if project_id_str not in user_projects:
            await ctx.send("iNat user project not known.")
            return

        del user_projects[project_id_str]
        await config.user_projects.set(user_projects)
        await ctx.send("iNat user project removed.")

    @inat_show.command(name="user_projects")
    async def show_user_projects(self, ctx):
        """Show server user projects."""
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        for project_id in user_projects:
            await ctx.send(
                f"{user_projects[project_id]} {WWW_BASE_URL}/projects/{project_id}"
            )
            await asyncio.sleep(1)

    @commands.command()
    async def iuser(self, ctx, *, login: str):
        """Show iNat user matching login.

        Examples:

        `[p]iuser kueda`
        """
        if not ctx.guild:
            return

        found = None
        response = await self.api.get_users(login, refresh_cache=True)
        if response and response["results"]:
            found = next(
                (
                    result
                    for result in response["results"]
                    if login in (str(result["id"]), result["login"])
                ),
                None,
            )
        if not found:
            await ctx.send(embed=sorry(apology="Not found"))
            return

        inat_user = User.from_dict(found)
        await ctx.send(inat_user.profile_url())

    @commands.group(invoke_without_command=True, aliases=["who"])
    async def user(self, ctx, *, who: QuotedContextMemberConverter):
        """Show user if their iNat id is known.

        `Aliases: [p]who`

        First characters of the nickname or username are matched provided
        that user is cached by the server (e.g. if they were recently active).
        Otherwise, the nickname or username must be exact. If there is more
        than one username that exactly matches, append '#' plus the 4-digit
        discriminator to disambiguate.

        Examples:

        `[p]user Syn`
          matches `SyntheticBee#4951` if they spoke recently.
        `[p]user SyntheticBee`
          matches `SyntheticBee#4951` even if not recently active, assuming
          there is only one `SyntheticBee`.
        `[p]user SyntheticBee#4951`
          matches `SyntheticBee#4951` even if not recently active.

        If the server has defined any user_projects, then observations,
        species, & leaf taxa stats for each project are shown. Leaf taxa are
        explained here:
        https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        """
        if not ctx.guild:
            return

        member = who.member
        try:
            user = await self.user_table.get_user(member, refresh_cache=True)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        embed = await self.make_user_embed(ctx, member, user)
        await ctx.send(embed=embed)

    @commands.command()
    @known_inat_user()
    async def me(self, ctx):  # pylint: disable=invalid-name
        """Show your iNat info & stats for this server."""
        member = await ContextMemberConverter.convert(ctx, "me")
        await self.user(ctx, who=member)

    @commands.command()
    @known_inat_user()
    async def my(self, ctx, project: str):  # pylint: disable=invalid-name
        """Show your observations, species, & ranks for an iNat project."""
        await self.project_stats(ctx, project, "me")

    @commands.command()
    async def rank(self, ctx, project: str, user: str):  # pylint: disable=invalid-name
        """Show observations, species, & ranks in an iNat project for a user."""
        await self.project_stats(ctx, project, user)

    @user.command(name="add")
    @checks.admin_or_permissions(manage_roles=True)
    async def user_add(self, ctx, discord_user: discord.User, inat_user):
        """Add user as an iNat user (mods only)."""
        config = self.config.user(discord_user)

        inat_user_id = await config.inat_user_id()
        known_all = await config.known_all()
        known_in = await config.known_in()
        if inat_user_id and known_all or ctx.guild.id in known_in:
            await ctx.send("iNat user already known.")
            return

        mat_link = re.search(PAT_USER_LINK, inat_user)
        match = mat_link and (mat_link["user_id"] or mat_link["login"])
        if match:
            user_query = match
        else:
            user_query = inat_user

        user = None
        response = await self.api.get_users(user_query, refresh_cache=True)
        if response and response["results"]:
            user = User.from_dict(response["results"][0])
            mat_login = user_query.lower()
            mat_id = int(user_query) if user_query.isnumeric() else None
            if not ((user.login == mat_login) or (user.user_id == mat_id)):
                user = None

        if not user:
            await ctx.send("iNat user not found.")
            return

        # We don't support registering one Discord user on different servers
        # to different iNat user IDs! Corrective action is: bot owner removes
        # the user (will be removed from all guilds) before they can be added
        # under the new iNat ID.
        if inat_user_id:
            if inat_user_id != user.user_id:
                await ctx.send(
                    "New iNat user id for user! Registration under old id must be removed first."
                )
                return
        else:
            await config.inat_user_id.set(user.user_id)

        known_in.append(ctx.guild.id)
        await config.known_in.set(known_in)

        await ctx.send(
            f"{discord_user.display_name} is added as {user.display_name()}."
        )

    @user.command(name="remove")
    @checks.admin_or_permissions(manage_roles=True)
    async def user_remove(self, ctx, discord_user: discord.User):
        """Remove user as an iNat user (mods only)."""
        config = self.config.user(discord_user)
        inat_user_id = await config.inat_user_id()
        known_in = await config.known_in()
        known_all = await config.known_all()
        if not inat_user_id or not (known_all or ctx.guild.id in known_in):
            await ctx.send("iNat user not known.")
            return
        # User can only be removed from servers where they were added:
        if ctx.guild.id in known_in:
            known_in.remove(ctx.guild.id)
            await config.known_in.set(known_in)
            if known_in:
                await ctx.send("iNat user removed from this server.")
            else:
                # Removal from last server removes all traces of the user:
                await config.inat_user_id.clear()
                await config.known_all.clear()
                await config.known_in.clear()
                await ctx.send("iNat user removed.")
        elif known_in and known_all:
            await ctx.send(
                "iNat user was added on another server and can only be removed there."
            )

    async def get_valid_user_config(self, ctx):
        """Get iNat user config known in this guild."""
        user_config = self.config.user(ctx.author)
        inat_user_id = await user_config.inat_user_id()
        known_in = await user_config.known_in()
        known_all = await user_config.known_all()
        if not (inat_user_id and known_all or ctx.guild.id in known_in):
            raise LookupError("Ask a moderator to add your iNat profile link.")
        return user_config

    async def user_show_settings(self, ctx, config, setting: str = "all"):
        """Show iNat user settings."""
        if setting not in ["all", "known", "home"]:
            await ctx.send(f"Unknown setting: {setting}")
            return
        if setting in ["all", "known"]:
            known_all = await config.known_all()
            await ctx.send(f"known: {known_all}")
        if setting in ["all", "home"]:
            home_id = await config.home()
            if home_id:
                try:
                    home = await self.place_table.get_place(ctx.guild, home_id)
                    await ctx.send(f"home: {home.display_name} (<{home.url}>)")
                except LookupError:
                    await ctx.send(f"Non-existent place ({home_id})")
            else:
                await ctx.send("home: none")

    @user.group(name="set", invoke_without_command=True)
    @known_inat_user()
    async def user_set(self, ctx, arg: str = None):
        """Show or set your iNat user settings.

        `[p]user set` shows all settings
        `[p]user set [name]` shows the named setting
        `[p]user set [name] [value]` set value of the named setting
        """
        if arg:
            await ctx.send(f"Unknown setting: {arg}")
            return
        try:
            config = await self.get_valid_user_config(ctx)
        except LookupError as err:
            await ctx.send(err)
            return

        await self.user_show_settings(ctx, config)

    @user_set.command(name="home")
    @known_inat_user()
    async def user_set_home(self, ctx, *, value: str = None):
        """Show or set your home iNat place.

        `[p]user set home` show your home place
        `[p]user set home clear` clear your home place
        `[p]user set home [place]` set your home place
        """
        try:
            config = await self.get_valid_user_config(ctx)
        except LookupError as err:
            await ctx.send(err)
            return

        if value is not None:
            value = re.sub(DEQUOTE, r"\1", value)
            bot = self.bot.user.name
            if value.lower() in ["clear", "none", ""]:
                await config.home.clear()
                await ctx.send(f"{bot} no longer has a home place set for you.")
            else:
                try:
                    home = await self.place_table.get_place(ctx.guild, value)
                    await config.home.set(home.place_id)
                    await ctx.send(
                        f"{bot} will use {home.display_name} as your home place."
                    )
                except LookupError as err:
                    await ctx.send(err)
                    return

        await self.user_show_settings(ctx, config, "home")

    @user_set.command(name="known")
    @known_inat_user()
    async def user_set_known(self, ctx, value: bool = None):
        """Show or set if your iNat user settings are known on other servers.

        `[p]user set known` show known on other servers (default: not known)
        `[p]user set known true` set known on other servers
        """
        try:
            config = await self.get_valid_user_config(ctx)
        except LookupError as err:
            await ctx.send(err)
            return

        if value is not None:
            await config.known_all.set(value)

            bot = self.bot.user.name
            if value:
                await ctx.send(
                    f"{bot} will know your iNat settings when you join a server it is on."
                )
            else:
                await ctx.send(
                    f"{bot} will not know your iNat settings when you join a server it is on"
                    " until you have been added there."
                )

        await self.user_show_settings(ctx, config, "known")

    @user.command(name="list")
    @checks.admin_or_permissions(manage_roles=True)
    async def user_list(self, ctx, with_role: str = None):
        """List members with known iNat ids (mods only)."""
        if not ctx.guild:
            return

        # Avoid having to fully enumerate pages of discord/iNat user pairs
        # which would otherwise do expensive API calls if not in the cache
        # already just to get # of pages of member users:
        all_users = await self.config.all_users()
        config = self.config.guild(ctx.guild)
        user_projects = await config.user_projects()
        filter_role = None
        filter_role_id = None
        if with_role:
            if with_role == "active":
                filter_role_id = await config.active_role()
            elif with_role == "inactive":
                filter_role_id = await config.inactive_role()
            else:
                await ctx.send_help()
                return
        if with_role and not filter_role_id:
            await ctx.send(embed=make_embed(description=f"No {with_role} role set."))
            return

        if filter_role_id:
            filter_role = next(
                (role for role in ctx.guild.roles if role.id == filter_role_id), None
            )
            if not filter_role:
                await ctx.send(
                    embed=make_embed(
                        description=f"The {with_role} role is not a guild role: "
                        f"<@&{filter_role_id}>."
                    )
                )
                return

        responses = [
            await self.api.get_projects(int(project_id)) for project_id in user_projects
        ]
        projects = [
            UserProject.from_dict(response["results"][0])
            for response in responses
            if response
        ]

        if not self.user_cache_init.get(ctx.guild.id):
            await self.api.get_observers_from_projects(user_projects.keys())
            self.user_cache_init[ctx.guild.id] = True

        def emojis(user_id: int):
            emojis = [
                user_projects[str(project.project_id)]
                for project in projects
                if user_id in project.observed_by_ids()
            ]
            return " ".join(emojis)

        # TODO: Support lazy loading of pages of users (issues noted in comments below).
        all_names = [
            f"{dmember.mention} is {iuser.profile_link()} {emojis(iuser.user_id)}"
            async for (dmember, iuser) in self.user_table.get_member_pairs(
                ctx.guild, all_users
            )
            if not filter_role or filter_role in dmember.roles
        ]

        pages = ["\n".join(filter(None, names)) for names in grouper(all_names, 10)]

        if pages:
            pages_len = len(pages)  # Causes enumeration (works against lazy load).
            embeds = [
                make_embed(
                    title=f"Discord iNat user list (page {index} of {pages_len})",
                    description=page,
                )
                for index, page in enumerate(pages, start=1)
            ]
            # menu() does not support lazy load of embeds iterator.
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(
                f"No iNat login ids are known. Add them with `{ctx.clean_prefix}user add`."
            )
