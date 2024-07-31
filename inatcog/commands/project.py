"""Module for project command group."""

import logging
import re

import html2markdown
from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.discord.embeds import make_embed, MAX_EMBED_DESCRIPTION_LEN
from redbot.core import checks, commands
from redbot.core.commands import BadArgument
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from ..checks import can_manage_projects
from ..common import grouper
from ..converters.base import MemberConverter
from ..embeds.common import apologize
from ..embeds.inat import INatEmbeds
from ..interfaces import MixinMeta
from ..places import RESERVED_PLACES
from ..utils import get_home_server, has_valid_user_config

logger = logging.getLogger("red.dronefly." + __name__)


class CommandsProject(INatEmbeds, MixinMeta):
    """Mixin providing project command group."""

    @commands.group(invoke_without_command=True, aliases=["prj"])
    async def project(self, ctx, *, query):
        """iNat project for name, id number, or abbreviation.

        **query** may contain:
        - *id#* of the iNat project
        - *words* in the iNat project name
        - *abbreviation* defined with `[p]project add`; see `[p]help project add` for details.
        """
        try:
            project = await self.project_table.get_project(ctx.guild, query, ctx.author)
            embed = make_embed(
                title=project.title,
                url=project.url,
                description=html2markdown.convert(
                    " " + project.description[:MAX_EMBED_DESCRIPTION_LEN]
                ),
            )
            if project.banner_color:
                embed.color = int(project.banner_color.replace("#", "0x"), 16)
            if project.icon:
                embed.set_thumbnail(url=project.icon)
            embed.add_field(name="Project number", value=project.id)
            guild = ctx.guild or await get_home_server(self, ctx.author)
            if guild:
                guild_config = self.config.guild(guild)
                projects = await guild_config.projects()
                proj_abbrevs = [
                    abbrev for abbrev in projects if projects[abbrev] == project.id
                ]
                if proj_abbrevs:
                    abbrevs = ", ".join(proj_abbrevs)
                else:
                    abbrevs = "*none*"
                    can_add_projects = await has_valid_user_config(
                        self, ctx.author, anywhere=False
                    )
                    if can_add_projects:
                        embed.set_footer(
                            text=f"Add an abbreviation with {ctx.clean_prefix}project add"
                        )
                embed.add_field(
                    name=self.p.plural("Abbreviation", len(proj_abbrevs)), value=abbrevs
                )
            await ctx.send(embed=embed)
        except LookupError as err:
            await ctx.send(err)

    @can_manage_projects()
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
    @checks.bot_has_permissions(embed_links=True, read_message_history=True)
    async def project_list(self, ctx, *, match=""):
        """List projects with abbreviations on this server."""
        guild = ctx.guild or await get_home_server(self, ctx.author)
        if not guild:
            return
        config = self.config.guild(guild)
        projects = await config.projects()
        result_pages = []

        # Prefetch all uncached projects, 10 at a time
        # - 10 is a maximum determined by testing. beyond that, iNat API
        #   will respond with:
        #
        #      Unprocessable Entity (422)
        #
        proj_id_groups = [
            list(filter(None, results))
            for results in grouper(
                [
                    int(projects[abbrev])
                    for abbrev in projects
                    if int(projects[abbrev]) not in self.api.projects_cache
                ],
                10,
            )
        ]
        for proj_id_group in proj_id_groups:
            try:
                async with ctx.typing():
                    await self.api.get_projects(proj_id_group)
            except LookupError as err:
                # Deleted places should not raise here, but should simply be dropped
                # from the results, so this is something else (e.g. API failed to
                # respond)
                logger.warn(
                    "%s (places: %s, guild: %d)",
                    err,
                    ",".join(proj_id_group),
                    guild.id,
                )

        # Iterate over projects and do a quick cache lookup per project:
        for abbrev in sorted(projects):
            proj_id = int(projects[abbrev])
            proj_str_text = ""
            if proj_id in self.api.projects_cache:
                try:
                    project = await self.project_table.get_project(
                        guild, proj_id, ctx.author
                    )
                    proj_str = f"{abbrev}: [{project.title}]({project.url})"
                    proj_str_text = f"{abbrev} {project.title}"
                except LookupError as err:
                    # Shouldn't ever happen. The cache should've been filled with
                    # any existing project entries from proj_id_groups above. If
                    # the project is in the cache, then it should be retrievable by
                    # get_project(). If the project doesn't exist, it should not raise
                    # a LookupError, but should just fall through below and be
                    # listed by its id.
                    logger.error(
                        "Project in cache could not be retrieved: %s (project: %d, guild: %d)",
                        err,
                        proj_id,
                        guild.id,
                    )
                    # In the unlikely case of the deletion of a project that is cached:
                    proj_str = f"{abbrev}: {proj_id} not found."
                    proj_str_text = abbrev
            # Most likely this is a deleted project. Show the abbrev, id, and link. The
            # user can check by clicking the link if it 404's and take action as
            # needed.
            if not proj_str_text:
                logger.info(
                    "Project deleted? %s: %d (guild: %d)",
                    abbrev,
                    proj_id,
                    guild.id,
                )
                proj_str = f"{abbrev}: [{proj_id}]({WWW_BASE_URL}/projects/{proj_id})"
                proj_str_text = abbrev
            if match:
                words = match.split(" ")
                if all(
                    re.search(pat, proj_str_text)
                    for pat in [
                        re.compile(r"\b%s" % re.escape(word), re.I) for word in words
                    ]
                ):
                    result_pages.append(proj_str)
            else:
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
            await apologize(ctx, "Nothing found")

    @can_manage_projects()
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
    @checks.bot_has_permissions(embed_links=True)
    async def project_stats(self, ctx, project: str, *, user: str = "me"):
        """Project stats for the named user.

        Observation & species count & rank of the user within the project are shown, as well as leaf taxa, which are not ranked. Leaf taxa are explained here:
        https://www.inaturalist.org/pages/how_inaturalist_counts_taxa
        """  # noqa: E501

        if project == "":
            await ctx.send_help()
        error_msg = None
        async with ctx.typing():
            try:
                proj = await self.project_table.get_project(
                    ctx.guild, project, ctx.author
                )
                ctx_member = await MemberConverter.convert(ctx, user)
                member = ctx_member.member
                user = await self.user_table.get_user(member)
                embed = await self.make_stats_embed(member, user, proj)
                await ctx.send(embed=embed)
            except (BadArgument, LookupError) as err:
                error_msg = str(err)
        if error_msg:
            await apologize(ctx, error_msg)
