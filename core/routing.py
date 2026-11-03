from typing import Literal
ApprovalDecision = Literal['approved', 'rejected', 'needs_revision']
def route_after_approval(decision: ApprovalDecision) -> str:
    return {'approved': 'continue', 'rejected': 'stop', 'needs_revision': 'revise'}[decision]
