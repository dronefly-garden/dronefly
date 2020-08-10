"""Module to handle iNat embed concerns."""
from io import BytesIO
import re
from typing import Union
from discord import File
import html2markdown
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import start_adding_reactions
from .common import LOG
from .embeds import format_items_for_embed, make_embed
from .interfaces import MixinMeta
from .maps import INatMapURL
from .base_classes import (
    CompoundQuery,
    MEANS_LABEL_DESC,
    WWW_BASE_URL,
    PAT_OBS_LINK,
    FilteredTaxon,
    TaxonSummary,
)
from .projects import UserProject, ObserverStats
from .taxa import (
    format_taxon_name,
    format_taxon_names,
    get_taxon,
    get_taxon_fields,
    get_taxon_preferred_establishment_means,
    format_place_taxon_counts,
    format_user_taxon_counts,
    TAXON_ID_LIFE,
    TAXON_COUNTS_HEADER,
    TAXON_PLACES_HEADER,
)

SHORT_DATE_PAT = re.compile(
    r"(^.*\d{1,2}:\d{2}(:\d{2})?(\s+(am|pm))?)(.*$)", flags=re.I
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
        async with self.api.session.get(sound.url) as response:
            try:
                sound_io = BytesIO(await response.read())
            except OSError:
                sound_io = None
        if sound_io:
            filename = response.url.name.replace(".m4a", ".mp3")
            embed = make_embed()
            embed.set_footer(text=sound.attribution)
            await channel.send(embed=embed, file=File(sound_io, filename=filename))

    async def make_obs_counts_embed(self, arg):
        """Return embed for observation counts from place or by user."""
        group_by_param = ""
        formatted_counts = ""
        (taxon, user, place) = arg

        title = format_taxon_title(taxon)
        full_title = f"Observations of {title}"
        description = ""
        if place and user:
            full_title = f"Observations of {title} from {place.display_name}"
            group_by_param = f"&place_id={place.place_id}"
            formatted_counts = await format_user_taxon_counts(
                self, user, taxon, place.place_id
            )
            header = TAXON_COUNTS_HEADER
        elif user:
            formatted_counts = await format_user_taxon_counts(self, user, taxon)
            header = TAXON_COUNTS_HEADER
        elif place:
            formatted_counts = await format_place_taxon_counts(self, place, taxon)
            header = TAXON_PLACES_HEADER
        if formatted_counts:
            description = f"\n{header}\n{formatted_counts}"

        embed = make_embed(
            url=f"{WWW_BASE_URL}/observations?taxon_id={taxon.taxon_id}{group_by_param}",
            title=full_title,
            description=description,
        )
        return embed

    async def format_obs(
        self, obs, with_description=True, with_link=False, compact=False
    ):
        """Format an observation title & description."""

        def format_count(label, count):
            return f", {EMOJI[label]}" + (str(count) if count > 1 else "")

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
                summary += "by " + user.login
            else:
                summary += "Observed by " + user.profile_link()
            if obs.obs_on:
                if compact:
                    summary += " on " + re.sub(SHORT_DATE_PAT, r"\1", obs.obs_on)
                else:
                    summary += " on " + obs.obs_on
            if obs.obs_at:
                if compact:
                    summary += "\n"
                summary += " at " + obs.obs_at
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
                idents_count = (
                    f"{EMOJI['community']} ({obs.idents_agree}/{obs.idents_count})"
                )
            if not compact:
                summary += f" [obs#: {obs.obs_id}]"
            if (
                obs.community_taxon
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
                title += " " + idents_count
            return (title, summary)

        def format_media_counts(title, obs):
            if obs.images:
                title += format_count("image", len(obs.images))
            if obs.sounds:
                title += format_count("sound", len(obs.sounds))
            return title

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
        title = format_media_counts(title, obs)
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
                    self, TAXON_ID_LIFE, preferred_place_id=preferred_place_id
                )
            else:
                common_ancestor_id = first_taxon_ancestor_ids[
                    max(common_ancestor_indices)
                ]
                taxon = await get_taxon(
                    self, common_ancestor_id, preferred_place_id=preferred_place_id
                )

        description = (
            f"{names}\n**are related by {taxon.rank}**: {format_taxon_name(taxon)}"
        )

        return make_embed(title="Closest related taxon", description=description)

    async def make_image_embed(self, ctx, rec):
        """Make embed showing default image for taxon."""
        embed = make_embed(url=f"{WWW_BASE_URL}/taxa/{rec.taxon_id}")

        title = format_taxon_title(rec)
        image = None

        embed.title = title
        if rec.thumbnail:
            if rec.image:
                image = rec.image
                attribution = rec.image_attribution
            else:
                # A taxon record may have a thumbnail but no image if the image
                # is externally hosted (e.g. Flickr) and the record was created
                # from /v1/taxa/autocomplete (i.e. only has a subset of the
                # fields that /v1/taxa/# returns). In that case, we retrieve
                # the full record via taxon_id so the image will be set from
                # the full-quality original in taxon_photos.
                preferred_place_id = await self.get_home(ctx)
                full_taxon = await get_taxon(
                    self, rec.taxon_id, preferred_place_id=preferred_place_id
                )
                image = full_taxon.image
                attribution = full_taxon.image_attribution
        if image:
            embed.set_image(url=image)
            embed.set_footer(text=attribution)
        else:
            embed.description = "This taxon has no default photo!"

        return embed

    async def make_taxa_embed(self, ctx, arg):
        """Make embed describing taxa record."""
        if isinstance(arg, FilteredTaxon):
            (taxon, user, place) = arg
        else:
            taxon = arg
            user = None
            place = None
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

        async def format_ancestors(description, ancestors):
            if ancestors:
                ancestors = [get_taxon_fields(ancestor) for ancestor in ancestors]
                description += " in: " + format_taxon_names(ancestors, hierarchy=True)
            else:
                description += "."
            return description

        title = format_taxon_title(taxon)
        description = await format_description(taxon)

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
        if means and MEANS_LABEL_DESC.get(means.establishment_means):
            description += f" {means.emoji()}{means.link()}"
        status = full_taxon.conservation_status
        if status:
            description += f" [{status.description()}]({status.url})"

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

    async def send_embed_for_taxon_image(self, ctx, taxon):
        """Make embed for taxon image & send."""
        msg = await ctx.send(embed=await self.make_image_embed(ctx, taxon))
        start_adding_reactions(msg, ["#️⃣", "📝", "🏠", "📍"])

    async def send_embed_for_taxon(self, ctx, taxon):
        """Make embed for taxon & send."""
        msg = await ctx.send(embed=await self.make_taxa_embed(ctx, taxon))
        start_adding_reactions(msg, ["#️⃣", "📝", "🏠", "📍"])
