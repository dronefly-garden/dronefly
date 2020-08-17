"""A cog for using the iNaturalist platform."""
from abc import ABC
from datetime import datetime
import re
import asyncio
import discord
import inflect
from redbot.core import checks, commands, Config
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, start_adding_reactions
from .api import INatAPI
from .base_classes import WWW_BASE_URL, PAT_OBS_LINK, User
from .checks import known_inat_user
from .commands.inat import CommandsInat
from .commands.last import CommandsLast
from .commands.place import CommandsPlace
from .commands.project import CommandsProject
from .commands.search import CommandsSearch
from .common import DEQUOTE, grouper
from .converters import (
    ContextMemberConverter,
    NaturalCompoundQueryConverter,
    QuotedContextMemberConverter,
)
from .embeds import make_embed, sorry
from .obs import get_obs_fields, maybe_match_obs
from .obs_query import INatObsQuery
from .places import INatPlaceTable
from .projects import INatProjectTable, UserProject
from .listeners import Listeners
from .search import INatSiteSearch
from .taxa import format_taxon_name, get_taxon, PAT_TAXON_LINK
from .taxon_query import INatTaxonQuery
from .users import INatUserTable, PAT_USER_LINK

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
class INatCog(
    Listeners,
    commands.Cog,
    CommandsInat,
    CommandsLast,
    CommandsPlace,
    CommandsProject,
    CommandsSearch,
    name="iNat",
    metaclass=CompositeMetaClass,
):
    """Commands provided by `inatcog`."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1607)
        self.api = INatAPI()
        self.p = inflect.engine()  # pylint: disable=invalid-name
        self.obs_query = INatObsQuery(self)
        self.taxon_query = INatTaxonQuery(self)
        self.user_table = INatUserTable(self)
        self.place_table = INatPlaceTable(self)
        self.project_table = INatProjectTable(self)
        self.site_search = INatSiteSearch(self)
        self.user_cache_init = {}
        self.reaction_locks = {}
        self.predicate_locks = {}

        self.config.register_global(home=97394, schema_version=1)  # North America
        self.config.register_guild(
            autoobs=False,
            dot_taxon=False,
            active_role=None,
            bot_prefixes=[],
            inactive_role=None,
            user_projects={},
            places={},
            home=97394,  # North America
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
            taxa = await self.taxon_query.query_taxa(ctx, taxa_list)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_map_embed(taxa))

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
                await ctx.send(embed=sorry(apology="I don't understand"))
                return

        try:
            compound_query = await NaturalCompoundQueryConverter.convert(ctx, query)
            obs = await self.obs_query.query_single_obs(ctx, compound_query)
        except (BadArgument, LookupError) as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

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
            taxa = await self.taxon_query.query_taxa(ctx, taxa_list)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await ctx.send(embed=await self.make_related_embed(ctx, taxa))

    @commands.command(aliases=["img", "photo"])
    async def image(self, ctx, *, taxon_query: NaturalCompoundQueryConverter):
        """Show default image for taxon query.

        `Aliases: [p]img`

        See `[p]help taxon` for `taxon_query` format."""
        try:
            self.check_taxon_query(ctx, taxon_query)
        except BadArgument as err:
            await ctx.send(embed=sorry(apology=err.args[0]))
            return

        try:
            filtered_taxon = await self.taxon_query.query_taxon(ctx, taxon_query)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await self.send_embed_for_taxon_image(ctx, filtered_taxon.taxon)

    @commands.command(aliases=["tab"])
    async def tabulate(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Show a table from iNaturalist data matching the query.

        • Only taxa can be tabulated. More kinds of table
          to be supported in future releases.
        • The row contents can be `from` or `by`. If both
          are given, what to tabulate is filtered by the
          `from` place, and the `by` person is the first row.
        e.g.
        ```
        ,tab fish from home
             -> per place (home listed; others react to add)
        ,tab fish by me
             -> per user (self listed; others react to add)
        ,tab fish from canada by me
             -> per user (self listed; others react to add)
                but only fish from canada are tabulated
        ```
        """
        if query.controlled_term or not query.main:
            await ctx.send(embed=sorry("I can't tabulate that yet."))
            return

        try:
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
            msg = await ctx.send(embed=await self.make_obs_counts_embed(filtered_taxon))
            start_adding_reactions(msg, ["#️⃣", "📝", "🏠", "📍"])
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

    @commands.group(aliases=["t"], invoke_without_command=True)
    async def taxon(self, ctx, *, query: NaturalCompoundQueryConverter):
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
           -> Prunella (Accentors)
        [p]taxon wtsp
           -> Zonotrichia albicollis (White-throated Sparrow)
        ```
        """
        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await ctx.send(embed=sorry(apology=err.args[0]))
            return

        try:
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(embed=sorry(apology=reason))
            return

        await self.send_embed_for_taxon(ctx, filtered_taxon)

    @taxon.command()
    async def bonap(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Show info from bonap.net for taxon."""
        try:
            self.check_taxon_query(ctx, query)
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
        except (BadArgument, LookupError) as err:
            await ctx.send(embed=sorry(apology=err.args[0]))
            return

        base_url = "http://bonap.net/MapGallery/County/"
        maps_url = "http://bonap.net/NAPA/TaxonMaps/Genus/County/"
        taxon = filtered_taxon.taxon
        name = re.sub(r" ", "%20", taxon.name)
        full_name = format_taxon_name(taxon)
        if taxon.rank == "genus":
            await ctx.send(
                f"{full_name} species maps: {maps_url}{name}\nGenus map: {base_url}Genus/{name}.png"
            )
        elif taxon.rank == "species":
            await ctx.send(f"{full_name} map:\n{base_url}{name}.png")
        else:
            await ctx.send(f"{full_name} must be a genus or species, not: {taxon.rank}")

    @taxon.command(name="means")
    async def taxon_means(
        self, ctx, place_query: str, *, query: NaturalCompoundQueryConverter
    ):
        """Show establishment means for taxon from the specified place."""
        try:
            place = await self.place_table.get_place(ctx.guild, place_query, ctx.author)
        except LookupError as err:
            await ctx.send(err)
            return
        place_id = place.place_id

        try:
            self.check_taxon_query(ctx, query)
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
        except (BadArgument, LookupError) as err:
            await ctx.send(embed=sorry(apology=err.args[0]))
            return
        taxon = filtered_taxon.taxon
        title = format_taxon_name(taxon, with_term=True)
        url = f"{WWW_BASE_URL}/taxa/{taxon.taxon_id}"
        full_taxon = await get_taxon(self, taxon.taxon_id, preferred_place_id=place_id)
        description = f"Establishment means unknown in: {place.display_name}"
        try:
            place_id = full_taxon.establishment_means.place.id
            find_means = (
                means for means in full_taxon.listed_taxa if means.place.id == place_id
            )
            means = next(find_means, full_taxon.establishment_means)
            if means:
                description = (
                    f"{means.emoji()}{means.description()} ({means.list_link()})"
                )
        except AttributeError:
            pass
        await ctx.send(embed=make_embed(title=title, url=url, description=description))

    @commands.command()
    async def tname(self, ctx, *, query: NaturalCompoundQueryConverter):
        """Show taxon name best matching the query.

        See `[p]help taxon` for help with the query.
        ```
        """

        try:
            self.check_taxon_query(ctx, query)
        except BadArgument as err:
            await ctx.send(embed=sorry(apology=err.args[0]))
            return

        try:
            filtered_taxon = await self.taxon_query.query_taxon(ctx, query)
        except LookupError as err:
            reason = err.args[0]
            await ctx.send(reason)
            return

        await ctx.send(filtered_taxon.taxon.name)

    @commands.command(aliases=["sp"])
    async def species(self, ctx, *, query: str):
        """Show species best matching the query.

        `Aliases: [p]sp, [p]t sp`

        See `[p]help taxon` for query help."""
        query_species = await NaturalCompoundQueryConverter.convert(
            ctx, f"species {query}"
        )
        await self.taxon(ctx, query=query_species)

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

    @commands.group(invoke_without_command=True)
    @known_inat_user()
    async def my(self, ctx, *, project: str):  # pylint: disable=invalid-name
        """Show your observations, species, & ranks for an iNat project."""
        await self.project_stats(ctx, project, user="me")

    @my.command(name="inatyear", invoke_without_command=True)
    @known_inat_user()
    async def my_inatyear(self, ctx, year: int = None):
        """Display the URL for your iNat year graphs.

        Where `year` is a valid year on or after 1950."""
        await self.user_inatyear(ctx, user="me", year=year)

    @commands.command()
    async def rank(
        self, ctx, project: str, *, user: str
    ):  # pylint: disable=invalid-name
        """Show observations, species, & ranks in an iNat project for a user."""
        await self.project_stats(ctx, project, user=user)

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

    @user.command(name="inatyear")
    @known_inat_user()
    async def user_inatyear(self, ctx, user: str = "me", year: int = None):
        """Display the URL for the user's iNat year graphs.

        Where `year` is a valid year on or after 1950, and `user` is a Discord user
        whose iNat profile is known to the bot."""

        this_year = datetime.today().year
        stats_year = this_year if year is None else year
        # 1950 experimentally determined (as of 2020-07-26) to be the floor year
        # as 1949 and earlier produces a 404 Error.
        if stats_year < 1950 or stats_year > this_year:
            await ctx.send(
                f"Sorry, iNat does not support stats for that year: `{stats_year}`"
            )
            return

        try:
            ctx_member = await ContextMemberConverter.convert(ctx, user)
            member = ctx_member.member
            inat_user = await self.user_table.get_user(member)
        except (BadArgument, LookupError) as err:
            await ctx.send(err)
            return

        await ctx.send(
            f"https://www.inaturalist.org/stats/{stats_year}/{inat_user.login}"
        )
