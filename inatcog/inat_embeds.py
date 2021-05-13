"""Module to handle iNat embed concerns."""

import asyncio
import contextlib
import datetime as dt
from io import BytesIO
import re
import textwrap
from typing import Union
from urllib.parse import parse_qs, urlencode, urlsplit
import discord
from discord import DMChannel, File
import html2markdown
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate
from .base_classes import (
    CompoundQuery,
    MEANS_LABEL_DESC,
    WWW_BASE_URL,
    PAT_OBS_LINK,
    PAT_OBS_QUERY,
    PAT_OBS_TAXON_LINK,
    Place,
    FilteredTaxon,
    Taxon,
    TaxonSummary,
)
from .common import LOG
from .converters import ContextMemberConverter
from .embeds import (
    format_items_for_embed,
    make_embed,
    MAX_EMBED_DESCRIPTION_LEN,
    NoRoomInDisplay,
)
from .interfaces import MixinMeta
from .maps import INatMapURL
from .projects import UserProject, ObserverStats
from .taxa import (
    format_place_taxon_counts,
    format_taxon_name,
    format_taxon_names,
    format_user_taxon_counts,
    get_taxon,
    get_taxon_fields,
    get_taxon_preferred_establishment_means,
    PAT_TAXON_LINK,
    TAXON_ID_LIFE,
    TAXON_COUNTS_HEADER,
    TAXON_COUNTS_HEADER_PAT,
    TAXON_PLACES_HEADER,
    TAXON_PLACES_HEADER_PAT,
    TAXON_NOTBY_HEADER,
    TAXON_NOTBY_HEADER_PAT,
    TAXON_IDBY_HEADER,
    TAXON_IDBY_HEADER_PAT,
)

HIERARCHY_PAT = re.compile(r".*?(?=>)", re.DOTALL)
NO_TAXONOMY_PAT = re.compile(r"(\n__.*)?$", re.DOTALL)
SHORT_DATE_PAT = re.compile(
    r"(^.*\d{1,2}:\d{2}(:\d{2})?(\s+(am|pm))?)(.*$)", flags=re.I
)
TAXONOMY_PAT = re.compile(r"in:(.*?(?=\n__.*$)|.*$)", re.DOTALL)

OBS_ID_PAT = re.compile(r"\(.*/observations/(?P<obs_id>\d+).*?\)")
PLACE_ID_PAT = re.compile(
    r"\n\[[0-9 \(\)]+\]\(.*?[\?\&]place_id=(?P<place_id>\d+).*?\)"
)
UNOBSERVED_BY_USER_ID_PAT = re.compile(
    r"\n\[[0-9 \(\)]+\]\(.*?[\?\&]unobserved_by_user_id=(?P<unobserved_by_user_id>\d+).*?\)",
)
ID_BY_USER_ID_PAT = re.compile(
    r"\n\[[0-9 \(\)]+\]\(.*?[\?\&]ident_user_id=(?P<ident_user_id>\d+).*?\)",
)
USER_ID_PAT = re.compile(r"\n\[[0-9 \(\)]+\]\(.*?[\?\&]user_id=(?P<user_id>\d+).*?\)")

REACTION_EMOJI = {
    "self": "#️⃣",
    "user": "📝",
    "home": "🏠",
    "place": "📍",
    "taxonomy": "🇹",
}
TAXON_REACTION_EMOJIS = list(
    map(REACTION_EMOJI.get, ["self", "user", "home", "place", "taxonomy"])
)
NO_PARENT_TAXON_REACTION_EMOJIS = list(
    map(REACTION_EMOJI.get, ["self", "user", "home", "place"])
)
OBS_REACTION_EMOJIS = NO_PARENT_TAXON_REACTION_EMOJIS


class INatEmbed(discord.Embed):
    """Base class for INat embeds."""

    @classmethod
    def from_discord_embed(cls, embed: discord.Embed):
        """Create an inat embed from discord.Embed argument."""
        return cls.from_dict(embed.to_dict())

    def inat_content_as_dict(self):
        """Return iNat content from embed as dict."""
        content = dict()
        content["listed_not_by_user_ids"] = self.listed_not_by_user_ids()
        content["listed_place_ids"] = self.listed_place_ids()
        content["listed_user_ids"] = self.listed_user_ids()
        content["listed_observation_ids"] = self.listed_observation_ids()
        content["place_id"] = self.place_id()
        content["taxon_id"] = self.taxon_id()
        content["user_id"] = self.user_id()
        content["project_id"] = self.project_id()
        return content

    def has_users(self):
        """Embed has a user counts table."""
        return bool(re.search(TAXON_COUNTS_HEADER_PAT, self.description or ""))

    def has_id_by_users(self):
        """Embed has an id by user counts table."""
        return bool(re.search(TAXON_IDBY_HEADER_PAT, self.description or ""))

    def has_not_by_users(self):
        """Embed has a not by user counts table."""
        return bool(re.search(TAXON_NOTBY_HEADER_PAT, self.description or ""))

    def has_observations(self):
        """Embed has listed observations (e.g. from `[p]search obs`)."""
        return bool(re.search(OBS_ID_PAT, self.description or ""))

    def has_places(self):
        """Embed has a place counts table."""
        # prevent misdetect as 'not by' (unobserved_by_user_id=# can have a place filter applied)
        return bool(re.search(TAXON_PLACES_HEADER_PAT, self.description or ""))

    def listed_id_by_user_ids(self):
        """Return listed users, if present."""
        if not self.has_id_by_users():
            return None

        return [int(id) for id in re.findall(ID_BY_USER_ID_PAT, self.description)]

    def listed_not_by_user_ids(self):
        """Return listed users, if present."""
        if not self.has_not_by_users():
            return None

        return [
            int(id) for id in re.findall(UNOBSERVED_BY_USER_ID_PAT, self.description)
        ]

    def listed_observation_ids(self):
        """Return listed observations, if present."""
        if not self.has_observations():
            return None

        return [int(id) for id in re.findall(OBS_ID_PAT, self.description)]

    def listed_place_ids(self):
        """Return listed places, if present."""
        if not self.has_places():
            return None

        return [int(id) for id in re.findall(PLACE_ID_PAT, self.description)]

    def listed_user_ids(self):
        """Return listed users, if present."""
        if not self.has_users():
            return None

        return [int(id) for id in re.findall(USER_ID_PAT, self.description)]

    def place_id(self):
        """Return place_id(s) from embed url, if present."""
        if not self.url:
            return None

        mat = re.match(PAT_OBS_QUERY, self.url)
        if not mat:
            return None
        url = urlsplit(mat["url"])
        params = parse_qs(url.query)
        place_id = params.get("place_id")
        return int(place_id[0]) if place_id else None

    def project_id(self):
        """Return project_id(s) from embed url, if present."""
        if not self.url:
            return None

        mat = re.match(PAT_OBS_QUERY, self.url)
        if not mat:
            return None
        url = urlsplit(mat["url"])
        params = parse_qs(url.query)
        project_id = params.get("project_id")
        return int(project_id[0]) if project_id else None

    def taxon_id(self):
        """Return taxon_id(s) from embed url, if present."""
        if not self.url:
            return None

        # Could be direct link to /taxa/# record
        mat = re.match(PAT_TAXON_LINK, self.url)
        if mat and mat["taxon_id"]:
            return int(mat["taxon_id"])
        # Otherwise, match from /observations query
        mat = re.match(PAT_OBS_QUERY, self.url)
        if not mat:
            return None
        url = urlsplit(mat["url"])
        params = parse_qs(url.query)
        taxon_id = params.get("taxon_id")
        return int(taxon_id[0]) if taxon_id else None

    def user_id(self):
        """Return user_id(s) from embed url, if present."""
        if not self.url:
            return None

        mat = re.match(PAT_OBS_QUERY, self.url)
        if not mat:
            return None
        url = urlsplit(mat["url"])
        params = parse_qs(url.query)
        user_id = params.get("user_id")
        return int(user_id[0]) if user_id else None


