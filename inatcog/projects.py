"""Module to handle projects."""
from dataclasses import dataclass, field
from typing import List, Union
from dataclasses_json import config, DataClassJsonMixin
from .api import WWW_BASE_URL


@dataclass
class Project(DataClassJsonMixin):
    """A project."""

    project_id: int = field(metadata=config(field_name="id"))
    title: str
    url: str = field(init=False)

    def __post_init__(self):
        """URL for project."""
        self.url = f"{WWW_BASE_URL}/projects/{self.project_id}"


@dataclass
class UserProject(DataClassJsonMixin):
    """A collection project for observations by specific users."""

    project_id: int = field(metadata=config(field_name="id"))
    title: str
    user_ids: List
    project_observation_rules: List
    project_type: str

    def __post_init__(self):
        if self.project_type != "collection":
            raise TypeError

    def observed_by_ids(self):
        """The 'must be observed by' rule user ids."""
        return [
            rule["operand_id"]
            for rule in self.project_observation_rules
            if rule["operator"] == "observed_by_user?"
        ]


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

        if isinstance(query, str):
            abbrev = query.lower()
        if isinstance(query, int) or query.isnumeric():
            project_id = query
            response = await self.cog.api.get_projects(int(project_id))
        if guild:
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
