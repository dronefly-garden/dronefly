"""Module to handle iNat embed concerns."""
import asyncio
import contextlib
import copy
import datetime as dt
from io import BytesIO
import logging
import re
from typing import Optional, Union
from urllib.parse import parse_qs, urlsplit

import discord
from discord import DMChannel, File
from dronefly.core.constants import RANK_LEVELS
from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.formatters.discord import format_user_link
from dronefly.core.formatters.generic import (
    format_taxon_conservation_status,
    format_taxon_establishment_means,
    format_taxon_name,
    format_taxon_names,
    TaxonFormatter as CoreTaxonFormatter,
)
from dronefly.core.parsers.url import (
    MARKDOWN_LINK,
    PAT_OBS_LINK,
    PAT_OBS_QUERY,
    PAT_OBS_TAXON_LINK,
    PAT_TAXON_LINK,
)
from dronefly.core.query.query import EMPTY_QUERY, Query, QueryResponse, TaxonQuery
import html2markdown
import inflect
from pyinaturalist.constants import JsonResponse, ROOT_TAXON_ID
from pyinaturalist.models import IconPhoto, Place, Taxon, TaxonSummary, User, UserCount
from redbot.core.commands import BadArgument, Context
from redbot.core.utils.predicates import MessagePredicate

from ..embeds.common import (
    add_reactions_with_cancel,
    format_items_for_embed,
    make_embed,
    MAX_EMBED_DESCRIPTION_LEN,
    MAX_EMBED_FILE_LEN,
    NoRoomInDisplay,
)
from ..interfaces import MixinMeta
from ..maps import INatMapURL
from ..obs import obs_count_community_id, obs_get_sounds
from ..projects import UserProject
from ..taxa import (
    format_place_taxon_counts,
    format_user_taxon_counts,
    get_taxon,
    TAXON_COUNTS_HEADER,
    TAXON_COUNTS_HEADER_PAT,
    TAXON_PLACES_HEADER,
    TAXON_PLACES_HEADER_PAT,
    TAXON_NOTBY_HEADER,
    TAXON_NOTBY_HEADER_PAT,
    TAXON_IDBY_HEADER,
    TAXON_IDBY_HEADER_PAT,
)
from ..utils import get_lang, has_valid_user_config, obs_url_from_v1

logger = logging.getLogger("red.dronefly." + __name__)

HIERARCHY_PAT = re.compile(r".*?(?=>)", re.DOTALL)
NO_TAXONOMY_PAT = re.compile(r"(\n__.*)?$", re.DOTALL)
SHORT_DATE_PAT = re.compile(
    r"(^.*\d{1,2}:\d{2}(:\d{2})?(\s+(am|pm))?)(.*$)", flags=re.I
)
TAXONOMY_PAT = re.compile(r"in:(?P<taxonomy>.*?(?=\n__.*$)|.*$)", re.DOTALL)

OBS_ID_PAT = re.compile(r"\(.*/observations/(?P<obs_id>\d+).*?\)")
PLACE_ID_PAT = re.compile(
    r"\n\[[0-9, \(\)]+\]\(.*?[\?\&]place_id=(?P<place_id>\d+).*?\)"
)
UNOBSERVED_BY_USER_ID_PAT = re.compile(
    r"\n\[[0-9, \(\)]+\]\(.*?[\?\&]unobserved_by_user_id=(?P<unobserved_by_user_id>\d+).*?\)",
)
ID_BY_USER_ID_PAT = re.compile(
    r"\n\[[0-9, \(\)]+\]\(.*?[\?\&]ident_user_id=(?P<ident_user_id>\d+).*?\)",
)
USER_ID_PAT = re.compile(r"\n\[[0-9 \(\)]+\]\(.*?[\?\&]user_id=(?P<user_id>\d+).*?\)")

REACTION_EMOJI = {
    "self": "\N{BUST IN SILHOUETTE}",
    "user": "\N{BUSTS IN SILHOUETTE}",
    "home": "\N{HOUSE BUILDING}",
    "place": "\N{EARTH GLOBE EUROPE-AFRICA}",
    "taxonomy": "\N{REGIONAL INDICATOR SYMBOL LETTER T}",
}
TAXON_REACTION_EMOJIS = list(map(REACTION_EMOJI.get, ["self", "user", "taxonomy"]))
NO_PARENT_TAXON_REACTION_EMOJIS = list(map(REACTION_EMOJI.get, ["self", "user"]))
TAXON_PLACE_REACTION_EMOJIS = list(
    map(REACTION_EMOJI.get, ["home", "place", "taxonomy"])
)
NO_PARENT_TAXON_PLACE_REACTION_EMOJIS = list(map(REACTION_EMOJI.get, ["home", "place"]))
OBS_REACTION_EMOJIS = NO_PARENT_TAXON_REACTION_EMOJIS
OBS_PLACE_REACTION_EMOJIS = NO_PARENT_TAXON_PLACE_REACTION_EMOJIS

# pylint: disable=no-member, assigning-non-slot
# - See https://github.com/PyCQA/pylint/issues/981

p = inflect.engine()


class TaxonFormatter(CoreTaxonFormatter):
    def format(
        self,
        with_ancestors: bool = True
    ):
        """Format the taxon as markdown.

        with_ancestors: bool, optional
            When False, omit ancestors
        """
        description = self.format_taxon_description()
        if with_ancestors and self.taxon.ancestors:
            description += (
                " in: "
                + format_taxon_names(
                    self.taxon.ancestors,
                    hierarchy=True,
                    max_len=self.max_len,
                )
            )
        else:
            description += "."
        return description


