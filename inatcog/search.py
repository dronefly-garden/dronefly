"""Module to search iNat site."""

from collections import namedtuple

Result = namedtuple("result", "name, kind, match, match_id")


def get_fields_for_place(result):
    """Get fields for place result."""
    return Result(
        result.get("record").get("name"),
        result.get("type"),
        '"{matches}"'.format(matches=result.get("record").get("matched_term")),
        result.get("record").get("id"),
    )


def get_fields_for_project(result):
    """Get fields for project result."""
    return Result(
        result.get("record").get("name"),
        result.get("type"),
        '"{matches}"'.format(matches=result.get("record").get("matched_term")),
        result.get("record").get("id"),
    )


def get_fields_for_user(result):
    """Get fields for user result."""
    return Result(
        result.get("record").get("name"),
        result.get("type"),
        '"{matches}"'.format(matches=result.get("record").get("matched_term")),
        result.get("record").get("id"),
    )


def get_fields_for_taxon(result):
    """Get fields for taxon result."""
    return Result(
        result.get("record").get("name"),
        result.get("type"),
        '"{matches}"'.format(matches=result.get("record").get("matched_term")),
        result.get("record").get("id"),
    )


# pylint: disable=invalid-name
get_fields_for = {
    "Place": get_fields_for_place,
    "Project": get_fields_for_project,
    "User": get_fields_for_user,
    "Taxon": get_fields_for_taxon,
}


def get_fields(result):
    """Get fields for any result type."""
    return get_fields_for[result.get("type")](result)


# pylint: disable=too-few-public-methods
class INatSiteSearch:
    """Lookup helper for site search."""

    def __init__(self, cog):
        self.cog = cog

    async def search(self, query):
        """Search iNat site."""
        search_results = await self.cog.api.get_search_results(q=query, per_page=10)
        results = "\n".join(
            [
                "{0.name} ({0.kind} matching {0.match}): id={0.match_id}".format(
                    get_fields(result)
                )
                for result in search_results["results"]
            ]
        )
        return results
