"""Module to handle iNat embeds for Discord."""
import re

from .api import WWW_BASE_URL, get_taxa
from .common import LOG
from .embeds import format_items_for_embed, make_embed
from .maps import get_map_url_for_taxa
from .obs import PAT_OBS_LINK
from .taxa import get_taxon_fields, format_taxon_name, format_taxon_names


@format_items_for_embed
def format_taxon_names_for_embed(*args, **kwargs):
    """Format taxon names for output in embed."""
    return format_taxon_names(*args, **kwargs)


EMOJI = {
    "research": ":white_check_mark:",
    "needs_id": ":large_orange_diamond:",
    "casual": ":white_circle:",
    "fave": ":star:",
    "comment": ":speech_left:",
    "community": ":busts_in_silhouette:",
}


def make_last_obs_embed(last):
    """Return embed for recent observation link."""
    if last.obs:
        obs = last.obs
        embed = make_obs_embed(obs, url=last.url, preview=False)
    else:
        embed = make_embed(url=last.url)
        mat = re.search(PAT_OBS_LINK, last.url)
        obs_id = int(mat["obs_id"])
        LOG.info("Observation not found for link: %d", obs_id)
        embed.title = "No observation found for id: %d (deleted?)" % obs_id

    embed.description = f"{embed.description}\n\n· shared {last.ago} by @{last.name}"
    return embed


def make_map_embed(taxa):
    """Return embed for an observation link."""
    title = format_taxon_names_for_embed(
        taxa, with_term=True, names_format="Range map for %s"
    )
    url = get_map_url_for_taxa(taxa)
    return make_embed(title=title, url=url)


def make_obs_embed(obs, url, preview=True):
    """Return embed for an observation link."""
    embed = make_embed(url=url)

    if obs:
        taxon = obs.taxon
        user = obs.user
        if taxon:
            title = format_taxon_name(taxon)
        else:
            title = "Unknown"
        title += " " + EMOJI[obs.quality_grade]

        def format_count(label, count):
            return f", {EMOJI[label]}" + (str(count) if count > 1 else "")

        if obs.faves_count:
            title += format_count("fave", obs.faves_count)
        if obs.comments_count:
            title += format_count("comment", obs.comments_count)
        if preview and obs.thumbnail:
            embed.set_image(url=re.sub("/square", "/large", obs.thumbnail))
        summary = "Observed by " + user.profile_link()
        if obs.obs_on:
            summary += " on " + obs.obs_on
        if obs.obs_at:
            summary += " at " + obs.obs_at
        if obs.description:
            summary += "\n> %s\n" % obs.description.replace("\n", "\n> ")
        idents_count = ""
        if obs.idents_count:
            idents_count = (
                f"{EMOJI['community']} ({obs.idents_agree}/{obs.idents_count})"
            )
        summary += f" [obs#: {obs.obs_id}]"
        if obs.community_taxon and obs.community_taxon.taxon_id != obs.taxon.taxon_id:
            summary = (
                f"{format_taxon_name(obs.community_taxon)} {idents_count}\n\n" + summary
            )
        else:
            title += " " + idents_count

        embed.title = title
        embed.description = summary
    else:
        mat = re.search(PAT_OBS_LINK, url)
        obs_id = int(mat["obs_id"])
        LOG.info("Observation not found for link: %d", obs_id)
        embed.title = "No observation found for id: %d (deleted?)" % obs_id

    return embed


def make_taxa_embed(rec):
    """Make embed describing taxa record."""
    embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}")

    title = format_taxon_name(rec)
    matched = rec.term
    if matched not in (rec.name, rec.common):
        title += f" ({matched})"

    observations = rec.observations
    url = get_map_url_for_taxa([rec])
    if url:
        observations = "[%d](%s)" % (observations, url)
    description = f"is a {rec.rank} with {observations} observations"

    full_record = get_taxa(rec.taxon_id)
    ancestors = [
        get_taxon_fields(ancestor)
        for ancestor in full_record["results"][0]["ancestors"]
    ]
    if ancestors:
        description += " in: " + format_taxon_names(ancestors, hierarchy=True)
    else:
        description += "."

    embed.title = title
    embed.description = description
    if rec.thumbnail:
        embed.set_thumbnail(url=rec.thumbnail)

    return embed
