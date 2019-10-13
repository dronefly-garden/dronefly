"""Test inatcog.api."""
from .api import get_taxa

# FIXME: mock the actual /v1/taxa calls
def test_get_taxa_by_id():
    """Test get_taxa by id."""
    assert get_taxa(1)[0]["name"] == "Animalia"

def test_get_taxa_by_query():
    """Test get_taxa with query terms."""
    assert get_taxa(q="animals")[0]["name"] == "Animalia"