@format_items_for_embed
def format_taxon_names_for_embed(*args, **kwargs):
    """Format taxon names for output in embed."""
    return format_taxon_names(*args, **kwargs)


def format_taxon_title(rec):
    """Format taxon title."""
    title = format_taxon_name(rec)
    matched = rec.term
    if matched not in (rec.name, rec.common):
        title += f" ({matched})"
    return title


EMOJI = {
    "research": ":white_check_mark:",
    "needs_id": ":large_orange_diamond:",
    "casual": ":white_circle:",
    "fave": ":star:",
    "comment": ":speech_left:",
    "community": ":busts_in_silhouette:",
    "image": ":camera:",
    "sound": ":sound:",
    "ident": ":label:",
}


# Note: Consider broadening scope of module to INatHelpers to encompass things
# like check_taxon_query, or else split to own mixin.
class INatEmbeds(MixinMeta):
    """Provide embeds for iNatCog."""

    def check_taxon_query(self, ctx, query):
        """Check for valid taxon query."""
        if not isinstance(query, CompoundQuery):
            return
        if query.controlled_term or (query.user and query.place) or not query.main:
            args = ctx.message.content.split(" ", 1)[1]
            reason = (
                "I don't understand that query.\nPerhaps you meant one of:\n"
                f"`{ctx.clean_prefix}obs {args}`\n"
                f"`{ctx.clean_prefix}search obs {args}`"
            )
            raise BadArgument(reason)

    async def get_home(self, ctx):
        """Get configured home place."""
        user_config = self.config.user(ctx.author)
        home = await user_config.home()
        if not home:
            if ctx.guild:
                guild_config = self.config.guild(ctx.guild)
                home = await guild_config.home()
            else:
                home = await self.config.home()
        return home

    async def make_last_obs_embed(self, ctx, last):
        """Return embed for recent observation link."""
        if last.obs:
            obs = last.obs
            embed = await self.make_obs_embed(
                ctx.guild, obs, url=last.url, preview=False
            )
        else:
            embed = make_embed(url=last.url)
            mat = re.search(PAT_OBS_LINK, last.url)
            obs_id = int(mat["obs_id"])
            LOG.info("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        shared_by = f"· shared {last.ago}"
        if last.name:
            shared_by += f" by @{last.name}"
        embed.description = (
            f"{embed.description}\n\n{shared_by}" if embed.description else shared_by
        )
        return embed

    async def make_map_embed(self, taxa):
        """Return embed for an observation link."""
        title = format_taxon_names_for_embed(
            taxa, with_term=True, names_format="Range map for %s"
        )
        inat_map_url = INatMapURL(self.api)
        url = await inat_map_url.get_map_url_for_taxa(taxa)
        return make_embed(title=title, url=url)

    async def maybe_send_sound_url(self, channel, sound):
        """Given a URL to a sound, send it if it can be retrieved."""
        if (
            not isinstance(channel, DMChannel)
            and not channel.permissions_for(channel.guild.me).attach_files
        ):
            return
        async with self.api.session.get(sound.url) as response:
            try:
                sound_io = BytesIO(await response.read())
            except OSError:
                sound_io = None
        if sound_io:
            filename = response.url.name
            embed = make_embed()
            embed.set_footer(text=sound.attribution)
            await channel.send(embed=embed, file=File(sound_io, filename=filename))

    async def make_obs_counts_embed(self, arg):
        """Return embed for observation counts from place or by user."""
        title_params = {}
        formatted_counts = ""
        (taxon, user, place, unobserved_by, id_by, project) = arg

        if taxon:
            title = format_taxon_title(taxon)
            full_title = f"Observations of {title}"
        else:
            full_title = "Observations"
        description = ""
        if user:
            if place or project:
                if project:
                    full_title += f" in {project.title}"
                    title_params["project_id"] = project.project_id
                if place:
                    full_title += f" from {place.display_name}"
                    title_params["place_id"] = place.place_id
                formatted_counts = await format_user_taxon_counts(
                    self, user, taxon, **title_params
                )
                header = TAXON_COUNTS_HEADER
            elif unobserved_by or id_by:
                raise BadArgument("I can't tabulate that yet.")
            else:
                formatted_counts = await format_user_taxon_counts(self, user, taxon)
                header = TAXON_COUNTS_HEADER
        elif place or project:
            if unobserved_by:
                if project:
                    full_title += f" in {project.title}"
                    title_params["project_id"] = project.project_id
                if place:
                    full_title += f" from {place.display_name}"
                    title_params["place_id"] = place.place_id
                formatted_counts = await format_user_taxon_counts(
                    self, unobserved_by, taxon, unobserved=True, **title_params,
                )
                header = TAXON_NOTBY_HEADER
            elif id_by:
                if project:
                    full_title += f" in {project.title}"
                    title_params["project_id"] = project.project_id
                if place:
                    full_title += f" from {place.display_name}"
                    title_params["place_id"] = place.place_id
                formatted_counts = await format_user_taxon_counts(
                    self, id_by, taxon, ident=True, **title_params,
                )
                header = TAXON_IDBY_HEADER
            elif place:
                if project:
                    full_title += f" in {project.title}"
                    title_params["project_id"] = project.project_id
                formatted_counts = await format_place_taxon_counts(
                    self, place, taxon, **title_params
                )
                header = TAXON_PLACES_HEADER
            else:  # project
                full_title += f" in {project.title}"
                title_params["project_id"] = project.project_id

        elif unobserved_by:
            formatted_counts = await format_user_taxon_counts(
                self, unobserved_by, taxon, None, unobserved=True,
            )
            header = TAXON_NOTBY_HEADER
        elif id_by:
            formatted_counts = await format_user_taxon_counts(
                self, id_by, taxon, None, ident=True,
            )
            header = TAXON_IDBY_HEADER
        if formatted_counts:
            description = f"\n{header}\n{formatted_counts}"

        url = f"{WWW_BASE_URL}/observations"
        if taxon:
            title_params["taxon_id"] = taxon.taxon_id
        if title_params:
            url += "?" + urlencode(title_params)
        embed = make_embed(url=url, title=full_title, description=description,)
        return embed

    async def format_obs(
        self, obs, with_description=True, with_link=False, compact=False, with_user=True
    ):
        """Format an observation title & description."""

        def format_count(label, count):
            delim = " " if compact else ", "
            return f"{delim}{EMOJI[label]}" + (str(count) if count > 1 else "")

        def format_title(taxon, obs):
            title = ""
            if compact:
                title += f"{EMOJI[obs.quality_grade]} "
            if taxon:
                taxon_str = format_taxon_name(
                    taxon, with_rank=not compact, with_common=not compact,
                )
            else:
                taxon_str = "Unknown"
            if compact and with_link:
                link_url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
                taxon_str = f"[{taxon_str}]({link_url})"
            title += taxon_str
            if not compact:
                title += " " + EMOJI[obs.quality_grade]
                if obs.faves_count:
                    title += format_count("fave", obs.faves_count)
                if obs.comments_count:
                    title += format_count("comment", obs.comments_count)
            return title

        def format_summary(user, obs, taxon_summary):
            summary = ""
            if taxon_summary:
                means = taxon_summary.listed_taxon
                status = taxon_summary.conservation_status
                if status:
                    summary += f"Conservation Status: {status.description()} ({status.link()})\n"
                if means:
                    summary += f"{means.emoji()}{means.link()}\n"
            if compact:
                summary += f": {user.login if with_user else ''}"
            else:
                summary += "Observed by " + user.profile_link()
            if obs.obs_on:
                if compact:
                    if obs.obs_on.date() == dt.datetime.now().date():
                        if obs.time_obs:
                            obs_on = obs.time_obs.strftime("%I:%M%P")
                        else:
                            obs_on = "today"
                    elif obs.obs_on.year == dt.datetime.now().year:
                        obs_on = obs.obs_on.strftime("%d-%b")
                    else:
                        obs_on = obs.obs_on.strftime("%b-%Y")
                    summary += f" {obs_on}"
                else:
                    if obs.time_obs:
                        obs_on = obs.time_obs.strftime("%c")
                    else:
                        obs_on = obs.obs_on.strftime("%a %b %d %Y")
                    summary += " on " + obs_on
            if obs.obs_at:
                if compact:
                    name_width = len(taxon.name) if taxon else 7
                    place_width = 20 if with_user else 30
                    place_width += 18 - name_width
                    place_width = max(place_width, 20)
                    summary += " " + textwrap.shorten(
                        obs.obs_at, width=place_width, placeholder="…"
                    )
                else:
                    summary += " at " + obs.obs_at
            if compact:
                if obs.faves_count:
                    summary += format_count("fave", obs.faves_count)
                if obs.comments_count:
                    summary += format_count("comment", obs.comments_count)
                summary += format_media_counts(obs)
            if with_description and obs.description:
                # Contribute up to 10 lines from the description, and no more
                # than 500 characters:
                #
                # TODO: if https://bugs.launchpad.net/beautifulsoup/+bug/1873787 is
                # ever fixed, suppress the warning instead of adding this blank
                # as a workaround.
                text_description = html2markdown.convert(" " + obs.description)
                lines = text_description.split("\n", 11)
                description = "\n> %s" % "\n> ".join(lines[:10])
                if len(lines) > 10:
                    description += "\n> …"
                if len(description) > 500:
                    description = description[:498] + "…"
                summary += description + "\n"
            return summary

        def format_community_id(title, summary, obs, taxon_summary):
            idents_count = ""
            if obs.idents_count:
                if obs.community_taxon:
                    idents_count = (
                        f"{EMOJI['community']} ({obs.idents_agree}/{obs.idents_count})"
                    )
                else:
                    obs_idents_count = obs.idents_count if obs.idents_count > 1 else ""
                    idents_count = f"{EMOJI['ident']}{obs_idents_count}"
            if not compact:
                summary += f" [obs#: {obs.obs_id}]"
            if (
                not compact
                and obs.community_taxon
                and obs.community_taxon.taxon_id != obs.taxon.taxon_id
            ):
                if taxon_summary:
                    means = taxon_summary.listed_taxon
                    status = taxon_summary.conservation_status
                    if status:
                        status_link = (
                            f"\nConservation Status: {status.description()} "
                            f"({status.link()})"
                        )
                        status_link = f"\n{status.description()} ({status.link()})"
                    if means:
                        means_link = f"\n{means.emoji()}{means.link()}"
                else:
                    means_link = ""
                    status_link = ""
                summary = (
                    f"{format_taxon_name(obs.community_taxon)} "
                    f"{status_link}{idents_count}{means_link}\n\n" + summary
                )
            else:
                if idents_count:
                    if compact:
                        summary += " " + idents_count
                    else:
                        title += " " + idents_count
            return (title, summary)

        def format_media_counts(obs):
            media_counts = ""
            if obs.images:
                media_counts += format_count("image", len(obs.images))
            if obs.sounds:
                media_counts += format_count("sound", len(obs.sounds))
            return media_counts

        async def get_taxon_summary(obs, **kwargs):
            taxon_summary_raw = await self.api.get_obs_taxon_summary(
                obs.obs_id, **kwargs
            )
            taxon_summary = TaxonSummary.from_dict(taxon_summary_raw)
            means = None
            status = None
            if taxon_summary:
                listed = taxon_summary.listed_taxon
                if listed:
                    means = listed.establishment_means
                status = taxon_summary.conservation_status
            if means or status:
                return taxon_summary
            return None

        taxon = obs.taxon
        user = obs.user
        title = format_title(taxon, obs)
        taxon_summary = None
        community_taxon_summary = None
        if not compact:
            taxon_summary = await get_taxon_summary(obs)
            if (
                obs.community_taxon
                and obs.community_taxon.taxon_id != obs.taxon.taxon_id
            ):
                community_taxon_summary = await get_taxon_summary(obs, community=1)

        summary = format_summary(user, obs, taxon_summary)
        title, summary = format_community_id(
            title, summary, obs, community_taxon_summary
        )
        if not compact:
            title += format_media_counts(obs)
            if with_link:
                link_url = f"{WWW_BASE_URL}/observations/{obs.obs_id}"
                title = f"{title} [🔗]({link_url})"
        return (title, summary)

    async def make_obs_embed(self, guild, obs, url, preview: Union[bool, int] = True):
        """Return embed for an observation link."""
        # pylint: disable=too-many-locals

        def format_image_title_url(taxon, obs, num):
            if taxon:
                title = format_taxon_name(taxon)
            else:
                title = "Unknown"
            title += f" (Image {num} of {len(obs.images)})"
            mat = re.search(r"/photos/(\d+)", obs.images[num - 1].url)
            if mat:
                photo_id = mat[1]
                url = f"{WWW_BASE_URL}/photos/{photo_id}"
            else:
                url = None

            return (title, url)

        embed = make_embed(url=url)

        if obs:
            image_only = False
            error = None
            if preview:
                if isinstance(preview, bool):
                    image_number = 1
                else:
                    image_number = preview
                    image_only = True
                if obs.images and image_number >= 1 and image_number <= len(obs.images):
                    image = obs.images[image_number - 1]
                    embed.set_image(url=image.url)
                    embed.set_footer(text=image.attribution)
                else:
                    image_only = False
                    if obs.images:
                        num = len(obs.images)
                        error = (
                            f"*Image number out of range; must be between 1 and {num}.*"
                        )
                    else:
                        error = "*This observation has no images.*"

            if image_only:
                (title, url) = format_image_title_url(obs.taxon, obs, image_number)
                embed.title = title
                embed.url = url
            else:
                embed.title, summary = await self.format_obs(obs)
                if error:
                    summary += "\n" + error
                embed.description = summary
        else:
            mat = re.search(PAT_OBS_LINK, url)
            if mat:
                obs_id = int(mat["obs_id"])
                LOG.info("Observation not found for: %s", obs_id)
                embed.title = "No observation found for id: %s (deleted?)" % obs_id
            else:
                # If this happens, it's a bug (i.e. PAT_OBS_LINK should already match)
                LOG.info("Not an observation: %s", url)
                embed.title = "Not an observation:"
                embed.description = url

        return embed

    async def make_related_embed(self, ctx, taxa):
        """Return embed for related taxa."""
        names = format_taxon_names_for_embed(
            taxa, with_term=True, names_format="**The taxa:** %s"
        )
        taxa_iter = iter(taxa)
        first_taxon = next(taxa_iter)
        if len(taxa) == 1:
            taxon = first_taxon
        else:
            first_taxon_ancestor_ids = first_taxon.ancestor_ids
            first_set = set(first_taxon_ancestor_ids)
            remaining_sets = [set(taxon.ancestor_ids) for taxon in taxa_iter]
            common_ancestors = first_set.intersection(*remaining_sets)

            common_ancestor_indices = [
                first_taxon_ancestor_ids.index(ancestor_id)
                for ancestor_id in common_ancestors
            ]
            preferred_place_id = await self.get_home(ctx)
            if not common_ancestor_indices:
                taxon = await get_taxon(
                    self,
                    TAXON_ID_LIFE,
                    preferred_place_id=preferred_place_id,
                    refresh_cache=False,
                )
            else:
                common_ancestor_id = first_taxon_ancestor_ids[
                    max(common_ancestor_indices)
                ]
                taxon = await get_taxon(
                    self,
                    common_ancestor_id,
                    preferred_place_id=preferred_place_id,
                    refresh_cache=False,
                )

        description = (
            f"{names}\n**are related by {taxon.rank}**: {format_taxon_name(taxon)}"
        )

        return make_embed(title="Closest related taxon", description=description)

    async def make_image_embed(self, ctx, rec, index=1):
        """Make embed showing default image for taxon."""
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}")

        title = format_taxon_title(rec)
        image = None
        attribution = None

        embed.title = title
        if rec.thumbnail:
            if rec.image and index == 1:
                image = rec.image
                attribution = rec.image_attribution
            else:
                # - A taxon record may have a thumbnail but no image if the image
                #   is externally hosted (e.g. Flickr) and the record was created
                #   from /v1/taxa/autocomplete (i.e. only has a subset of the
                #   fields that /v1/taxa/# returns).
                # - Or the user may have requested other than the default image.
                # - In either case, we retrieve the full record via taxon_id so
                #   the image will be set from the full-quality original in
                #   taxon_photos.
                response = await self.api.get_taxa(rec.taxon_id)
                try:
                    taxon_photos_raw = response["results"][0]["taxon_photos"]
                except (TypeError, KeyError, IndexError):
                    taxon_photos_raw = None
                if taxon_photos_raw:
                    photos = (entry.get("photo") for entry in taxon_photos_raw)
                    (image, attribution) = next(
                        (
                            (photo.get("original_url"), photo.get("attribution", ""),)
                            for i, photo in enumerate(photos, 1)
                            if i == index
                        ),
                        (None, None),
                    )
        if image:
            embed.set_image(url=image)
            embed.set_footer(text=attribution)
        else:
            if index == 1:
                embed.description = "This taxon has no default photo."
            else:
                embed.description = f"This taxon does not have an image number {index}."

        return embed

    async def make_taxa_embed(self, ctx, arg, include_ancestors=True):
        """Make embed describing taxa record."""
        if isinstance(arg, FilteredTaxon):
            (taxon, user, place, _unobserved_by, _id_by, _project) = arg  # noqa: F841
        else:
            taxon = arg
            user = None
            place = None
            _unobserved_by = None  # noqa: F841
            _id_by = None  # noqa: F841
            _project = None  # noqa: F841
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{taxon.taxon_id}")
        p = self.p  # pylint: disable=invalid-name

        async def format_description(rec, status, means_fmtd):
            obs_cnt = rec.observations
            url = f"{WWW_BASE_URL}/observations?taxon_id={rec.taxon_id}&verifiable=any"
            obs_fmt = "[%d](%s)" % (obs_cnt, url)
            if status:
                # inflect statuses with single digits in them correctly
                first_word = re.sub(
                    r"[0-9]",
                    " {0} ".format(p.number_to_words(r"\1")),
                    status.description(),
                ).split()[0]
                article = p.a(first_word).split()[0]
                descriptor = (
                    f"{article} [{status.description()}]({status.url}) {rec.rank}"
                )
            else:
                descriptor = p.a(rec.rank)
            description = (
                f"is {descriptor} with {obs_fmt} {p.plural('observation', obs_cnt)}"
            )
            if means_fmtd:
                description += f" {means_fmtd}"
            return description

        async def format_ancestors(description, ancestors):
            if ancestors:
                ancestors = [get_taxon_fields(ancestor) for ancestor in ancestors]
                description += " in: " + format_taxon_names(ancestors, hierarchy=True)
            else:
                description += "."
            return description

        title = format_taxon_title(taxon)

        preferred_place_id = await self.get_home(ctx)
        if place:
            preferred_place_id = place.place_id
        full_record = (
            await self.api.get_taxa(
                taxon.taxon_id, preferred_place_id=preferred_place_id
            )
        )["results"][0]
        full_taxon = get_taxon_fields(full_record)
        means = await get_taxon_preferred_establishment_means(self, ctx, full_taxon)
        means_fmtd = ""
        if means and MEANS_LABEL_DESC.get(means.establishment_means):
            means_fmtd = f"{means.emoji()}{means.link()}"
        status = full_taxon.conservation_status
        # Workaround for neither conservation_status record has both status_name and url:
        # - /v1/taxa/autocomplete result has 'threatened' as status_name for
        #   status 't' polar bear, but no URL
        # - /v1/taxa/# for polar bear has the URL, but no status_name 'threatened'
        # - therefore, our grubby hack is to put them together here
        try:
            if not status.status_name and taxon.conservation_status.status_name:
                status.status_name = taxon.conservation_status.status_name
        except AttributeError:
            pass

        description = await format_description(taxon, status, means_fmtd)

        if include_ancestors:
            ancestors = full_record.get("ancestors")
            description = await format_ancestors(description, ancestors)

        if place:
            formatted_counts = await format_place_taxon_counts(self, place, taxon)
            if formatted_counts:
                description += f"\n{TAXON_PLACES_HEADER}\n{formatted_counts}"
        if user:
            formatted_counts = await format_user_taxon_counts(self, user, taxon)
            if formatted_counts:
                description += f"\n{TAXON_COUNTS_HEADER}\n{formatted_counts}"

        embed.title = title
        embed.description = description
        if taxon.thumbnail:
            embed.set_thumbnail(url=taxon.thumbnail)

        return embed

    async def get_user_project_stats(self, project_id, user, category: str = "obs"):
        """Get user's ranked obs & spp stats for a project."""

        async def get_unranked_count(*args, **kwargs):
            response = await self.api.get_observations(
                *args, project_id=project_id, user_id=user.user_id, per_page=0, **kwargs
            )
            if response:
                return response["total_results"]
            return "unknown"

        rank = "unranked"
        count = 0

        if category == "taxa":
            count = await get_unranked_count("species_counts")
            return (count, rank)

        kwargs = {}
        if category == "spp":
            kwargs["order_by"] = "species_count"
        # TODO: cache for a short while so users can compare stats but not
        # have to worry about stale data.
        response = await self.api.get_project_observers_stats(
            project_id=project_id, **kwargs
        )
        stats = [ObserverStats.from_dict(observer) for observer in response["results"]]
        if stats:
            rank = next(
                (
                    index + 1
                    for (index, d) in enumerate(stats)
                    if d.user_id == user.user_id
                ),
                None,
            )
            if rank:
                ranked = stats[rank - 1]
                count = (
                    ranked.species_count
                    if category == "spp"
                    else ranked.observation_count
                )
            else:
                if category == "spp":
                    count = await get_unranked_count("species_counts", hrank="species")
                else:
                    count = await get_unranked_count()  # obs
                rank = ">500" if count > 0 else "unranked"
        return (count, rank)

    async def get_user_server_projects_stats(self, ctx, user):
        """Get a user's stats for the server's user projects."""
        user_projects = await self.config.guild(ctx.guild).user_projects() or {}
        project_ids = list(map(int, user_projects))
        projects = await self.api.get_projects(project_ids, refresh_cache=True)
        stats = []
        for project_id in project_ids:
            if project_id not in projects:
                continue
            user_project = UserProject.from_dict(projects[project_id]["results"][0])
            if user.user_id in user_project.observed_by_ids():
                abbrev = user_projects[str(project_id)]
                obs_stats = await self.get_user_project_stats(project_id, user)
                spp_stats = await self.get_user_project_stats(
                    project_id, user, category="spp"
                )
                taxa_stats = await self.get_user_project_stats(
                    project_id, user, category="taxa"
                )
                stats.append((project_id, abbrev, obs_stats, spp_stats, taxa_stats))
        return stats

    async def make_user_embed(self, ctx, member, user):
        """Make an embed for user including user stats."""
        embed = make_embed(description=f"{member.mention} is {user.profile_link()}")
        project_stats = await self.get_user_server_projects_stats(ctx, user)
        for project_id, abbrev, obs_stats, spp_stats, taxa_stats in project_stats:
            obs_count, _obs_rank = obs_stats
            spp_count, _spp_rank = spp_stats
            taxa_count, _taxa_rank = taxa_stats
            url = (
                f"{WWW_BASE_URL}/observations?project_id={project_id}"
                f"&user_id={user.user_id}"
            )
            obs_url = f"{url}&view=observations"
            spp_url = f"{url}&view=species&verifiable=any&hrank=species"
            taxa_url = f"{url}&view=species&verifiable=any"
            fmt = (
                f"[{obs_count}]({obs_url}) / [{spp_count}]({spp_url}) / "
                f"[{taxa_count}]({taxa_url})"
            )
            embed.add_field(
                name=f"Obs / Spp / Leaf taxa ({abbrev})", value=fmt, inline=True
            )
        ids = user.identifications_count
        url = f"[{ids}]({WWW_BASE_URL}/identifications?user_id={user.user_id})"
        embed.add_field(name="Ids", value=url, inline=True)
        return embed

    async def make_stats_embed(self, member, user, project):
        """Make an embed for user showing stats for a project."""
        embed = make_embed(
            title=project.title, url=project.url, description=member.mention
        )
        project_id = project.project_id
        obs_count, obs_rank = await self.get_user_project_stats(project_id, user)
        spp_count, spp_rank = await self.get_user_project_stats(
            project_id, user, category="spp"
        )
        taxa_count, _taxa_rank = await self.get_user_project_stats(
            project_id, user, category="taxa"
        )
        url = (
            f"{WWW_BASE_URL}/observations?project_id={project.project_id}"
            f"&user_id={user.user_id}"
        )
        obs_url = f"{url}&view=observations"
        spp_url = f"{url}&view=species&verifiable=any&hrank=species"
        taxa_url = f"{url}&view=species&verifiable=any"
        fmt = (
            f"[{obs_count}]({obs_url}) (#{obs_rank}) / [{spp_count}]({spp_url}) (#{spp_rank}) / "
            f"[{taxa_count}]({taxa_url})"
        )
        embed.add_field(
            name="Obs (rank) / Spp (rank) / Leaf taxa", value=fmt, inline=True
        )
        return embed

    def add_obs_reaction_emojis(self, msg):
        """Add obs embed reaction emojis."""
        start_adding_reactions(msg, OBS_REACTION_EMOJIS)

    def add_taxon_reaction_emojis(
        self, msg, filtered_taxon: Union[FilteredTaxon, Taxon], taxonomy=True
    ):
        """Add taxon embed reaction emojis."""
        if isinstance(filtered_taxon, FilteredTaxon):
            (
                taxon,
                _user,
                _place,
                _unobserved_by,
                _id_by,
                _project,
            ) = filtered_taxon  # noqa: F841
        else:
            taxon = filtered_taxon
        if taxonomy and len(taxon.ancestor_ids) > 2:
            reaction_emojis = TAXON_REACTION_EMOJIS
        else:
            reaction_emojis = NO_PARENT_TAXON_REACTION_EMOJIS
        start_adding_reactions(msg, reaction_emojis)

    async def send_embed_for_taxon_image(
        self, ctx, filtered_taxon: Union[FilteredTaxon, Taxon], index=1
    ):
        """Make embed for taxon image & send."""
        msg = await ctx.send(
            embed=await self.make_image_embed(ctx, filtered_taxon, index)
        )
        # TODO: drop taxonomy=False when #139 is fixed
        # - This workaround omits Taxonomy reaction to make it less likely a
        #   user will break the display; they can use `,last t` to get the taxon
        #   display with taxonomy instead, if they need it.
        # - Note: a tester may still manually add the :regional_indicator_t:
        #   reaction to test the feature in its current, broken state.
        self.add_taxon_reaction_emojis(msg, filtered_taxon, taxonomy=False)

    async def send_embed_for_taxon(self, ctx, filtered_taxon, include_ancestors=True):
        """Make embed for taxon & send."""
        msg = await ctx.send(
            embed=await self.make_taxa_embed(
                ctx, filtered_taxon, include_ancestors=include_ancestors
            )
        )
        self.add_taxon_reaction_emojis(msg, filtered_taxon)

    def get_inat_url_ids(self, url):
        """Match taxon_id & optional place_id/user_id from an iNat taxon or obs URL."""
        taxon_id = None
        place_id = None
        inat_user_id = None
        mat = re.match(PAT_TAXON_LINK, url)
        if not mat:
            mat = re.match(PAT_OBS_TAXON_LINK, url)
            if mat:
                place_id = mat["place_id"]
                inat_user_id = mat["user_id"]
        if mat:
            taxon_id = mat["taxon_id"]
        return (taxon_id, place_id, inat_user_id)

    async def maybe_update_member(
        self, msg: discord.Message, member: discord.Member, action: str
    ):
        """Add or remove member count in the embed if valid."""
        try:
            inat_user = await self.user_table.get_user(member)
            counts_pat = r"(\n|^)\[[0-9 \(\)]+\]\(.*?\) " + inat_user.login
        except LookupError:
            return

        inat_embed = msg.embeds[0]
        if inat_embed.taxon_id():
            taxon = await get_taxon(self, inat_embed.taxon_id(), refresh_cache=False)
        else:
            taxon = None
        # Observed by count add/remove for taxon:
        await self.edit_totals_locked(msg, taxon, inat_user, action, counts_pat)

    async def maybe_update_place(
        self,
        msg: discord.Message,
        user: discord.Member,
        action: str,
        place: Place = None,
    ):
        """Add or remove place count in the embed if valid."""
        try:
            await self.user_table.get_user(user)
        except LookupError:
            return

        update_place = None
        if place is None:
            config = self.config.user(user)
            home = await config.home()
            if not home:
                return

            try:
                update_place = await self.place_table.get_place(msg.guild, home, user)
            except LookupError:
                return
        else:
            update_place = place

        inat_embed = msg.embeds[0]
        place_counts_pat = r"(\n|^)\[[0-9 \(\)]+\]\(.*?\) " + re.escape(
            update_place.display_name
        )
        if inat_embed.taxon_id():
            taxon = await get_taxon(self, inat_embed.taxon_id(), refresh_cache=False)
        else:
            taxon = None
        await self.edit_place_totals_locked(
            msg, taxon, update_place, action, place_counts_pat
        )

    async def query_locked(self, msg, user, prompt, timeout):
        """Query member with user lock."""

        async def is_query_response(response):
            # so we can ignore '[p]cancel` too. doh!
            # - FIXME: for the love of Pete, why does response.content
            #   contain the cancel command? then we could remove this
            #   foolishness.
            prefixes = await self.bot.get_valid_prefixes(msg.guild)
            config = self.config.guild(msg.guild)
            other_bot_prefixes = await config.bot_prefixes()
            all_prefixes = prefixes + other_bot_prefixes
            ignore_prefixes = r"|".join(re.escape(prefix) for prefix in all_prefixes)
            prefix_pat = re.compile(r"^({prefixes})".format(prefixes=ignore_prefixes))
            return not re.match(prefix_pat, response.content)

        response = None
        if user.id not in self.predicate_locks:
            self.predicate_locks[user.id] = asyncio.Lock()
        lock = self.predicate_locks[user.id]
        if lock.locked():
            # An outstanding query for this user hasn't been answered.
            # They must answer it or the timeout must expire before they
            # can start another interaction.
            return

        async with self.predicate_locks[user.id]:
            query = await msg.channel.send(prompt)
            try:
                response = await self.bot.wait_for(
                    "message_without_command",
                    check=MessagePredicate.same_context(channel=msg.channel, user=user),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
                    return

            # Cleanup messages:
            if await is_query_response(response):
                try:
                    await msg.channel.delete_messages((query, response))
                except (discord.HTTPException, AttributeError):
                    # In case the bot can't delete other users' messages:
                    with contextlib.suppress(discord.HTTPException):
                        await query.delete()
            else:
                # Response was a command for another bot: just delete the prompt
                # and discard the response.
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
                response = None
        return response

    async def maybe_update_member_by_name(
        self, ctx, msg: discord.Message, user: discord.Member
    ):
        """Prompt for a member by name and update the embed if provided & valid."""
        try:
            await self.user_table.get_user(user)
        except LookupError:
            return
        response = await self.query_locked(
            msg,
            user,
            "Add or remove which member (you have 15 seconds to answer)?",
            15,
        )
        if response:
            try:
                who = await ContextMemberConverter.convert(ctx, response.content)
            except discord.ext.commands.errors.BadArgument as error:
                error_msg = await msg.channel.send(error)
                await asyncio.sleep(15)
                with contextlib.suppress(discord.HTTPException):
                    await error_msg.delete()
                return

            await self.maybe_update_member(msg, who.member, "toggle")

    async def maybe_update_place_by_name(
        self, msg: discord.Message, user: discord.Member
    ):
        """Prompt user for place by name and update the embed if provided & valid."""
        try:
            await self.user_table.get_user(user)
        except LookupError:
            return
        response = await self.query_locked(
            msg, user, "Add or remove which place (you have 15 seconds to answer)?", 15,
        )
        if response:
            try:
                place = await self.place_table.get_place(
                    msg.guild, response.content, user
                )
            except LookupError as error:
                error_msg = await msg.channel.send(error)
                await asyncio.sleep(15)
                with contextlib.suppress(discord.HTTPException):
                    await error_msg.delete()
                return

            await self.maybe_update_place(msg, user, "toggle", place)

    async def maybe_update_taxonomy(self, message):
        """Update taxonomy in taxon embed, if applicable."""
        embeds = message.embeds
        inat_embed = embeds[0]
        description = inat_embed.description or ""
        new_description = re.sub(TAXONOMY_PAT, "", description)
        if new_description == description:
            response = await self.api.get_taxa(
                inat_embed.taxon_id(), refresh_cache=False
            )
            full_taxon_raw = response["results"][0]
            if full_taxon_raw:
                ancestors_raw = full_taxon_raw.get("ancestors")
                if not ancestors_raw:
                    return
                ancestors = [get_taxon_fields(ancestor) for ancestor in ancestors_raw]
                formatted_names = format_taxon_names(ancestors, hierarchy=True)
                hierarchy = re.sub(HIERARCHY_PAT, "", formatted_names, 1)
                new_description = re.sub(
                    NO_TAXONOMY_PAT, " in:\n" + hierarchy + r"\1", description, 1,
                )
            else:
                return
        inat_embed.description = new_description
        await message.edit(embed=inat_embed)

    async def update_totals(
        self, description, taxon, inat_user, action, inat_embed, counts_pat,
    ):
        """Update the totals for the embed."""
        unobserved = inat_embed.has_not_by_users()
        ident = inat_embed.has_id_by_users()
        place_id = inat_embed.place_id()
        project_id = inat_embed.project_id()
        if not (unobserved or ident):
            # Add/remove always results in a change to totals, so remove:
            description = re.sub(
                r"\n\[[0-9 \(\)]+?\]\(.*?\) \*total\*", "", description
            )

        matches = re.findall(
            r"\n\[[0-9 \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
        )
        if action == "remove":
            # Remove the header if last one and the user's count:
            if len(matches) == 1:
                if unobserved:
                    description = re.sub(TAXON_NOTBY_HEADER_PAT, "", description)
                elif ident:
                    description = re.sub(TAXON_IDBY_HEADER_PAT, "", description)
                else:
                    description = re.sub(TAXON_COUNTS_HEADER_PAT, "", description)
            description = re.sub(counts_pat + r".*?((?=\n)|$)", "", description)
        else:
            # Add the header if first one and the user's count:
            if not matches:
                if unobserved:
                    # not currently possible (new :hash: reaction starts 'by' embed)
                    description += "\n" + TAXON_NOTBY_HEADER
                elif ident:
                    # not currently possible (new :hash: reaction starts 'by' embed)
                    description += "\n" + TAXON_IDBY_HEADER
                else:
                    description += "\n" + TAXON_COUNTS_HEADER
            formatted_counts = await format_user_taxon_counts(
                self, inat_user, taxon, place_id, unobserved, ident, project_id
            )
            description += "\n" + formatted_counts

        if not (unobserved or ident):
            matches = re.findall(
                r"\n\[[0-9 \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
            )
            # Total added only if more than one user:
            if len(matches) > 1:
                formatted_counts = await format_user_taxon_counts(
                    self, ",".join(matches), taxon, place_id, project_id=project_id
                )
                description += f"\n{formatted_counts}"
                return description
        return description

    async def edit_totals_locked(
        self, msg, taxon, inat_user, action, counts_pat,
    ):
        """Update totals for message locked."""
        if msg.id not in self.reaction_locks:
            self.reaction_locks[msg.id] = asyncio.Lock()
        async with self.reaction_locks[msg.id]:
            # Refetch the message because it may have changed prior to
            # acquiring lock
            try:
                msg = await msg.channel.fetch_message(msg.id)
            except discord.errors.NotFound:
                return  # message has been deleted, nothing left to do
            embeds = msg.embeds
            inat_embed = INatEmbed.from_discord_embed(embeds[0])
            description = inat_embed.description or ""
            mat = re.search(counts_pat, description)
            if action == "toggle":
                action = "remove" if mat else "add"

            if (mat and (action == "remove")) or (not mat and (action == "add")):
                description = await self.update_totals(
                    description, taxon, inat_user, action, inat_embed, counts_pat,
                )
                if len(description) > MAX_EMBED_DESCRIPTION_LEN:
                    raise NoRoomInDisplay(
                        "No more room for additional users in this display."
                    )
                inat_embed.description = description
                if not inat_embed.has_not_by_users() and re.search(
                    r"\*total\*", inat_embed.description
                ):
                    inat_embed.set_footer(
                        text="User counts may not add up to "
                        "the total if they changed since they were added. "
                        "Remove, then add them again to update their counts."
                    )
                else:
                    inat_embed.set_footer(text="")
                await msg.edit(embed=inat_embed)

    async def update_place_totals(
        self, description, taxon, place, action, inat_embed, place_counts_pat
    ):
        """Update the place totals for the embed."""
        # Add/remove always results in a change to totals, so remove:
        description = re.sub(r"\n\[[0-9 \(\)]+?\]\(.*?\) \*total\*", "", description)

        matches = re.findall(r"\n\[[0-9 \(\)]+\]\(.*?\) (.*?)(?=\n|$)", description)
        if action == "remove":
            # Remove the header if last one and the place's count:
            if len(matches) == 1:
                description = re.sub(TAXON_PLACES_HEADER_PAT, "", description)
            description = re.sub(place_counts_pat + r".*?((?=\n)|$)", "", description)
        else:
            # Add the header if first one and the place's count:
            if not matches:
                description += "\n" + TAXON_PLACES_HEADER
            formatted_counts = await format_place_taxon_counts(
                self,
                place,
                taxon,
                inat_embed.user_id(),
                project_id=inat_embed.project_id(),
            )
            description += "\n" + formatted_counts

        matches = re.findall(
            r"\n\[[0-9 \(\)]+\]\(.*?\?place_id=(?P<place_id>\d+)&.*?\)", description,
        )
        # Total added only if more than one place:
        if len(matches) > 1:
            formatted_counts = await format_place_taxon_counts(
                self,
                ",".join(matches),
                taxon,
                inat_embed.user_id(),
                project_id=inat_embed.project_id(),
            )
            description += f"\n{formatted_counts}"
            return description
        return description

    async def edit_place_totals_locked(
        self, msg, taxon, place, action, place_counts_pat
    ):
        """Update place totals for message locked."""
        if msg.id not in self.reaction_locks:
            self.reaction_locks[msg.id] = asyncio.Lock()
        async with self.reaction_locks[msg.id]:
            # Refetch the message because it may have changed prior to
            # acquiring lock
            try:
                msg = await msg.channel.fetch_message(msg.id)
            except discord.errors.NotFound:
                return  # message has been deleted, nothing left to do
            embeds = msg.embeds
            inat_embed = INatEmbed.from_discord_embed(embeds[0])
            description = inat_embed.description or ""
            mat = re.search(place_counts_pat, description)
            if action == "toggle":
                action = "remove" if mat else "add"

            if (mat and (action == "remove")) or (not mat and (action == "add")):
                description = await self.update_place_totals(
                    description, taxon, place, action, inat_embed, place_counts_pat
                )
                if len(description) > MAX_EMBED_DESCRIPTION_LEN:
                    raise NoRoomInDisplay(
                        "No more room for additional places in this display."
                    )
                inat_embed.description = description
                if re.search(r"\*total\*", inat_embed.description):
                    inat_embed.set_footer(
                        text="Non-overlapping place counts may not add up to "
                        "the total if they changed since they were added. "
                        "Remove, then add them again to update their counts."
                    )
                else:
                    inat_embed.set_footer(text="")
                await msg.edit(embed=inat_embed)
