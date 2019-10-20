"""Module to handle iNat embeds for Discord."""
import re

from .api import WWW_BASE_URL
from .common import LOG
from .embeds import format_items_for_embed, make_embed
from .maps import get_map_url_for_taxa
from .obs import PAT_OBS_LINK
from .taxa import format_taxon_name, format_taxon_names


@format_items_for_embed
def format_taxon_names_for_embed(*args, **kwargs):
    """Format taxon names for output in embed."""
    return format_taxon_names(*args, **kwargs)


def make_last_obs_embed(last):
    """Return embed for recent observation link."""
    embed = make_embed(url=last.url)
    summary = None

    if last.obs:
        obs = last.obs
        user = obs.user
        taxon = obs.taxon
        if taxon:
            embed.title = format_taxon_name(taxon)
        else:
            embed.title = "Unknown"
        if obs.thumbnail:
            embed.set_thumbnail(url=obs.thumbnail)
        summary = "Observed by %s" % user.profile_link()
        if obs.obs_on:
            summary += " on %s" % obs.obs_on
        if obs.obs_at:
            summary += " at %s" % obs.obs_at
    else:
        mat = re.search(PAT_OBS_LINK, last.url)
        obs_id = int(mat["obs_id"])
        LOG.info("Observation not found for link: %d", obs_id)
        embed.title = "No observation found for id: %d (deleted?)" % obs_id

    embed.description = f"{summary}\n\n· shared {last.ago} by @{last.name}"
    return embed


def make_map_embed(taxa):
    """Return embed for an observation link."""
    title = format_taxon_names_for_embed(
        taxa, with_term=True, names_format="Range map for %s"
    )
    url = get_map_url_for_taxa(taxa)
    return make_embed(title=title, url=url)


def make_obs_embed(obs, url):
    """Return embed for an observation link."""
    embed = make_embed(url=url)
    summary = None

    if obs:
        taxon = obs.taxon
        user = obs.user
        if taxon:
            embed.title = format_taxon_name(taxon)
        else:
            embed.title = "Unknown"
        if obs.thumbnail:
            embed.set_image(url=re.sub("/square", "/large", obs.thumbnail))
        summary = "Observed by %s" % user.profile_link()
        if obs.obs_on:
            summary += " on %s" % obs.obs_on
        if obs.obs_at:
            summary += " at %s" % obs.obs_at
        embed.description = summary
    else:
        mat = re.search(PAT_OBS_LINK, url)
        obs_id = int(mat["obs_id"])
        LOG.info("Observation not found for link: %d", obs_id)
        embed.title = "No observation found for id: %d (deleted?)" % obs_id

    return embed


def make_taxa_embed(rec):
    """Make embed describing taxa record."""
    embed = make_embed(
        title=format_taxon_name(rec), url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}"
    )

    if rec.thumbnail:
        embed.set_thumbnail(url=rec.thumbnail)

    matched = rec.term
    if matched not in (rec.name, rec.common):
        embed.description = matched

    observations = rec.observations

    url = get_map_url_for_taxa([rec])
    if url:
        observations = "%s[%d](%s)" % [
            "≥" if observations >= 10000 else "",
            observations,
            url,
        ]
    embed.add_field(name="Observations:", value=observations, inline=True)

    return embed