class QueryResponseFormatter(TaxonFormatter):
    def __init__(
            self,
            query_response: QueryResponse,
            observations: JsonResponse=None,
            **kwargs,
        ):
        super().__init__(**kwargs)
        self.query_response = query_response
        self.observations = observations
        self.obs_count_formatter = self.ObsCountFormatter(query_response.taxon, query_response, observations)

    class ObsCountFormatter(TaxonFormatter.ObsCountFormatter):
        def __init__(self, taxon: Taxon, query_response: QueryResponse=None, observations: JsonResponse=None):
            super().__init__(taxon)
            self.query_response = query_response
            self.observations = observations

        def count(self):
            if self.observations:
                count = self.observations.get('total_results')
            else:
                count = self.taxon.observations_count
            return count

        def url(self):
            return obs_url_from_v1(self.query_response.obs_args())

        def description(self):
            count = self.link()
            count_str = "uncounted" if count is None else str(count)
            adjectives = self.query_response.adjectives # rg, nid, etc.
            query_without_taxon = copy.copy(self.query_response)
            query_without_taxon.taxon = None
            description = [
                count_str,
                *adjectives,
                p.plural('observation', count),
            ]
            filter = query_without_taxon.obs_query_description(with_adjectives=False) # place, prj, etc.
            if filter:
                description.append(filter)
            return " ".join(description)


class INatEmbed(discord.Embed):
    """Base class for INat embeds."""

    taxon_url: str = None
    obs_url: str = None
    taxonomy: str = None
    params: dict = {}

    @classmethod
    def from_discord_embed(cls, embed: discord.Embed):
        """Create an iNat embed from a discord.Embed."""
        return cls.from_dict(embed.to_dict())

    @classmethod
    def from_dict(cls, data: dict):
        """Create an iNat embed from a dict."""
        inat_embed = super(cls, INatEmbed).from_dict(data)
        inat_embed.obs_url = inat_embed.get_observations_url()
        inat_embed.taxon_url, taxon_id = inat_embed.get_taxon_url()
        inat_embed.taxonomy = inat_embed.get_taxonomy()
        inat_embed.params = inat_embed.get_params(taxon_id)
        return inat_embed

    def __init__(self):
        super().__init__()
        self.obs_url = self.get_observations_url()
        self.taxon_url, taxon_id = self.get_taxon_url()
        self.taxonomy = self.get_taxonomy()
        self.params = self.get_params(taxon_id)

    def get_observations_url(self):
        """Return observations url, if present."""
        if self.url:
            if re.match(PAT_OBS_QUERY, self.url):
                return self.url
        # url may be in first link of body (i.e. observations count)
        mat = re.search(MARKDOWN_LINK, self.description) if self.description else None
        if mat:
            mat = re.search(PAT_OBS_QUERY, mat["url"])
            if mat:
                return mat["url"]
        return None

    def get_taxon_url(self):
        """Return taxon url and the taxon_id in it, if present."""
        if self.url:
            mat = re.match(PAT_TAXON_LINK, self.url)
            if mat:
                return (mat["url"], mat["taxon_id"])
        # url may be in first link of body (i.e. Taxon in an observations embed)
        mat = re.search(MARKDOWN_LINK, self.description) if self.description else None
        if mat:
            mat = re.search(PAT_TAXON_LINK, mat["url"])
            if mat:
                return (mat["url"], mat["taxon_id"])
        return (None, None)

    def get_taxonomy(self):
        """Return taxonomy for the embed."""
        if not self.description:
            return ""
        mat = re.search(TAXONOMY_PAT, self.description)
        if mat:
            return mat["taxonomy"]
        return ""

    def get_params(self, taxon_id=None):
        """Return recognized params for the embed."""
        url = self.obs_url or self.taxon_url or self.url
        if self.params or not url:
            return self.params

        params = parse_qs(urlsplit(url).query)
        # TODO: we should leave these as-is and use urlencode with doseq=True
        # instead to put the URL back together later
        new_params = {key: ",".join(params[key]) for key in params}
        if taxon_id:
            new_params["taxon_id"] = taxon_id
        return new_params

    def inat_content_as_dict(self):
        """Return iNat content from embed as dict."""
        content = dict()
        content["listed_id_by_user_ids"] = self.listed_id_by_user_ids()
        content["listed_not_by_user_ids"] = self.listed_not_by_user_ids()
        content["listed_place_ids"] = self.listed_place_ids()
        content["listed_user_ids"] = self.listed_user_ids()
        content["listed_observation_ids"] = self.listed_observation_ids()
        content["place_id"] = self.place_id()
        content["taxon_id"] = self.taxon_id()
        content["user_id"] = self.user_id()
        content["unobserved_by_user_id"] = self.unobserved_by_user_id()
        content["not_user_id"] = self.not_user_id()
        content["ident_user_id"] = self.ident_user_id()
        content["project_id"] = self.project_id()
        content["taxon_url"] = self.taxon_url
        content["obs_url"] = self.obs_url
        content["params"] = self.params
        content["taxonomy"] = self.taxonomy
        content["query"] = str(self.query())
        return content

    def query(self, query: Query = EMPTY_QUERY):  # Query
        """Produce a query from embed, merging new query if given."""

        main = None
        if query.main and query.main.terms and query.main.terms[0] == "any":
            main = query.main
        if not main and self.taxon_id():
            main = TaxonQuery(taxon_id=self.taxon_id())
        user = query.user or self.user_id()
        id_by = query.id_by or self.ident_user_id()
        unobserved_by = query.unobserved_by or self.unobserved_by_user_id()
        except_by = query.except_by or self.not_user_id()
        place = query.place or self.place_id()
        project = query.project or self.project_id()
        controlled_term = query.controlled_term or self.controlled_term()
        query = Query(
            main=main,
            user=user,
            id_by=id_by,
            unobserved_by=unobserved_by,
            except_by=except_by,
            place=place,
            project=project,
            controlled_term=controlled_term,
        )
        return query

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
        """Return place_id(s) from embed, if present."""
        place_id = self.params.get("place_id")
        return int(place_id) if place_id else None

    def project_id(self):
        """Return project_id(s) from embed, if present."""
        project_id = self.params.get("project_id")
        return int(project_id) if project_id else None

    def taxon_id(self):
        """Return taxon_id(s) from embed, if present."""
        taxon_id = self.params.get("taxon_id")
        return int(taxon_id) if taxon_id else None

    def controlled_term(self):
        term_id = self.params.get("term_id")
        if not term_id:
            return None
        term_value_id = self.params.get("term_value_id")
        if not term_value_id:
            return str(term_id)
        return "{} {}".format(term_id, term_value_id)

    def user_id(self):
        """Return user_id(s) from embed, if present."""
        user_id = self.params.get("user_id")
        return int(user_id) if user_id else None

    def unobserved_by_user_id(self):
        """Return unobserved_by_user_id(s) from embed, if present."""
        unobserved_by_user_id = self.params.get("unobserved_by_user_id")
        return int(unobserved_by_user_id) if unobserved_by_user_id else None

    def not_user_id(self):
        """Return not_user_id(s) from embed, if present."""
        not_user_id = self.params.get("not_user_id")
        return int(not_user_id) if not_user_id else None

    def ident_user_id(self):
        """Return ident_user_id(s) from embed, if present."""
        ident_user_id = self.params.get("ident_user_id")
        return int(ident_user_id) if ident_user_id else None


