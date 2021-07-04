"""Module to search iNat site."""

from .base_classes import Place, WWW_BASE_URL, User
from .projects import Project
from .taxa import get_taxon_fields


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
    """Get taxon result (v1/search)."""
    taxon = get_taxon_fields(result.get("record"))
    return (
        f":green_circle: [{taxon.format_name(with_term=True)}]"
        f"({WWW_BASE_URL}/taxa/{taxon.id})"
    )


def get_taxon2(result):
    """Get taxon result (/v1/taxa)."""
    taxon = get_taxon_fields(result)
    return (
        f":green_circle: [{taxon.format_name(with_term=True)}]"
        f"({WWW_BASE_URL}/taxa/{taxon.id})"
    )


# pylint: disable=invalid-name
get_result_type = {
    "Place": get_place,
    "Project": get_project,
    "User": get_user,
    "Taxon": get_taxon,
    "Inactive": get_taxon2,
}


def get_result(result, result_type: str = None):
    """Get fields for any result type."""
    res_type = result_type or result.get("type")
    return get_result_type[res_type](result)


# pylint: disable=too-few-public-methods
class INatSiteSearch:
    """Lookup helper for site search."""

    def __init__(self, cog):
        self.cog = cog

    async def search(self, ctx, query, **kwargs):
        """Search iNat site."""

        # Through experimentation on May 25, 2020, I've determined a smaller
        # number than 500 will usually be returned:
        # - for /v1/taxa it will be 500
        # - for /v1/search?source=x (for any single source) it will be 100
        # - for /v1/search without a source it will be 30
        # If more than the maximum per_page is specified, however, it defaults
        # back to 30, so we try to intelligently adjust the per_page in our
        # request.
        result_type = "Inactive" if "is_active" in kwargs else None
        if result_type == "Inactive":
            per_page = 500
        elif "sources" in kwargs:
            per_page = 100
        else:
            per_page = 30
        home = await self.cog.get_home(ctx)
        api_kwargs = {"q": query, "per_page": per_page, "preferred_place_id": home}
        api_kwargs.update(kwargs)
        search_results = await self.cog.api.get_search_results(**api_kwargs)
        results = [
            get_result(result, result_type) for result in search_results["results"]
        ]
        # But we return the actual per_page so the pager can accurately report
        # how many results were not shown.
        return (results, search_results["total_results"], search_results["per_page"])
