"""Taxon model module."""
from dataclasses import dataclass
from typing import Optional

PLANTAE_ID = 47126

# RANK_LEVELS and RANK_EQUIVALENTS are from:
# - https://github.com/inaturalist/inaturalist/blob/master/app/models/taxon.rb
RANK_LEVELS = {
    "stateofmatter": 100,
    "unranked": 90,  # Invented to make parent check work (this is null in the db)
    "kingdom": 70,
    "phylum": 60,
    "subphylum": 57,
    "superclass": 53,
    "class": 50,
    "subclass": 47,
    "infraclass": 45,
    "subterclass": 44,
    "superorder": 43,
    "order": 40,
    "suborder": 37,
    "infraorder": 35,
    "parvorder": 34.5,
    "zoosection": 34,
    "zoosubsection": 33.5,
    "superfamily": 33,
    "epifamily": 32,
    "family": 30,
    "subfamily": 27,
    "supertribe": 26,
    "tribe": 25,
    "subtribe": 24,
    "genus": 20,
    "genushybrid": 20,
    "subgenus": 15,
    "section": 13,
    "subsection": 12,
    "complex": 11,
    "species": 10,
    "hybrid": 10,
    "subspecies": 5,
    "variety": 5,
    "form": 5,
    "infrahybrid": 5,
}

RANK_EQUIVALENTS = {
    "division": "phylum",
    "sub-class": "subclass",
    "super-order": "superorder",
    "sub-order": "suborder",
    "super-family": "superfamily",
    "sub-family": "subfamily",
    "gen": "genus",
    "sp": "species",
    "spp": "species",
    "infraspecies": "subspecies",
    "ssp": "subspecies",
    "sub-species": "subspecies",
    "subsp": "subspecies",
    "trinomial": "subspecies",
    "var": "variety",
    # 'unranked': None,
}

RANK_KEYWORDS = tuple(RANK_LEVELS.keys()) + tuple(RANK_EQUIVALENTS.keys())
TAXON_PRIMARY_RANKS = ["kingdom", "phylum", "class", "order", "family"]
TRINOMIAL_ABBR = {"variety": "var.", "subspecies": "ssp.", "form": "f."}


# TODO: use pyinaturalist models
# TODO: resolve unnecessary divergences from API response attribute names
@dataclass
class Taxon:
    """A taxon."""

    name: str
    taxon_id: int
    common: Optional[str]
    term: str
    thumbnail: Optional[str]
    image: Optional[str]
    image_attribution: Optional[str]
    rank: str
    ancestor_ids: list
    observations: int
    ancestor_ranks: list
    active: bool
    listed_taxa: list
    names: list
    # FIXME: not yet implemented in core
    # establishment_means: Optional[EstablishmentMeansPartial]
    # conservation_status: Optional[ConservationStatus]

    def format_name(
        self, with_term=False, hierarchy=False, with_rank=True, with_common=True
    ):
        """Format taxon name.

        TODO: Consider moving this out of the model into a separate formatters module.
              - Currently we format as Discord-flavored markdown, but that should be
                made chat-platform-agnostic for core.
              - Other output formats will likely be desired soon: plain text, ANSI
                colored text, html.

        Parameters
        ----------
        with_term: bool, optional
            When with_common=True, non-common / non-name matching term is put in
            parentheses in place of common name.
        hierarchy: bool, optional
            If specified, produces a list item suitable for inclusion in the hierarchy section
            of a taxon embed. See format_taxon_names() for details.
        with_rank: bool, optional
            If specified and hierarchy=False, includes the rank for ranks higher than species.
        with_common: bool, optional
            If specified, include common name in parentheses after scientific name.

        Returns
        -------
        str
            A name of the form "Rank Scientific name (Common name)" following the
            same basic format as iNaturalist taxon pages on the web, i.e.

            - drop the "Rank" keyword for species level and lower
            - italicize the name (minus any rank abbreviations; see next point) for genus
            level and lower
            - for trinomials (must be subspecies level & have exactly 3 names to qualify),
            insert the appropriate abbreviation, unitalicized, between the 2nd and 3rd
            name (e.g. "Anser anser domesticus" -> "*Anser anser* var. *domesticus*")
        """

        if with_common:
            if with_term:
                common = (
                    self.term
                    if self.term not in (self.name, self.common)
                    else self.common
                )
            else:
                if hierarchy:
                    common = None
                else:
                    common = self.common
        else:
            common = None
        name = self.name

        rank = self.rank
        rank_level = RANK_LEVELS[rank]

        if rank_level <= RANK_LEVELS["genus"]:
            name = f"*{name}*"
        if rank_level > RANK_LEVELS["species"]:
            if hierarchy:
                bold = ("\n> **", "**") if rank in TAXON_PRIMARY_RANKS else ("", "")
                name = f"{bold[0]}{name}{bold[1]}"
            elif with_rank:
                name = f"{rank.capitalize()} {name}"
        else:
            if rank in TRINOMIAL_ABBR.keys():
                tri = name.split(" ")
                if len(tri) == 3:
                    # Note: name already italicized, so close/reopen italics around insertion.
                    name = f"{tri[0]} {tri[1]}* {TRINOMIAL_ABBR[rank]} *{tri[2]}"
        full_name = f"{name} ({common})" if common else name
        if not self.active:
            full_name += " :exclamation: Inactive Taxon"
        return full_name
