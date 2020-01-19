"""Module to handle iNat embed concerns."""
from io import BytesIO
import re
from typing import Union
from discord import File
from .api import WWW_BASE_URL
from .common import LOG
from .embeds import format_items_for_embed, make_embed
from .interfaces import MixinMeta
from .maps import INatMapURL
from .obs import PAT_OBS_LINK
from .taxa import (
    format_taxon_name,
    format_taxon_names,
    get_taxon_fields,
    FilteredTaxon,
    format_user_taxon_counts,
)


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
}


class INatEmbeds(MixinMeta):
    """Provide embeds for iNatCog."""

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
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            LOG.info("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        shared_by = f"· shared {last.ago} by @{last.name}"
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

    async def maybe_send_sound_url(self, channel, url):
        """Given a URL to a sound, send it if it can be retrieved."""
        async with self.api.session.get(url) as response:
            try:
                sound = BytesIO(await response.read())
            except OSError:
                sound = None
        if sound:
            await channel.send(file=File(sound, filename=response.url.name))

    async def make_obs_embed(self, guild, obs, url, preview: Union[bool, int] = True):
        """Return embed for an observation link."""
        # pylint: disable=too-many-locals
        def format_count(label, count):
            return f", {EMOJI[label]}" + (str(count) if count > 1 else "")

        def format_image_title_url(taxon, obs, num):
            if taxon:
                title = format_taxon_name(taxon)
            else:
                title = "Unknown"
            title += f" (Image {num} of {len(obs.images)})"
            mat = re.search(r"/photos/(\d+)", obs.images[num - 1])
            if mat:
                photo_id = mat[1]
                url = f"{WWW_BASE_URL}/photos/{photo_id}"
            else:
                url = None

            return (title, url)

        def format_title(taxon, obs):
            if taxon:
                title = format_taxon_name(taxon)
            else:
                title = "Unknown"
            title += " " + EMOJI[obs.quality_grade]
            if obs.faves_count:
                title += format_count("fave", obs.faves_count)
            if obs.comments_count:
                title += format_count("comment", obs.comments_count)
            return title

        def format_summary(user, obs):
            summary = "Observed by " + user.profile_link()
            if obs.obs_on:
                summary += " on " + obs.obs_on
            if obs.obs_at:
                summary += " at " + obs.obs_at
            if obs.description:
                # Contribute up to 10 lines from the description, and no more
                # than 500 characters:
                lines = obs.description.split("\n", 11)
                description = "\n> %s" % "\n> ".join(lines[:10])
                if len(lines) > 10:
                    description += "\n> …"
                if len(description) > 500:
                    description = description[:498] + "…"
                summary += description + "\n"
            return summary

        def format_community_id(title, summary, obs):
            idents_count = ""
            if obs.idents_count:
                idents_count = (
                    f"{EMOJI['community']} ({obs.idents_agree}/{obs.idents_count})"
                )
            summary += f" [obs#: {obs.obs_id}]"
            if (
                obs.community_taxon
                and obs.community_taxon.taxon_id != obs.taxon.taxon_id
            ):
                summary = (
                    f"{format_taxon_name(obs.community_taxon)} {idents_count}\n\n"
                    + summary
                )
            else:
                title += " " + idents_count
            return (title, summary)

        def format_media_counts(title, obs):
            if obs.images:
                title += format_count("image", len(obs.images))
            if obs.sounds:
                title += format_count("sound", len(obs.sounds))
            return title

        async def format_projects(title, obs):
            project_emojis = (
                await self.config.guild(guild).project_emojis() if guild else None
            )
            if project_emojis:
                for obs_id in obs.project_ids:
                    if obs_id in project_emojis:
                        title += project_emojis[obs_id]
            return title

        embed = make_embed(url=url)

        if obs:
            taxon = obs.taxon
            user = obs.user

            image_only = False
            error = None
            if preview:
                if isinstance(preview, bool):
                    image_number = 1
                else:
                    image_number = preview
                    image_only = True
                if obs.images and image_number >= 1 and image_number <= len(obs.images):
                    embed.set_image(url=obs.images[image_number - 1])
                else:
                    image_only = False
                    if obs.images:
                        num = len(obs.images)
                        error = (
                            f"*Image number out of range; must be between 1 and {num}.*"
                        )
                    else:
                        error = f"*This observation has no images.*"

            if image_only:
                (title, url) = format_image_title_url(taxon, obs, image_number)
                embed.title = title
                embed.url = url
            else:
                title = format_title(taxon, obs)
                summary = format_summary(user, obs)
                title, summary = format_community_id(title, summary, obs)
                title = format_media_counts(title, obs)
                title = await format_projects(title, obs)

                embed.title = title
                if error:
                    summary += "\n" + error
                embed.description = summary
        else:
            mat = re.search(PAT_OBS_LINK, url)
            obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
            LOG.info("Observation not found for link: %d", obs_id)
            embed.title = "No observation found for id: %d (deleted?)" % obs_id

        return embed

    async def make_related_embed(self, taxa):
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
            common_ancestor_id = first_taxon_ancestor_ids[max(common_ancestor_indices)]
            taxon_record = (await self.api.get_taxa(common_ancestor_id))["results"][0]
            taxon = get_taxon_fields(taxon_record)

        description = (
            f"{names}\n**are related by {taxon.rank}**: {format_taxon_name(taxon)}"
        )

        return make_embed(title="Closest related taxon", description=description)

    async def make_image_embed(self, rec):
        """Make embed showing default image for taxon."""
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}")

        title = format_taxon_title(rec)

        embed.title = title
        if rec.thumbnail:
            if rec.image:
                image = rec.image
            else:
                # A taxon record may have a thumbnail but no image if the image
                # is externally hosted (e.g. Flickr) and the record was created
                # from /v1/taxa/autocomplete (i.e. only has a subset of the
                # fields that /v1/taxa/# returns). In that case, we retrieve
                # the full record via taxon_id so the image will be set from
                # the full-quality original in taxon_photos.
                taxon_record = (await self.api.get_taxa(rec.taxon_id))["results"][0]
                full_taxon = get_taxon_fields(taxon_record)
                image = full_taxon.image
        if image:
            embed.set_image(url=image)

        return embed

    async def make_taxa_embed(self, arg):
        """Make embed describing taxa record."""
        if isinstance(arg, FilteredTaxon):
            (taxon, user) = arg
        else:
            taxon = arg
            user = None
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{taxon.taxon_id}")
        p = self.p  # pylint: disable=invalid-name

        async def format_description(rec):
            obs_cnt = rec.observations
            url = f"{WWW_BASE_URL}/observations?taxon_id={rec.taxon_id}&verifiable=any"
            obs_fmt = "[%d](%s)" % (obs_cnt, url)
            description = (
                f"is {p.a(rec.rank)} with {obs_fmt} {p.plural('observation', obs_cnt)}"
            )
            return description

        async def format_ancestors(description, rec):
            full_record = (await self.api.get_taxa(rec.taxon_id))["results"][0]
            ancestors = full_record.get("ancestors")
            if ancestors:
                ancestors = [get_taxon_fields(ancestor) for ancestor in ancestors]
                description += " in: " + format_taxon_names(ancestors, hierarchy=True)
            else:
                description += "."
            return description

        title = format_taxon_title(taxon)
        description = await format_description(taxon)
        description = await format_ancestors(description, taxon)
        if user:
            formatted_counts = await format_user_taxon_counts(self, user, taxon)
            if formatted_counts:
                description += f"\n{formatted_counts}"

        embed.title = title
        embed.description = description
        if taxon.thumbnail:
            embed.set_thumbnail(url=taxon.thumbnail)

        return embed
