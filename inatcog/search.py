"""Module to search iNat site."""

from .api import WWW_BASE_URL
from .places import Place
from .projects import Project
from .taxa import format_taxon_name, get_taxon_fields
from .users import User


def get_place(result):
    """Get place result."""
    place = Place.from_dict(result.get("record"))
    return f":round_pushpin: [{place.display_name}]({place.url})"


def get_project(result):
    """Get project result."""
    project = Project.from_dict(result.get("record"))
    return (
        f":briefcase: [{project.title}]({WWW_BASE_URL}/projects/{project.project_id})"
    )


def get_user(result):
    """Get user result."""
    user = User.from_dict(result.get("record"))
    return f":bust_in_silhouette: {user.profile_link()}"


def get_taxon(result):
    """Get taxon result."""
    taxon = get_taxon_fields(result.get("record"))
    return (
        f":green_circle: [{format_taxon_name(taxon, with_term=True)}]"
        "({WWW_BASE_URL}/taxa/{taxon.taxon_id})"
    )


# pylint: disable=invalid-name
get_result_type = {
    "Place": get_place,
    "Project": get_project,
    "User": get_user,
    "Taxon": get_taxon,
}


def get_result(result):
    """Get fields for any result type."""
    return get_result_type[result.get("type")](result)


# pylint: disable=too-few-public-methods
class INatSiteSearch:
    """Lookup helper for site search."""

    def __init__(self, cog):
        self.cog = cog

    async def search(self, query, **kwargs):
        """Search iNat site."""

        api_kwargs = {"q": query, "per_page": 30}
        api_kwargs.update(kwargs)
        search_results = await self.cog.api.get_search_results(**api_kwargs)
        results = [get_result(result) for result in search_results["results"]]
        return (results, search_results["total_results"])
