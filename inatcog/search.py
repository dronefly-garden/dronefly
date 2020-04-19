"""Module to search iNat site."""


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
                "{name} ({kind} matching {match}): id={match_id}".format(
                    name=result.get("record").get("name"),
                    kind=result.get("type"),
                    match='"{matches}"'.format(
                        matches=result.get("record").get("matched_term")
                    ),
                    match_id=result.get("record").get("id"),
                )
                for result in search_results["results"]
            ]
        )
        return results
