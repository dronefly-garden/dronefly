"""Module to handle projects."""
from dataclasses import dataclass, field
from typing import List, Union

from dataclasses_json import config, DataClassJsonMixin

from .base_classes import Project


@dataclass
class CollectionProjectRule(DataClassJsonMixin):
    """A collection project rule."""

    operand_id: int
    operator: str


@dataclass
class UserProject(DataClassJsonMixin):
    """A collection project for observations by specific users.

    There are two basic kinds of UserProject. Both are collection projects,
    and both are "Members only" with the following differences:

    1. prefers_user_trust projects are "Members only" with an open membership.
        i.e. any user can join and become a member, and only their observations
        are included.
    2. "observed_by_user?" projects are "Members only" with a closed membership.
        i.e. users added to the project by the project admins, and only their
        observations will be included.
    """

    project_id: int = field(metadata=config(field_name="id"))
    title: str
    user_ids: List[int]
    prefers_user_trust: bool
    project_observation_rules: List[CollectionProjectRule]
    project_type: str

    def __post_init__(self):
        if self.project_type != "collection":
            raise TypeError

    def observed_by_ids(self):
        """Valid observer user ids for the project.

        TODO: clarify what the iNat code actually does for these cases and fix
        as needed. we implement, based on some reasonable assumptions:

        - for closed membership projects, exclude any user that has both
          an included rule (observed_by_user?) and an excluded rule
          (not_observed_by_user?)
        - for open membership projects, ignore any included user rules
          and only obey excluded user rules
        """
        exclude_user_ids = [
            rule.operand_id
            for rule in self.project_observation_rules
            if rule.operator == "not_observed_by_user?"
        ]
        if self.prefers_user_trust:
            include_user_ids = [
                user_id for user_id in self.user_ids if user_id not in exclude_user_ids
            ]
        else:
            include_user_ids = [
                rule.operand_id
                for rule in self.project_observation_rules
                if rule.operator == "observed_by_user?"
                and rule.operand_id not in exclude_user_ids
            ]
        return include_user_ids


@dataclass
class ObserverStats(DataClassJsonMixin):
    """The stats for an observer from a set of observers (as from a project)."""

    user_id: int
    observation_count: int
    species_count: int


class INatProjectTable:
    """Lookup helper for projects."""

    def __init__(self, cog):
        self.cog = cog

    async def get_project(self, guild, query: Union[int, str]):
        """Get project by guild abbr or via id#/keyword lookup in API."""
        project = None
        response = None
        abbrev = None

        if isinstance(query, str):
            abbrev = query.lower()
        if isinstance(query, int) or query.isnumeric():
            project_id = query
            response = await self.cog.api.get_projects(int(project_id))
        if guild and abbrev:
            guild_config = self.cog.config.guild(guild)
            projects = await guild_config.projects()
            if abbrev in projects:
                response = await self.cog.api.get_projects(projects[abbrev])

        if not response:
            response = await self.cog.api.get_projects("autocomplete", q=query)

        if response:
            results = response.get("results")
            if results:
                project = results[0]

        if project:
            return Project.from_dict(project)

        raise LookupError("iNat project not known.")
