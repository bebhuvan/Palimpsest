from __future__ import annotations

import hashlib
from datetime import datetime

import orjson

from history_pipeline.models import (
    AcceptedProposalRelease,
    CommunityProposal,
    ProposalReviewAction,
    ProposalReviewEvent,
    ProposalStatus,
)

_TRANSITIONS = {
    (ProposalStatus.PROPOSED, ProposalStatus.IN_REVIEW): (
        ProposalReviewAction.SUBMITTED_FOR_REVIEW
    ),
    (ProposalStatus.IN_REVIEW, ProposalStatus.ACCEPTED): ProposalReviewAction.ACCEPTED,
    (ProposalStatus.IN_REVIEW, ProposalStatus.REJECTED): ProposalReviewAction.REJECTED,
}


def advance_proposal(
    proposal: CommunityProposal,
    target_status: ProposalStatus,
    event: ProposalReviewEvent,
) -> CommunityProposal:
    """Return a new proposal revision after one allowed editorial transition."""

    if proposal.status in {ProposalStatus.ACCEPTED, ProposalStatus.REJECTED}:
        raise ValueError("accepted and rejected proposals are terminal")
    expected_action = _TRANSITIONS.get((proposal.status, target_status))
    if expected_action is None:
        raise ValueError(
            f"proposal cannot transition from {proposal.status.value} "
            f"to {target_status.value}"
        )
    if event.action != expected_action:
        raise ValueError(
            f"transition to {target_status.value} requires {expected_action.value}"
        )
    if event.created_at < proposal.updated_at:
        raise ValueError("review event cannot precede the current proposal revision")
    return CommunityProposal.model_validate(
        {
            **proposal.model_dump(mode="python"),
            "revision": proposal.revision + 1,
            "status": target_status,
            "updated_at": event.created_at,
            "review_history": [*proposal.review_history, event],
        }
    )


def proposal_checksum(proposal: CommunityProposal) -> str:
    payload = orjson.dumps(
        proposal.model_dump(mode="json"),
        option=orjson.OPT_SORT_KEYS,
    )
    return hashlib.sha256(payload).hexdigest()


def create_release_receipt(
    proposal: CommunityProposal,
    *,
    receipt_id: str,
    release_build_id: str,
    published_record_ids: list[str],
    released_at: datetime,
) -> AcceptedProposalRelease:
    """Link only an accepted terminal revision to an immutable canonical release."""

    if proposal.status != ProposalStatus.ACCEPTED:
        raise ValueError("only accepted proposals can enter an immutable release")
    decision = proposal.review_history[-1]
    if decision.action != ProposalReviewAction.ACCEPTED:
        raise ValueError("accepted proposal has no final acceptance decision")
    return AcceptedProposalRelease.model_validate(
        {
            "receipt_id": receipt_id,
            "proposal_id": proposal.proposal_id,
            "proposal_revision": proposal.revision,
            "decision_event_id": decision.event_id,
            "proposal_checksum_sha256": proposal_checksum(proposal),
            "release_build_id": release_build_id,
            "published_record_ids": published_record_ids,
            "released_at": released_at,
        }
    )
