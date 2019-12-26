"""Module to handle projects."""
from dataclasses import dataclass, field
from typing import List
from dataclasses_json import config, DataClassJsonMixin


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