@format_items_for_embed
def format_taxon_names_for_embed(*args, **kwargs):
    """Format taxon names for output in embed."""
    return format_taxon_names(*args, **kwargs)


def format_taxon_title(taxon, lang=None):
    """Format taxon title."""
    title = format_taxon_name(taxon, lang=lang)
    matched = taxon.matched_term
    preferred_common_name = taxon.preferred_common_name
    if lang and taxon.names:
        name = next(
            iter([name for name in taxon.names if name.get("locale") == lang]), None
        )
        if name:
            preferred_common_name = name.get("name")
    if matched not in (None, taxon.name, preferred_common_name):
        invalid_names = (
            [name["name"] for name in taxon.names if not name["is_valid"]]
            if taxon.names
            else []
        )
        if matched in invalid_names:
            matched = f"~~{matched}~~"
        title += f" ({matched})"
    return title


# TODO: refactor these two helpers as a single context manager so we can
# supply custom emoji sets in the context block.
def _add_place_emojis(query_response: QueryResponse, is_taxon_embed: bool = False):
    if not query_response:
        return False
    if is_taxon_embed:
        return query_response.place and not query_response.user
    return query_response.place and not (
        query_response.user or query_response.id_by or query_response.unobserved_by
    )


# Note: always call this after _add_place_emojis
def _add_user_emojis(query_response: QueryResponse):
    if not query_response:
        return True
    return not query_response.except_by


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
        if not isinstance(query, Query):
            return
        if not query.main:
            args = ctx.message.content.split(" ", 1)[1]
            reason = (
                "I don't understand that query.\nPerhaps you meant one of:\n"
                f"`{ctx.clean_prefix}tab {args}`\n"
                f"`{ctx.clean_prefix}obs {args}`\n"
                f"`{ctx.clean_prefix}search obs {args}`"
            )
            raise BadArgument(reason)

    async def make_last_obs_embed(self, ctx, last):
        """Return embed for recent observation link."""
        if last.obs:
            obs = last.obs
            embed = await self.make_obs_embed(ctx, obs, url=last.url, preview=False)
        else:
            embed = make_embed(url=last.url)
            mat = re.search(PAT_OBS_LINK, last.url)
            obs_id = int(mat["obs_id"])
            logger.debug("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        shared_by = f"· shared {last.ago}"
        if last.name:
            shared_by += f" by @{last.name}"
        embed.description = (
            f"{embed.description}\n\n{shared_by}" if embed.description else shared_by
        )
        return embed

    async def make_map_embed(self, ctx, taxa, lang=None):
        """Return embed for an observation link."""
        lang = await get_lang(ctx)
        title = format_taxon_names_for_embed(
            taxa, with_term=True, names_format="Range map for %s", lang=lang
        )
        inat_map_url = INatMapURL(self.api)
        url = await inat_map_url.get_map_url_for_taxa(taxa)
        return make_embed(title=title, url=url)

    @contextlib.asynccontextmanager
    async def sound_message_params(
        self, channel, sounds: list, embed: discord.Embed, index=0
    ):
        """Given a sound URL, yield params to send embed with file (if possible) or just URL."""
        if not sounds:
            yield None
            return
        sound = sounds[index]
        if isinstance(channel, DMChannel):
            url_only = False
            max_embed_file_size = MAX_EMBED_FILE_LEN
        else:
            url_only = not channel.permissions_for(channel.guild.me).attach_files
            # Boosts could make this > default 8M maximum (95% due to overhead)
            max_embed_file_size = channel.guild.filesize_limit * 0.95
        sound_io = None

        async with self.api.session.get(sound.url) as response:
            try:
                filename = response.url.name
                sound_bytes = await response.read()
            except OSError:
                filename = None
                sound_bytes = None

        _embed = make_embed()
        title = "Sound recording"
        if len(sounds) > 1:
            title += f" ({index + 1} of {len(sounds)})"
        if filename:
            title += f": {filename}"
        _embed.title = title
        _embed.url = sound.url
        _embed.set_footer(text=sound.attribution)
        embeds = [embed, _embed]
        _params = {"embeds": embeds}

        if not url_only:
            if len(sound_bytes) <= max_embed_file_size:
                sound_io = BytesIO(sound_bytes)

            if sound_io:
                _params["file"] = File(sound_io, filename=filename)
                yield _params
                sound_io.close()
                return

        yield _params

    async def summarize_obs_spp_counts(self, taxon, obs_args):
        observations = await self.api.get_observations(per_page=0, **obs_args)
        if observations:
            species = await self.api.get_observations(
                "species_counts", per_page=0, **obs_args
            )
            observations_count = observations["total_results"]
            species_count = species["total_results"]
            url = obs_url_from_v1(obs_args)
            species_url = obs_url_from_v1({**obs_args, "view": "species"})
            if taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
                summary_counts = f"Total: [{observations_count:,}]({url})"
            else:
                summary_counts = (
                    f"Total: [{observations_count:,}]({url}) "
                    f"Species: [{species_count:,}]({species_url})"
                )
            return summary_counts
        return ""

    async def make_obs_counts_embed(self, query_response: QueryResponse):
        """Return embed for observation counts from place or by user."""
        formatted_counts = ""
        taxon = query_response.taxon
        user = query_response.user
        place = query_response.place
        unobserved_by = query_response.unobserved_by
        id_by = query_response.id_by
        count_args = query_response.obs_args()

        title_query_response = copy.copy(query_response)
        description = ""
        if user or unobserved_by or id_by:
            if user:
                title_query_response.user = None
                header = TAXON_COUNTS_HEADER
            elif unobserved_by:
                user = copy.copy(title_query_response.unobserved_by)
                title_query_response.unobserved_by = None
                header = TAXON_NOTBY_HEADER
            elif id_by:
                user = copy.copy(title_query_response.id_by)
                title_query_response.id_by = None
                header = TAXON_IDBY_HEADER
            formatted_counts = await format_user_taxon_counts(
                self, user, taxon, **count_args
            )
        elif place:
            formatted_counts = await format_place_taxon_counts(
                self, place, taxon, **count_args
            )
            title_query_response.place = None
            header = TAXON_PLACES_HEADER
        summary_counts = ""
        title_query_args = title_query_response.obs_args()
        summary_counts = await self.summarize_obs_spp_counts(taxon, title_query_args)
        if formatted_counts:
            description = f"\n{summary_counts}\n{header}\n{formatted_counts}"
        else:
            description = summary_counts

        title_args = title_query_response.obs_args()
        url = obs_url_from_v1(title_args)
        full_title = f"Observations {title_query_response.obs_query_description()}"
        embed = make_embed(url=url, title=full_title, description=description)
        return embed

    async def format_obs(
        self,
        ctx,
        obs,
        with_description=True,
        with_link=False,
        compact=False,
        with_user=True,
        lang=None,
    ):
        """Format an observation title & description."""

        def format_count(label, count):
            delim = " " if compact else ", "
            return f"{delim}{EMOJI[label]}" + (str(count) if count > 1 else "")

        def get_taxon_name(taxon):
            if taxon:
                taxon_str = format_taxon_name(
                    taxon, with_rank=not compact, with_common=False
                )
            else:
                taxon_str = "Unknown"
            return taxon_str

        def format_title(taxon, obs):
            title = ""
            taxon_str = get_taxon_name(taxon)
            if with_link:
                link_url = f"{WWW_BASE_URL}/observations/{obs.id}"
                taxon_str = f"[{taxon_str}]({link_url})"
            title += taxon_str
            if not compact:
                title += f" by {user.login} " + EMOJI[obs.quality_grade]
                if obs.faves:
                    title += format_count("fave", len(obs.faves))
                if obs.comments:
                    title += format_count("comment", len(obs.comments))
            return title

        def format_summary(user, obs, taxon, taxon_summary):
            summary = ""
            if not compact:
                taxon_str = get_taxon_name(taxon)
                if taxon:
                    common = (
                        f" ({taxon.preferred_common_name})"
                        if taxon.preferred_common_name
                        else ""
                    )
                    link_url = f"{WWW_BASE_URL}/taxa/{taxon.id}"
                    taxon_str = f"[{taxon_str}]({link_url}){common}"
                summary += f"Taxon: {taxon_str}\n"
            if taxon_summary:
                means = taxon_summary.listed_taxon
                status = taxon_summary.conservation_status
                if status:
                    formatted_status = format_taxon_conservation_status(status)
                    summary += f"Conservation Status: {formatted_status}\n"
                if means:
                    summary += f"{format_taxon_establishment_means(means)}\n"
            login = ""
            if compact:
                if with_user:
                    login = user.login
                summary += "\n"
            else:
                summary += "Observed by " + format_user_link(user)
            obs_on = ""
            obs_at = ""
            if obs.observed_on:
                if compact:
                    if obs.observed_on.date() == dt.datetime.now().date():
                        obs_on = obs.observed_on.strftime("%-I:%M%P")
                    elif obs.observed_on.year == dt.datetime.now().year:
                        obs_on = obs.observed_on.strftime("%-d-%b")
                    else:
                        obs_on = obs.observed_on.strftime("%b-%Y")
                else:
                    obs_on = obs.observed_on.strftime("%a %b %-d, %Y · %-I:%M %P")
                    summary += " on " + obs_on
            if obs.place_guess:
                if compact:
                    obs_at = obs.place_guess
                else:
                    summary += " at " + obs.place_guess
            if compact:
                line = " ".join((item for item in (login, obs_on, obs_at) if item))
                if len(line) > 32:
                    line = line[0:31] + "…"
                summary += "`{0: <32}`".format(line)
                summary += EMOJI[obs.quality_grade]
                if obs.faves:
                    summary += format_count("fave", len(obs.faves))
                if obs.comments:
                    summary += format_count("comment", len(obs.comments))
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

        async def format_community_id(title, summary, obs, taxon_summary, lang=lang):
            idents_count = ""
            if obs.identifications_count:
                if obs.community_taxon_id:
                    (idents_count, idents_agree) = obs_count_community_id(obs)
                    idents_count = (
                        f"{EMOJI['community']} ({idents_agree}/{idents_count})"
                    )
                else:
                    obs_idents_count = obs.identifications_count if obs.identifications_count > 1 else ""
                    idents_count = f"{EMOJI['ident']}{obs_idents_count}"
            if not compact:
                summary += f" [obs#: {obs.id}]"
            if (
                not compact
                and obs.community_taxon_id
                and obs.community_taxon_id != obs.taxon.id
            ):
                means_link = ""
                status_link = ""
                if taxon_summary:
                    means = taxon_summary.listed_taxon
                    status = taxon_summary.conservation_status
                    if status:
                        status_link = (
                            "\nConservation Status: "
                            f"{format_taxon_conservation_status(status)}"
                        )
                    if means:
                        means_link = f"\n{format_taxon_establishment_means(means)}"
                community_taxon = await get_taxon(ctx, obs.community_taxon_id)
                summary = (
                    f"{format_taxon_name(community_taxon, lang=lang)} "
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
            if obs.photos:
                media_counts += format_count("image", len(obs.photos))
            if obs.sounds:
                media_counts += format_count("sound", len(obs.sounds))
            return media_counts

        async def get_taxon_summary(obs, **kwargs):
            taxon_summary_raw = await self.api.get_obs_taxon_summary(
                obs.id, **kwargs
            )
            taxon_summary = TaxonSummary.from_json(taxon_summary_raw)
            means = None
            status = None
            if taxon_summary:
                listed = taxon_summary.listed_taxon
                if listed:
                    means = listed.establishment_means
                    # TODO: remove this kludge once pyinat sets listed_taxon.place itself
                    taxon_summary.listed_taxon.place = Place(**taxon_summary_raw["listed_taxon"].get("place"))
                status = taxon_summary.conservation_status
            if means or status:
                return taxon_summary
            return None

        if lang and obs.taxon:
            taxon = await get_taxon(ctx, obs.taxon.id)
        else:
            taxon = obs.taxon
        user = obs.user
        title = format_title(taxon, obs)
        taxon_summary = None
        community_taxon_summary = None
        if not compact:
            taxon_summary = await get_taxon_summary(obs)
            if obs.community_taxon_id and obs.community_taxon_id != obs.taxon.id:
                community_taxon_summary = await get_taxon_summary(obs, community=1)

        summary = format_summary(user, obs, taxon, taxon_summary)
        title, summary = await format_community_id(
            title, summary, obs, community_taxon_summary, lang=lang
        )
        if not compact:
            title += format_media_counts(obs)
            if with_link:
                link_url = f"{WWW_BASE_URL}/observations/{obs.id}"
                title = f"{title} [🔗]({link_url})"
        return (title, summary)

    async def make_obs_embed(self, ctx, obs, url, preview: Union[bool, int] = True):
        """Return embed for an observation link."""
        # pylint: disable=too-many-locals

        def format_image_title_url(taxon, obs, num):
            if taxon:
                title = format_taxon_name(taxon)
            else:
                title = "Unknown"
            title += f" (Image {num} of {len(obs.photos)})"
            mat = re.search(r"/photos/(\d+)", obs.photos[num - 1].original_url)
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
                if obs.photos and image_number >= 1 and image_number <= len(obs.photos):
                    image = obs.photos[image_number - 1]
                    embed.set_image(url=image.original_url)
                    embed.set_footer(text=image.attribution)
                else:
                    image_only = False
                    if obs.photos:
                        num = len(obs.photos)
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
                lang = await get_lang(ctx)
                embed.title, summary = await self.format_obs(ctx, obs, lang=lang)
                if error:
                    summary += "\n" + error
                embed.description = summary
        else:
            mat = re.search(PAT_OBS_LINK, url)
            if mat:
                obs_id = int(mat["obs_id"])
                logger.debug("Observation not found for: %s", obs_id)
                embed.title = "No observation found for id: %s (deleted?)" % obs_id
            else:
                # If this happens, it's a bug (i.e. PAT_OBS_LINK should already match)
                logger.error("Not an observation: %s", url)
                embed.title = "Not an observation:"
                embed.description = url

        return embed

    async def make_related_embed(self, ctx, taxa):
        """Return embed for related taxa."""
        lang = await get_lang(ctx)
        names = format_taxon_names_for_embed(
            taxa, with_term=True, names_format="**The taxa:** %s", lang=lang
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
            if not common_ancestor_indices:
                taxon = await get_taxon(ctx, ROOT_TAXON_ID)
            else:
                common_ancestor_id = first_taxon_ancestor_ids[
                    max(common_ancestor_indices)
                ]
                taxon = await get_taxon(ctx, common_ancestor_id)

        description = (
            f"{names}\n**are related by {taxon.rank}**: "
            f"{format_taxon_name(taxon, lang=lang)}"
        )

        return make_embed(title="Closest related taxon", description=description)

    async def make_image_embed(self, ctx, taxon, index=1):
        """Make embed showing default image for taxon."""
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{taxon.id}")

        lang = await get_lang(ctx)
        title = format_taxon_title(taxon, lang=lang)
        taxon_photo = None

        embed.title = title
        if taxon.default_photo and not isinstance(taxon.default_photo, IconPhoto):
            if index == 1:
                taxon_photo = taxon.default_photo
            else:
                # - A taxon record may have a default_photo but no photos if the
                #   photo is externally hosted (e.g. Flickr) and the record
                #   was created from /v1/taxa/autocomplete (i.e. only has a
                #   subset of the fields that /v1/taxa/# returns).
                # - Or the user may have requested other than the default photo.
                # - In either case, we retrieve the full record via taxon_id so
                #   the photo will be set from the full-quality original in
                #   taxon_photos.
                if getattr(taxon, 'taxon_photos', None) is None or len(taxon.taxon_photos) == 0:
                    _taxon = await ctx.inat_client.taxa.populate(taxon)
                else:
                    _taxon = taxon
                if _taxon and index <= len(_taxon.taxon_photos):
                    taxon_photo = _taxon.taxon_photos[index - 1]
        if taxon_photo:
            embed.set_image(url=taxon_photo.original_url)
            embed.set_footer(text=taxon_photo.attribution)
        else:
            if index == 1:
                embed.description = "This taxon has no default photo."
            else:
                embed.description = f"This taxon does not have an image number {index}."

        return embed

    async def make_taxa_embed(
        self, ctx: Context, arg: Union[QueryResponse, Taxon], include_ancestors=True
    ):
        """Make embed describing taxa record."""
        formatter_params = {
            "lang": ctx.inat_client.ctx.get_inat_user_default("inat_lang"),
            "with_url": False,
        }
        if isinstance(arg, QueryResponse):
            place = arg.place
            if place:
                taxon = await ctx.inat_client.taxa.populate(arg.taxon, preferred_place_id=place.id)
            else:
                taxon = await ctx.inat_client.taxa.populate(arg.taxon)
            user = arg.user
            title_query_response = copy.copy(arg)
            if user:
                title_query_response.user = None
            elif place:
                title_query_response.place = None
            obs_args = title_query_response.obs_args()
            # i.e. any args other than the ones accounted for in taxon.observations_count
            if [arg for arg in obs_args if arg != "taxon_id"]:
                formatter_params["observations"] = await self.api.get_observations(per_page=0, **obs_args)
            formatter = QueryResponseFormatter(title_query_response, taxon=taxon, **formatter_params)
        elif isinstance(arg, Taxon):
            taxon = await ctx.inat_client.taxa.populate(arg)
            user = None
            place = None
            obs_args = {"taxon_id": taxon.id}
            formatter = TaxonFormatter(taxon, max_len=MAX_EMBED_DESCRIPTION_LEN, **formatter_params)
        else:
            logger.error("Invalid input: %s", repr(arg))
            raise BadArgument("Invalid input.")

        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{taxon.id}")
        description = formatter.format(with_ancestors=include_ancestors)

        if user:
            formatted_counts = await format_user_taxon_counts(
                self, user, taxon, **arg.obs_args()
            )
            if formatted_counts:
                description += f"\n{TAXON_COUNTS_HEADER}\n{formatted_counts}"
        elif place:
            formatted_counts = await format_place_taxon_counts(
                self, place, taxon, **arg.obs_args()
            )
            if formatted_counts:
                description += f"\n{TAXON_PLACES_HEADER}\n{formatted_counts}"

        embed.title = formatter.format_title()
        embed.description = description
        embed.set_thumbnail(
            url=taxon.default_photo.square_url
            if taxon.default_photo
            else taxon.icon.url
        )

        return embed

    async def get_user_project_stats(
        self, project_id, user, category: str = "obs", with_rank: bool = True
    ):
        """Get user's ranked obs & spp stats for a project."""

        async def get_unranked_count(*args, **kwargs):
            _kwargs = {
                "user_id": user.id,
                "per_page": 0,
                **kwargs,
            }
            if project_id:
                _kwargs["project_id"] = project_id
            response = await self.api.get_observations(*args, **_kwargs)
            if response:
                return response["total_results"]
            return "unknown"

        stats = None
        rank = None
        count = 0

        if category == "taxa":
            count = await get_unranked_count("species_counts")
            if with_rank:
                rank = "unranked"
            return (count, rank)

        kwargs = {}
        if category == "spp":
            kwargs["order_by"] = "species_count"
        # TODO: cache for a short while so users can compare stats but not
        # have to worry about stale data.
        if with_rank:
            if project_id:
                kwargs["project_id"] = project_id
            response = await self.api.get_observers_stats(**kwargs)
            stats = [
                UserCount.from_json(observer) for observer in response["results"]
            ]
            if stats:
                rank = next(
                    (
                        index + 1
                        for (index, d) in enumerate(stats)
                        if d.id == user.id
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
        if not (with_rank and rank):
            if category == "spp":
                count = await get_unranked_count("species_counts", hrank="species")
            else:
                count = await get_unranked_count()  # obs
        if with_rank and not rank:
            rank = ">500" if count > 0 else "unranked"
        return (count, rank)

    async def get_user_server_projects_stats(self, ctx, user):
        """Get a user's stats for the server's main event projects."""
        event_projects = None
        if ctx.guild:
            event_projects = await self.config.guild(ctx.guild).event_projects()
        if not event_projects:
            # No projects defined; implicit `ever` project for all-time stats
            event_projects = {"ever": {"project_id": 0, "main": True}}
        projects_by_id = {
            int(event_projects[prj]["project_id"]): prj
            for prj in event_projects
            if event_projects[prj].get("main")
        }
        project_ids = [project_id for project_id in projects_by_id if project_id]
        projects = await self.api.get_projects(project_ids, refresh_cache=True)
        stats = []
        for project_id in projects_by_id:
            if project_id and project_id not in projects:
                continue
            # Project id 0 is a pseudo-project consisting of just one person
            # - this allows a server to define user's all-time stats to put in
            #   `,me` without a project to track them
            # - set up this special stats item with:
            #   `,inat set event ever 0 true`
            # - note that
            if project_id:
                user_project = UserProject.from_json(projects[project_id]["results"][0])
                is_member = user.id in user_project.observed_by_ids()
            else:
                is_member = True
            if is_member:
                abbrev = projects_by_id[int(project_id)]
                obs_stats = await self.get_user_project_stats(
                    project_id, user, with_rank=False
                )
                spp_stats = await self.get_user_project_stats(
                    project_id, user, category="spp", with_rank=False
                )
                taxa_stats = await self.get_user_project_stats(
                    project_id, user, category="taxa", with_rank=False
                )
                emoji = event_projects[abbrev].get("emoji")
                stats.append(
                    (project_id, abbrev, emoji, obs_stats, spp_stats, taxa_stats)
                )
        return stats

    async def make_user_embed(self, ctx, member, user):
        """Make an embed for user including user stats."""
        description = f"{member.mention} is {format_user_link(user)}"
        if ctx.guild:
            event_projects = await self.config.guild(ctx.guild).event_projects() or {}
            main_projects = {
                event_project: event_projects[event_project]
                for event_project in event_projects
                if event_projects[event_project].get("main")
            }
            # The "master project" for the server is hardcoded to be the event
            # project with the abbrev "ever"
            # - if it is defined and has a custom emoji set, use that
            # - otherwise, fall back to :white_check_mark: to indicate a
            #   mod-added member in this server
            master_project = main_projects.get("ever")
            master_project_emoji = (
                master_project and master_project.get("emoji")
            ) or ":white_check_mark:"
            if master_project_emoji and await has_valid_user_config(
                self, member, False
            ):
                description += f" {master_project_emoji}"
        embed = make_embed()
        project_stats = await self.get_user_server_projects_stats(ctx, user)
        for (
            project_id,
            abbrev,
            emoji,
            obs_stats,
            spp_stats,
            taxa_stats,
        ) in project_stats:
            obs_count, _obs_rank = obs_stats
            spp_count, _spp_rank = spp_stats
            taxa_count, _taxa_rank = taxa_stats
            obs_args = {"user_id": user.id}
            if int(project_id):
                obs_args["project_id"] = project_id
            obs_url = obs_url_from_v1(
                {**obs_args, "view": "observations", "verifiable": "any"}
            )
            spp_url = obs_url_from_v1(
                {**obs_args, "view": "species", "verifiable": "any", "hrank": "species"}
            )
            taxa_url = obs_url_from_v1(
                {**obs_args, "view": "species", "verifiable": "any"}
            )
            fmt = (
                f"[{obs_count:,}]({obs_url}) / [{spp_count:,}]({spp_url}) / "
                f"[{taxa_count:,}]({taxa_url})"
            )
            embed.add_field(
                name=f"Obs / Spp / Leaf taxa ({abbrev})", value=fmt, inline=True
            )
        embed.description = description
        ids = user.identifications_count
        url = f"[{ids:,}]({WWW_BASE_URL}/identifications?user_id={user.id})"
        embed.add_field(name="Ids", value=url, inline=True)
        return embed

    async def make_stats_embed(self, member, user, project):
        """Make an embed for user showing stats for a project."""
        embed = make_embed(
            title=project.title, url=project.url, description=member.mention
        )
        project_id = project.id
        obs_count, obs_rank = await self.get_user_project_stats(project_id, user)
        spp_count, spp_rank = await self.get_user_project_stats(
            project_id, user, category="spp"
        )
        taxa_count, _taxa_rank = await self.get_user_project_stats(
            project_id, user, category="taxa"
        )
        obs_args = {"project_id": project.id, "user_id": user.id}
        obs_url = obs_url_from_v1(
            {**obs_args, "view": "observations", "verifiable": "any"}
        )
        spp_url = obs_url_from_v1(
            {**obs_args, "view": "species", "verifiable": "any", "hrank": "species"}
        )
        taxa_url = obs_url_from_v1({**obs_args, "view": "species", "verifiable": "any"})
        fmt = (
            f"[{obs_count:,}]({obs_url}) (#{obs_rank}) / "
            f"[{spp_count:,}]({spp_url}) (#{spp_rank}) / "
            f"[{taxa_count:,}]({taxa_url})"
        )
        embed.add_field(
            name="Obs (rank) / Spp (rank) / Leaf taxa", value=fmt, inline=True
        )
        return embed

    async def add_obs_reaction_emojis(self, ctx, msg, query_response: QueryResponse):
        """Add obs embed reaction emojis."""
        reaction_emojis = (
            OBS_PLACE_REACTION_EMOJIS
            if _add_place_emojis(query_response)
            else OBS_REACTION_EMOJIS
            if _add_user_emojis(query_response)
            else []
        )
        return await add_reactions_with_cancel(ctx, msg, reaction_emojis)

    async def add_taxon_reaction_emojis(
        self,
        ctx,
        msg,
        query_response: Union[QueryResponse, Taxon],
        taxonomy=True,
        with_keep=False,
    ):
        """Add taxon embed reaction emojis."""
        if isinstance(query_response, QueryResponse):
            taxon = query_response.taxon
        else:
            taxon = query_response
            query_response = None
        add_place_emojis = _add_place_emojis(query_response, True)
        if taxonomy and len(taxon.ancestor_ids) > 2:
            reaction_emojis = (
                TAXON_PLACE_REACTION_EMOJIS
                if add_place_emojis
                else TAXON_REACTION_EMOJIS
                if _add_user_emojis(query_response)
                else []
            )
        else:
            reaction_emojis = (
                NO_PARENT_TAXON_PLACE_REACTION_EMOJIS
                if add_place_emojis
                else NO_PARENT_TAXON_REACTION_EMOJIS
                if _add_user_emojis(query_response)
                else []
            )
        return await add_reactions_with_cancel(
            ctx, msg, reaction_emojis, with_keep=with_keep
        )

    async def send_embed_for_taxon_image(
        self, ctx, query_response: Union[QueryResponse, Taxon], index=1, with_keep=False
    ):
        """Make embed for taxon image & send."""
        msg = await ctx.send(
            embed=await self.make_image_embed(ctx, query_response, index)
        )
        # TODO: drop taxonomy=False when #139 is fixed
        # - This workaround omits Taxonomy reaction to make it less likely a
        #   user will break the display; they can use `,last t` to get the taxon
        #   display with taxonomy instead, if they need it.
        # - Note: a tester may still manually add the :regional_indicator_t:
        #   reaction to test the feature in its current, broken state.
        return await self.add_taxon_reaction_emojis(
            ctx, msg, query_response, taxonomy=False, with_keep=with_keep
        )

    async def send_embed_for_taxon(
        self, ctx, query_response, include_ancestors=True, with_keep=False
    ):
        """Make embed for taxon & send."""
        msg = await ctx.send(
            embed=await self.make_taxa_embed(
                ctx, query_response, include_ancestors=include_ancestors
            )
        )
        return await self.add_taxon_reaction_emojis(
            ctx, msg, query_response, with_keep=with_keep
        )

    async def send_obs_embed(self, ctx, embed, obs, **reaction_params):
        """Send observation embed and sound."""

        async def hybrid_send(ctx, **kwargs):
            """See d.py /discord/ext/commands/context.py send()"""
            if ctx.interaction is None:
                msg = await ctx.channel.send(**kwargs)
            else:
                if ctx.interaction.response.is_done():
                    msg = await ctx.interaction.followup.send(**kwargs, wait=True)
                else:
                    await ctx.interaction.response.send_message(**kwargs)
                    msg = await ctx.interaction.original_response()
            return msg

        msg = None
        if obs and obs.sounds:
            sounds = obs_get_sounds(obs)
            async with self.sound_message_params(
                ctx.channel, sounds, embed=embed
            ) as params:
                if params:
                    msg = await hybrid_send(ctx, **params)
        if not msg:
            msg = await hybrid_send(ctx, embed=embed)

        return await add_reactions_with_cancel(ctx, msg, [], **reaction_params)

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

    async def maybe_update_user(
        self,
        ctx,
        msg: discord.Message,
        action: str,
        member: Optional[discord.Member] = None,
        user: Optional[User] = None,
    ):
        """Add or remove user count in the embed if valid."""
        inat_user = None
        if member:
            try:
                inat_user = await self.user_table.get_user(member)
            except LookupError:
                return
        if user:
            inat_user = user
        if not inat_user:
            return

        counts_pat = r"(\n|^)\[[0-9, \(\)]+\]\(.*?\) " + inat_user.login
        inat_embed = msg.embeds[0]
        if inat_embed.taxon_id():
            taxon = await get_taxon(ctx, inat_embed.taxon_id())
        else:
            taxon = None
        # Observed by count add/remove for taxon:
        await self.edit_totals_locked(msg, taxon, inat_user, action, counts_pat)

    async def maybe_update_place(
        self,
        ctx,
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
            try:
                update_place = await self.place_table.get_place(msg.guild, "home", user)
            except LookupError:
                return
        else:
            update_place = place

        inat_embed = msg.embeds[0]
        place_counts_pat = r"(\n|^)\[[0-9, \(\)]+\]\(.*?\) " + re.escape(
            update_place.display_name
        )
        if inat_embed.taxon_id():
            taxon = await get_taxon(ctx, inat_embed.taxon_id())
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

    async def maybe_update_user_by_name(
        self, ctx, msg: discord.Message, member: discord.Member
    ):
        """Prompt for a user by name and update the embed if provided & valid."""
        try:
            await self.user_table.get_user(member)
        except LookupError:
            return
        response = await self.query_locked(
            msg,
            member,
            "Add or remove which user (you have 15 seconds to answer)?",
            15,
        )
        if response:
            try:
                _user = await self.query.get_inat_user(ctx, response.content)
            except (LookupError, discord.ext.commands.errors.BadArgument) as error:
                error_msg = await msg.channel.send(error)
                await asyncio.sleep(15)
                with contextlib.suppress(discord.HTTPException):
                    await error_msg.delete()
                return

            await self.maybe_update_user(ctx, msg, user=_user, action="toggle")

    async def maybe_update_place_by_name(
        self, ctx, msg: discord.Message, user: discord.Member
    ):
        """Prompt user for place by name and update the embed if provided & valid."""
        try:
            await self.user_table.get_user(user)
        except LookupError:
            return
        response = await self.query_locked(
            msg,
            user,
            "Add or remove which place (you have 15 seconds to answer)?",
            15,
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

            await self.maybe_update_place(ctx, msg, user, "toggle", place)

    async def maybe_update_taxonomy(self, ctx, message):
        """Update taxonomy in taxon embed, if applicable."""
        embeds = message.embeds
        inat_embed = embeds[0]
        description = inat_embed.description or ""
        new_description = re.sub(TAXONOMY_PAT, "", description)
        if new_description == description:
            full_taxon = await get_taxon(ctx, inat_embed.taxon_id())
            if full_taxon:
                formatted_names = format_taxon_names(
                    full_taxon.ancestors, hierarchy=True
                )
                hierarchy = re.sub(HIERARCHY_PAT, "", formatted_names, 1)
                new_description = re.sub(
                    NO_TAXONOMY_PAT,
                    " in:\n" + hierarchy + r"\1",
                    description,
                    1,
                )
            else:
                return
        inat_embed.description = new_description
        await message.edit(embed=inat_embed)

    async def update_totals(
        self,
        description,
        taxon,
        inat_user,
        action,
        inat_embed,
        counts_pat,
    ):
        """Update the totals for the embed."""
        unobserved = inat_embed.has_not_by_users()
        ident = inat_embed.has_id_by_users()
        if not (unobserved or ident):
            # Add/remove always results in a change to totals, so remove:
            description = re.sub(
                r"\n\[[0-9, \(\)]+?\]\(.*?\) \*total\*", "", description
            )

        matches = re.findall(
            r"\n\[[0-9, \(\)]+\]\(.*?\) (?P<user_id>[-_a-z0-9]+)", description
        )
        count_params = {**inat_embed.params}
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
            user_id = inat_user.id
            if unobserved:
                count_params["unobserved_by_user_id"] = user_id
            elif ident:
                count_params["ident_user_id"] = user_id
            else:
                count_params["user_id"] = user_id
            formatted_counts = await format_user_taxon_counts(
                self,
                inat_user,
                taxon,
                **count_params,
            )
            description += "\n" + formatted_counts

        if not (unobserved or ident):
            matches = re.findall(
                r"\n\[[0-9, \(\)]+\]\(.*?[?&]user_id=(?P<user_id>\d+).*?\)",
                description,
            )
            # Total added only if more than one user:
            if len(matches) > 1:
                user_ids = ",".join(matches)
                count_params["user_id"] = user_ids
                formatted_counts = await format_user_taxon_counts(
                    self,
                    user_ids,
                    taxon,
                    **count_params,
                )
                description += f"\n{formatted_counts}"
                return description
        return description

    async def edit_totals_locked(
        self,
        msg,
        taxon,
        inat_user,
        action,
        counts_pat,
    ):
        """Update totals for message locked."""
        if msg.id not in self.reaction_locks:
            self.reaction_locks[msg.id] = asyncio.Lock()
        async with self.reaction_locks[msg.id]:
            # If permitted, refetch the message because it may have changed prior to
            # acquiring lock
            if (
                msg.guild
                and not msg.channel.permissions_for(msg.guild.me).read_message_history
            ):
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
                    description,
                    taxon,
                    inat_user,
                    action,
                    inat_embed,
                    counts_pat,
                )
                if len(description) > MAX_EMBED_DESCRIPTION_LEN:
                    raise NoRoomInDisplay(
                        "No more room for additional users in this display."
                    )
                inat_embed.description = description
                # Image embeds use the footer for photo attribution.
                if not inat_embed.image:
                    if not inat_embed.has_not_by_users() and re.search(
                        r"\*total\*", inat_embed.description
                    ):
                        inat_embed.set_footer(
                            text="User counts may not add up to "
                            "the total if they changed since they were added. "
                            "Remove, then add them again to update their counts."
                        )
                    else:
                        if not inat_embed.image:
                            inat_embed.set_footer(text="")
                await msg.edit(embed=inat_embed)

    async def update_place_totals(
        self, description, taxon, place, action, inat_embed, place_counts_pat
    ):
        """Update the place totals for the embed."""
        # Add/remove always results in a change to totals, so remove:
        description = re.sub(r"\n\[[0-9, \(\)]+?\]\(.*?\) \*total\*", "", description)

        matches = re.findall(r"\n\[[0-9, \(\)]+\]\(.*?\) (.*?)(?=\n|$)", description)
        count_params = {**inat_embed.params, "place_id": place.id}
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
                **count_params,
            )
            description += "\n" + formatted_counts

        matches = re.findall(
            r"\n\[[0-9, \(\)]+\]\(.*?\?place_id=(?P<place_id>\d+)&.*?\)",
            description,
        )
        # Total added only if more than one place:
        if len(matches) > 1:
            place_ids = ",".join(matches)
            formatted_counts = await format_place_taxon_counts(
                self,
                place_ids,
                taxon,
                **count_params,
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
            # If permitted, refetch the message because it may have changed prior to
            # acquiring lock
            if (
                msg.guild
                and not msg.channel.permissions_for(msg.guild.me).read_message_history
            ):
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
