"""Module to handle projects."""
from typing import Union

from redbot.core import Config
from pyinaturalist.models import Project

from .client import iNatClient
from .converters.base import QuotedContextMemberConverter
from .utils import get_home_server, get_hub_server


async def get_event_project_config(guild_config: Config, abbrev: str):
    event_projects = await guild_config.event_projects()
    event_project = event_projects.get(abbrev)
    return event_project


async def get_event_project_id(guild_config: Config, abbrev: str):
    event_project = await get_event_project_config(guild_config, abbrev)
    event_project_id = int(event_project["project_id"]) if event_project else 0
    if not (event_project and event_project_id > 0):
        raise LookupError("Event project not known.")
    return event_project


async def get_event_project(guild_config: Config, abbrev: str, client: iNatClient):
    event_project_id = await get_event_project_id(guild_config, abbrev)
    paginator = client.projects.from_ids(event_project_id, limit=1)
    projects = await paginator.async_all() if paginator else None
    if projects:
        return projects[0]
    raise LookupError("iNat project not found.")


class UserProject(Project):
    """A collection project for observations by specific users.

    This class handles projects that include observations by members, with membership
    being managed either solely by the user, soley by the admins, or a combination
    of both:

    1. Open membership, users join on the web:

       - members_only: True
       - do not set any "observed_by_user?" rules

    2. Closed membership, admins edit the project to join users:

       - members_only: False
       - set at least one "observed_by_user?" rule

    3. Closed membership, users join on web and admins edit project to "approve" join:

       - members_only: True
       - set at least one "observed_by_user?" rule
       - a user's observations are included when both the user joins *and* the
         admin "approves" the join by adding a rule for them
    """

    def members_only(self):
        return next(
            iter(
                [
                    param.get("value")
                    for param in self.search_parameters
                    if param.get("field") == "members_only"
                ]
            ),
            False,
        )

    def observed_by_ids(self):
        """Valid observer user ids for the project.

        TODO: clarify what the iNat code actually does for these cases and fix
        as needed. we implement, based on some reasonable assumptions:

        - for closed membership projects, exclude any user that has both
          an included rule (observed_by_user?) and an excluded rule
          (not_observed_by_user?)
        """
        exclude_user_ids = [
            rule.get("operand_id")
            for rule in self.project_observation_rules
            if rule.get("operator") == "not_observed_by_user?"
        ]
        include_user_rules = [
            rule
            for rule in self.project_observation_rules
            if rule.get("operator") == "observed_by_user?"
            and rule.get("operand_id") not in exclude_user_ids
        ]

        if self.members_only():
            if include_user_rules:
                # i.e. case 3, Closed (user joins & admin approves the join)
                include_user_ids = [
                    rule.get("operand_id")
                    for rule in include_user_rules
                    if rule.get("operand_id") in self.user_ids
                ]
            else:
                # i.e. case 1, Open (user joins)
                include_user_ids = [
                    user_id
                    for user_id in self.user_ids
                    if user_id not in exclude_user_ids
                ]
        else:
            if include_user_rules:
                # i.e. case 2, Closed (admin joins the user)
                include_user_ids = [
                    rule.get("operand_id") for rule in include_user_rules
                ]
            else:
                # i.e. fallback - project membership is undefined, so is empty
                # - as in case 2 but admins haven't joined anyone yet
                # - note: exclusions are irrelevant; an empty membership minus
                #   some specific users is still "empty"
                include_user_ids = []

        return include_user_ids


class INatProjectTable:
    """Lookup helper for projects."""

    def __init__(self, cog):
        self.cog = cog

    async def get_project(
        self,
        guild,
        query: Union[int, str],
        user: QuotedContextMemberConverter = None,
    ):
        """Get project by guild abbr or via id#/keyword lookup in API."""

        async def _get_project_abbrev(guild, abbrev):
            response = None
            guild_config = self.cog.config.guild(guild)
            projects = await guild_config.projects()
            if abbrev in projects:
                response = await self.cog.api.get_projects(projects[abbrev])
            return response

        abbrev = query.lower() if isinstance(query, str) else None
        project = None
        response = None
        _guild = guild or await get_home_server(self.cog, user)

        if _guild and abbrev:
            response = await _get_project_abbrev(_guild, abbrev)
            if not response:
                hub_server = await get_hub_server(self.cog, _guild)
                if hub_server:
                    response = await _get_project_abbrev(hub_server, abbrev)

        if not response:
            if isinstance(query, int) or query.isnumeric():
                project_id = int(query)
                response = await self.cog.api.get_projects(project_id)

        if not response:
            response = await self.cog.api.get_projects("autocomplete", q=query)

        if response:
            results = response.get("results")
            if results:
                project = results[0]

        if project:
            return Project.from_json(project)

        raise LookupError("iNat project not known.")
