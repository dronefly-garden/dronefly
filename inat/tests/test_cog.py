from redbot.core.commands import CogMeta
from inat.inat import INat

def test_cog():
    assert isinstance(INat, CogMeta)
