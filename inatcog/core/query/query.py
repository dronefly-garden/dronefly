"""Naturalist information system query module."""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TaxonQuery:
    """A taxon query composed of terms and/or phrases or a code or taxon_id, filtered by ranks."""

    taxon_id: Optional[int] = None
    terms: Optional[List[str]] = None
    phrases: Optional[List[str]] = None
    ranks: Optional[List[str]] = None
    code: Optional[str] = None
    _query: Optional[str] = None

    def _add_term(self, item):
        if item:
            if isinstance(item, list):
                formatted_item = " ".join(item)
            else:
                formatted_item = str(item)
            self._query += " " + formatted_item if self._query else formatted_item

    def __str__(self):
        self._query = ""
        self._add_term(self.taxon_id)
        self._add_term(self.terms)
        # TODO: support mixture of terms and phrases better
        # - currently all phrases will be rendered unquoted as terms,
        #   so we lose information that was present in the input
        # self._add_term(self.phrases)
        self._add_term(self.ranks)
        self._add_term(self.code)
        return self._query


@dataclass
class Query:
    """Naturalist information system query.

    A naturalist information system query is generally composed of one or more
    "who", "what", "when", & "where" clauses. This class provides both a single
    representation of those parts that can be applied to looking things up on
    different information systems and also a common grammar and syntax for users
    to learn to make requests across all systems.

    - the "who" is the person or persons related to the data
    - the "what" is primarily taxa or records related to one or more taxa
    - the "when" is the date/times or date/time periods relating to the data
    - the "where" is the place associated with the data
    - some additional options controlling retrieval and presentation of the
      data may also be a part of the query

    While this query class was initially written to cater to the kinds of
    requests directly supported through the iNaturalist API, it is not
    intended to be limited to making requests from that site. Many sites
    support subsets of what iNat API can do, and so the applicable parts
    of the query & grammar can be used to fetch material from those sites.

    Options governing "who":

    - "by", "not by", "id by" identify people related to the data
    - "by" is the author of the data (e.g. observer)
    - other "who" options indicate different roles of the people relating
      to the requested data

    Options governing "what":

    - "of" identifies data matching a taxon query
    - the taxon query can further be qualified by:
        - double-quoted phrases to express exact phrase match for some or
          all of the name
        - rank keywords to only match taxa of the specified rank(s)
    - "in" is an ancestor taxon that the target taxon ("of") must be
      a child of in the hierarchy to match
    - "with" are controlled terms that select only data with particular
      attributes
    - A "per" option influences which entities or groupings of entities
      are requested, where that is not otherwise imposed by the kind of
      query performed.

    Options governing "where":

    - "from" identifies a place associated with the data

    Options governing "when":

    - "when" features:
        - "on", "since", and "until" are always inclusive of the date given
        - the assumed date is the date associated with the record itself, and
          not the date it was added to the system
        - the "added" qualifier can be combined with these three option keywords
          to request the date the record was added instead

    Options that don't neatly fit into the above:

    - "project" is a fairly iNaturalist-specific concept
    - A generic "opt" option is provided to pass through miscellaneous
      options to the information system APIs not neatly falling into these
      categories, like "order" and "order by".
        - Because these are often highly dependent on the specific information
          systems involved, these are not treated as an integral part of our
          who, what, when, and where concepts.
    """

    main: Optional[TaxonQuery] = None
    ancestor: Optional[TaxonQuery] = None
    user: Optional[str] = None
    place: Optional[str] = None
    controlled_term: Optional[str] = None
    unobserved_by: Optional[str] = None
    id_by: Optional[str] = None
    per: Optional[str] = None
    project: Optional[str] = None
    options: Optional[List] = None
    obs_d1: Optional[List] = None
    obs_d2: Optional[List] = None
    obs_on: Optional[List] = None
    added_d1: Optional[List] = None
    added_d2: Optional[List] = None
    added_on: Optional[List] = None
    _query: Optional[str] = None

    def _add_clause(self, fmt, item):
        if item:
            if isinstance(item, list):
                formatted_item = fmt.format(" ".join(item))
            else:
                formatted_item = fmt.format(item)
            self._query += " " + formatted_item if self._query else formatted_item

    def __str__(self):
        self._query = ""
        if self.main:
            self._add_clause("{}", str(self.main))
        if self.ancestor:
            self._add_clause("in {}", str(self.ancestor))
        self._add_clause("from {}", self.place)
        self._add_clause("in prj {}", self.project)
        self._add_clause("by {}", self.user)
        self._add_clause("id by {}", self.id_by)
        self._add_clause("not by {}", self.unobserved_by)
        self._add_clause("with {}", self.controlled_term)
        self._add_clause("per {}", self.per)
        self._add_clause("opt {}", self.options)
        self._add_clause("since {}", self.obs_d1)
        self._add_clause("until {}", self.obs_d2)
        self._add_clause("on {}", self.obs_on)
        self._add_clause("added since {}", self.added_d1)
        self._add_clause("added until {}", self.added_d2)
        self._add_clause("added on {}", self.added_on)
        return self._query


EMPTY_QUERY = Query()
