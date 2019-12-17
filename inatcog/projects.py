"""Module to handle projects."""
from dataclasses import dataclass, field
from typing import List
from dataclasses_json import config, DataClassJsonMixin


@dataclass
class UserProject(DataClassJsonMixin):
    """A collection project for observations by specific users."""

    id: int = field(metadata=config(field_name="project_id"))
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
