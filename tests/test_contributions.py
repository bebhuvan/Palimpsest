from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import HttpUrl, ValidationError

from history_pipeline.contributions import advance_proposal, create_release_receipt
from history_pipeline.models import (
    CommunityProposal,
    ContributionKind,
    ProposalContributor,
    ProposalEvidence,
    ProposalReviewAction,
    ProposalReviewEvent,
    ProposalStatus,
    ProposedChange,
    SourceReference,
)

CREATED = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)


def contributor(identifier: str, name: str) -> ProposalContributor:
    return ProposalContributor(
        contributor_id=f"contributor:{identifier}",
        display_name=name,
        attribution=f"Contribution by {name}",
    )


def proposal() -> CommunityProposal:
    alice = contributor("alice", "Alice Example")
    source = SourceReference(
        source_id="proposal_source",
        record_id="record-1",
        title="Evidence record",
        publisher="Example Archive",
        url=HttpUrl("https://example.org/archive/record-1"),
        license_id="CC-BY-4.0",
        retrieved_at=CREATED,
        version="1",
        citation="Example Archive, Evidence record",
    )
    return CommunityProposal(
        proposal_id="proposal:example-1",
        contributor=alice,
        contribution_license_id="CC-BY-4.0",
        contribution_attribution=alice.attribution,
        changes=[
            ProposedChange(
                change_id="change:geometry-1",
                kind=ContributionKind.GEOMETRY,
                target_record_id="place:example",
                summary="Correct the reviewed extent using the cited survey.",
                proposed_value={
                    "type": "Polygon",
                    "coordinates": [[[10, 20], [11, 20], [11, 21], [10, 20]]],
                },
            )
        ],
        source_evidence=[
            ProposalEvidence(
                evidence_id="evidence:survey-1",
                supports_change_ids=["change:geometry-1"],
                source_ref=source,
                explanation="The survey supplies an explicit bounded extent.",
            )
        ],
        supersedes_proposal_ids=["proposal:example-0"],
        created_at=CREATED,
        updated_at=CREATED,
    )


def review_event(
    action: ProposalReviewAction,
    offset_hours: int,
) -> ProposalReviewEvent:
    return ProposalReviewEvent(
        event_id=f"review:{action.value}-{offset_hours}",
        action=action,
        actor=contributor("editor", "Example Editor"),
        created_at=CREATED + timedelta(hours=offset_hours),
        rationale=f"Editorial action: {action.value}.",
    )


def test_proposal_lifecycle_preserves_attribution_evidence_and_supersession() -> None:
    proposed = proposal()
    in_review = advance_proposal(
        proposed,
        ProposalStatus.IN_REVIEW,
        review_event(ProposalReviewAction.SUBMITTED_FOR_REVIEW, 1),
    )
    accepted = advance_proposal(
        in_review,
        ProposalStatus.ACCEPTED,
        review_event(ProposalReviewAction.ACCEPTED, 2),
    )

    assert proposed.status == ProposalStatus.PROPOSED
    assert accepted.revision == 3
    assert accepted.contributor.attribution == "Contribution by Alice Example"
    assert accepted.contribution_license_id == "CC-BY-4.0"
    assert accepted.source_evidence[0].source_ref.citation
    assert accepted.supersedes_proposal_ids == ["proposal:example-0"]
    assert [event.action for event in accepted.review_history] == [
        ProposalReviewAction.SUBMITTED_FOR_REVIEW,
        ProposalReviewAction.ACCEPTED,
    ]

    receipt = create_release_receipt(
        accepted,
        receipt_id="proposal-release:example-1",
        release_build_id="abc123",
        published_record_ids=["place:example"],
        released_at=CREATED + timedelta(hours=3),
    )
    assert receipt.proposal_id == accepted.proposal_id
    assert receipt.proposal_revision == accepted.revision
    assert receipt.decision_event_id == accepted.review_history[-1].event_id
    assert receipt.semantics == "accepted-proposal-release-receipt-not-canonical-record"


def test_rejected_proposal_can_never_receive_a_release_receipt() -> None:
    in_review = advance_proposal(
        proposal(),
        ProposalStatus.IN_REVIEW,
        review_event(ProposalReviewAction.SUBMITTED_FOR_REVIEW, 1),
    )
    rejected = advance_proposal(
        in_review,
        ProposalStatus.REJECTED,
        review_event(ProposalReviewAction.REJECTED, 2),
    )

    with pytest.raises(ValueError, match="only accepted proposals"):
        create_release_receipt(
            rejected,
            receipt_id="proposal-release:rejected",
            release_build_id="abc123",
            published_record_ids=["place:must-not-publish"],
            released_at=CREATED + timedelta(hours=3),
        )
    with pytest.raises(ValueError, match="terminal"):
        advance_proposal(
            rejected,
            ProposalStatus.IN_REVIEW,
            review_event(ProposalReviewAction.SUBMITTED_FOR_REVIEW, 4),
        )


def test_status_cannot_claim_acceptance_without_review_history() -> None:
    payload = proposal().model_dump(mode="python")
    payload["status"] = ProposalStatus.ACCEPTED
    with pytest.raises(ValidationError, match="final review action accepted"):
        CommunityProposal.model_validate(payload)


def test_evidence_cannot_point_outside_its_bounded_proposal() -> None:
    payload = proposal().model_dump(mode="python")
    payload["source_evidence"][0]["supports_change_ids"] = ["change:other"]
    with pytest.raises(ValidationError, match="same proposal"):
        CommunityProposal.model_validate(payload)


def test_lifecycle_rejects_skipped_review_and_mismatched_decisions() -> None:
    with pytest.raises(ValueError, match="cannot transition"):
        advance_proposal(
            proposal(),
            ProposalStatus.ACCEPTED,
            review_event(ProposalReviewAction.ACCEPTED, 1),
        )
    with pytest.raises(ValueError, match="requires submitted_for_review"):
        advance_proposal(
            proposal(),
            ProposalStatus.IN_REVIEW,
            review_event(ProposalReviewAction.REJECTED, 1),
        )
