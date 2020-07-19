"""Module to handle controlled terms."""
import re
from typing import List, Optional
from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin

# pylint: disable=invalid-name


@dataclass
class ControlledTermValue(DataClassJsonMixin):
    """An iNat controlled term value."""

    id: int
    label: str
    taxon_ids: Optional[List[int]]
    excepted_taxon_ids: Optional[List[int]]


@dataclass
class ControlledTerm(DataClassJsonMixin):
    """An iNat controlled term."""

    id: int
    label: str
    values: List[ControlledTermValue]


def match_controlled_term(
    controlled_terms: List[ControlledTerm], term_label: str, value_label: str
):
    """Match term and value matching term's label & value's label."""
    matched_term = next(
        iter(
            [
                term
                for term in controlled_terms
                if re.match(re.escape(term_label), term.label, re.I)
            ]
        ),
        None,
    )
    if matched_term:
        matched_value = next(
            iter(
                [
                    value
                    for value in matched_term.values
                    if re.match(re.escape(value_label), value.label, re.I)
                ]
            ),
            None,
        )
        if matched_value:
            return (matched_term, matched_value)
        raise LookupError("No matching value for controlled term")
    raise LookupError("No matching controlled term")
