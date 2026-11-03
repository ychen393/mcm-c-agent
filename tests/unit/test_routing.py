import pytest
from core.routing import route_after_approval
@pytest.mark.parametrize(('decision','expected'), [('approved','continue'), ('rejected','stop'), ('needs_revision','revise')])
def test_approval_routing(decision, expected): assert route_after_approval(decision) == expected
