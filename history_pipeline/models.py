from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class FeatureKind(StrEnum):
    POLITY = "polity"
    CULTURAL_REGION = "cultural_region"
    SETTLEMENT = "settlement"
    ARCHAEOLOGICAL_SITE = "archaeological_site"
    ROUTE = "route"
    EVENT = "event"
    ARCHIVAL_MAP = "archival_map"
    SOCIAL_GROUP = "social_group"
    MOBILE_GROUP = "mobile_group"
    CULTURAL_NETWORK = "cultural_network"


class EntityKind(StrEnum):
    """Stable product-level identity classes, independent of source vocabularies."""

    PERSON = "person"
    EVENT = "event"
    INSTITUTION = "institution"
    WORK = "work"
    ARTIFACT = "artifact"
    ROUTE = "route"
    PLACE = "place"
    POLITY = "polity"
    CONCEPT = "concept"
    OTHER = "other"


class HistoricalTheme(StrEnum):
    """Broad, non-exclusive discovery lenses attached by a reviewed source mapping."""

    POWER = "power"
    BELIEF = "belief"
    KNOWLEDGE = "knowledge"
    CULTURE = "culture"
    TRADE = "trade"


class SpatialMeaning(StrEnum):
    LEGAL_BOUNDARY = "legal_boundary"
    TERRITORIAL_CONTROL = "territorial_control"
    TERRITORIAL_CLAIM = "territorial_claim"
    OCCUPATION = "occupation"
    TRIBUTARY_RELATIONSHIP = "tributary_relationship"
    CULTURAL_REGION = "cultural_region"
    INFLUENCE_ZONE = "influence_zone"
    LOCATION = "location"
    ROUTE = "route"
    MOBILITY_RANGE = "mobility_range"
    SEASONAL_USE = "seasonal_use"
    NETWORK = "network"
    UNKNOWN = "unknown"


class DatePrecision(StrEnum):
    EXACT = "exact"
    YEAR = "year"
    DECADE = "decade"
    CENTURY = "century"
    RANGE = "range"
    UNKNOWN = "unknown"


class ConfidenceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    CONTESTED = "contested"
    REJECTED = "rejected"


class SourceRole(StrEnum):
    """The evidentiary job a source is allowed to perform in the product."""

    HISTORICAL_GEOMETRY = "historical_geometry"
    GAZETTEER = "gazetteer"
    CHRONOLOGY = "chronology"
    AUTHORITY_METADATA = "authority_metadata"
    TERTIARY_SUMMARY = "tertiary_summary"
    PRIMARY_SOURCE = "primary_source"
    SCHOLARLY_ASSERTION = "scholarly_assertion"
    INDICATOR = "indicator"
    MEDIA = "media"
    BIBLIOGRAPHY = "bibliography"


class CommercialRedistribution(StrEnum):
    ALLOWED = "allowed"
    CONDITIONAL = "conditional"
    PROHIBITED = "prohibited"
    UNREVIEWED = "unreviewed"


class DistributionTier(StrEnum):
    OPEN_CORE = "open_core"
    RESEARCH_ONLY = "research_only"


class RightsScope(StrEnum):
    METADATA = "metadata"
    MEDIA = "media"
    GEOREFERENCE = "georeference"


class NameKind(StrEnum):
    """How a historical name relates to the people and source using it."""

    ENDONYM = "endonym"
    EXONYM = "exonym"
    OFFICIAL = "official"
    CONVENTIONAL = "conventional"
    TRANSLITERATED = "transliterated"
    TRANSLATED = "translated"
    SHORT = "short"
    UNKNOWN = "unknown"


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: ConfidenceGrade
    rationale: str = Field(min_length=1)


class TemporalUncertainty(BaseModel):
    """Uncertainty envelope around the canonical rendering interval.

    The four bounds describe what a source permits; they are not samples to average.
    ``valid_from``/``valid_to`` on the feature remain the interval used for map filtering.
    """

    model_config = ConfigDict(extra="forbid")

    earliest_start: int | None = None
    latest_start: int | None = None
    earliest_end: int | None = None
    latest_end: int | None = None
    circa: bool = False
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> TemporalUncertainty:
        values = (
            self.earliest_start,
            self.latest_start,
            self.earliest_end,
            self.latest_end,
        )
        if any(value == 0 for value in values):
            raise ValueError("Historical years use BCE/CE notation and cannot contain year zero")
        if (
            self.earliest_start is not None
            and self.latest_start is not None
            and self.earliest_start > self.latest_start
        ):
            raise ValueError("earliest_start must not be later than latest_start")
        if (
            self.earliest_end is not None
            and self.latest_end is not None
            and self.earliest_end > self.latest_end
        ):
            raise ValueError("earliest_end must not be later than latest_end")
        return self


class SpatialUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal[
        "source_geometry",
        "accuracy_radius",
        "bounding_extent",
        "multiple_reconstructions",
        "unknown",
    ]
    accuracy_meters: float | None = Field(default=None, gt=0)
    rationale: str = Field(min_length=1)


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    record_id: str
    title: str
    publisher: str
    url: HttpUrl
    license_id: str
    retrieved_at: datetime
    version: str | None = None
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    citation: str
    modified: bool = False


class RightsReference(BaseModel):
    """A rights decision for one kind of material, never an implicit relicense."""

    model_config = ConfigDict(extra="forbid")

    scope: RightsScope
    license_id: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    rights_uri: HttpUrl | None = None


class ReleaseRightsApproval(BaseModel):
    """One release decision for one material scope."""

    model_config = ConfigDict(extra="forbid")

    scope: RightsScope
    status: Literal["approved"]
    decision_id: str = Field(pattern=r"^rights:[a-z0-9][a-z0-9:_-]+$")
    reviewed_by: str = Field(min_length=1)
    reviewed_at: AwareDatetime
    rationale: str = Field(min_length=1)


class HistoricalMapRendering(BaseModel):
    """A release-local raster positioned from a reviewed IIIF georeference."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["iiif-georeference-maplibre-image-v1"] = (
        "iiif-georeference-maplibre-image-v1"
    )
    image_path: str = Field(
        pattern=r"^historical-maps/[a-zA-Z0-9][a-zA-Z0-9._/-]*\.(png|jpg|jpeg|webp)$"
    )
    image_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    coordinates: list[tuple[float, float]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_rendering(self) -> HistoricalMapRendering:
        if ".." in self.image_path.split("/"):
            raise ValueError("historical map image_path cannot traverse release directories")
        if len(set(self.coordinates)) != 4:
            raise ValueError("historical map rendering requires four distinct corners")
        for longitude, latitude in self.coordinates:
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError("historical map rendering coordinates must be WGS84")
        return self


class TransformationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    input_record_ids: list[str] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AuthorityMatch(BaseModel):
    """A reviewable authority candidate; a score never silently establishes identity."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    match_id: str = Field(pattern=r"^match:[a-f0-9]{16}$")
    subject_id: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)
    authority_namespace: str = Field(min_length=1)
    label: str = Field(min_length=1)
    relation: Literal["exact_match", "close_match", "candidate"]
    review_status: Literal["proposed", "accepted", "rejected"]
    confidence_score: float = Field(ge=0, le=100)
    confidence: Confidence
    source_ref: SourceReference
    rights: RightsReference
    lineage: list[TransformationStep] = Field(min_length=1)


class HistoricalMapMetadata(BaseModel):
    """Build-time metadata for a georeferenced IIIF map; no image bytes are embedded."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    map_id: str = Field(pattern=r"^map:[a-f0-9]{16}$")
    manifest_id: HttpUrl
    canvas_id: HttpUrl
    annotation_id: HttpUrl
    label: str = Field(min_length=1)
    depicted_date: str = Field(min_length=1)
    providers: list[str] = Field(min_length=1)
    required_statement: str = Field(min_length=1)
    metadata_rights: RightsReference
    image_rights: RightsReference
    georeference_rights: RightsReference
    georeference_confidence: Confidence
    source_refs: list[SourceReference] = Field(min_length=2)
    lineage: list[TransformationStep] = Field(min_length=1)
    known_limitations: list[str] = Field(default_factory=list)
    release_rights_approvals: list[ReleaseRightsApproval] = Field(default_factory=list)
    rendering: HistoricalMapRendering | None = None

    @model_validator(mode="after")
    def require_separate_rights_scopes(self) -> HistoricalMapMetadata:
        scopes = (
            self.metadata_rights.scope,
            self.image_rights.scope,
            self.georeference_rights.scope,
        )
        if scopes != (
            RightsScope.METADATA,
            RightsScope.MEDIA,
            RightsScope.GEOREFERENCE,
        ):
            raise ValueError("map rights must remain separated by material scope")
        if self.rendering is not None:
            approval_scopes = [approval.scope for approval in self.release_rights_approvals]
            if approval_scopes != [
                RightsScope.METADATA,
                RightsScope.MEDIA,
                RightsScope.GEOREFERENCE,
            ]:
                raise ValueError(
                    "renderable maps require separately ordered metadata, media, "
                    "and georeference release approvals"
                )
            if len({approval.decision_id for approval in self.release_rights_approvals}) != 3:
                raise ValueError("renderable map rights decisions must be distinct")
            if not self.known_limitations:
                raise ValueError("renderable maps require known limitations")
        return self


class IntegrationIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["build-time-reviewed-source-integrations"] = (
        "build-time-reviewed-source-integrations"
    )
    authority_matches_path: str = "integrations/authority-matches.ndjson"
    authority_match_count: int = Field(ge=0)
    historical_maps_path: str = "integrations/historical-maps.ndjson"
    historical_map_count: int = Field(ge=0)


class ContributionKind(StrEnum):
    PLACE = "place"
    NAME = "name"
    DATE = "date"
    GEOMETRY = "geometry"
    SOURCE = "source"
    GEOREFERENCE = "georeference"


class ProposalStatus(StrEnum):
    PROPOSED = "proposed"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProposalReviewAction(StrEnum):
    SUBMITTED_FOR_REVIEW = "submitted_for_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProposalContributor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contributor_id: str = Field(pattern=r"^contributor:[a-z0-9][a-z0-9:_-]+$")
    display_name: str = Field(min_length=1)
    attribution: str = Field(min_length=1)


class ProposedChange(BaseModel):
    """A bounded patch proposal, never a canonical record."""

    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(pattern=r"^change:[a-z0-9][a-z0-9:_-]+$")
    kind: ContributionKind
    target_record_id: str | None = None
    summary: str = Field(min_length=1)
    proposed_value: dict[str, Any]


class ProposalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^evidence:[a-z0-9][a-z0-9:_-]+$")
    supports_change_ids: list[str] = Field(min_length=1)
    source_ref: SourceReference
    explanation: str = Field(min_length=1)


class ProposalDiscussionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(pattern=r"^discussion:[a-z0-9][a-z0-9:_-]+$")
    author: ProposalContributor
    created_at: AwareDatetime
    body: str = Field(min_length=1)


class ProposalReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=r"^review:[a-z0-9][a-z0-9:_-]+$")
    action: ProposalReviewAction
    actor: ProposalContributor
    created_at: AwareDatetime
    rationale: str = Field(min_length=1)


class CommunityProposal(BaseModel):
    """Editorial input kept structurally separate from published canonical records."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["community-proposal-not-canonical-record"] = (
        "community-proposal-not-canonical-record"
    )
    proposal_id: str = Field(pattern=r"^proposal:[a-z0-9][a-z0-9:_-]+$")
    revision: int = Field(default=1, ge=1)
    status: ProposalStatus = ProposalStatus.PROPOSED
    contributor: ProposalContributor
    contribution_license_id: str = Field(min_length=1)
    contribution_attribution: str = Field(min_length=1)
    changes: list[ProposedChange] = Field(min_length=1, max_length=100)
    source_evidence: list[ProposalEvidence] = Field(min_length=1, max_length=100)
    discussion_history: list[ProposalDiscussionEntry] = Field(default_factory=list)
    review_history: list[ProposalReviewEvent] = Field(default_factory=list)
    supersedes_proposal_ids: list[str] = Field(default_factory=list)
    superseded_by_proposal_ids: list[str] = Field(default_factory=list)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_lifecycle(self) -> CommunityProposal:
        if self.updated_at < self.created_at:
            raise ValueError("proposal updated_at cannot precede created_at")
        change_ids = [change.change_id for change in self.changes]
        if len(change_ids) != len(set(change_ids)):
            raise ValueError("proposal change IDs must be unique")
        known_changes = set(change_ids)
        if any(
            not set(evidence.supports_change_ids).issubset(known_changes)
            for evidence in self.source_evidence
        ):
            raise ValueError("proposal evidence must reference changes in the same proposal")
        if any(
            self.proposal_id in links
            for links in (
                self.supersedes_proposal_ids,
                self.superseded_by_proposal_ids,
            )
        ):
            raise ValueError("a proposal cannot supersede itself")
        if set(self.supersedes_proposal_ids) & set(self.superseded_by_proposal_ids):
            raise ValueError("proposal supersession directions cannot overlap")
        expected_action = {
            ProposalStatus.PROPOSED: None,
            ProposalStatus.IN_REVIEW: ProposalReviewAction.SUBMITTED_FOR_REVIEW,
            ProposalStatus.ACCEPTED: ProposalReviewAction.ACCEPTED,
            ProposalStatus.REJECTED: ProposalReviewAction.REJECTED,
        }[self.status]
        last_action = self.review_history[-1].action if self.review_history else None
        if last_action != expected_action:
            raise ValueError(
                f"proposal status {self.status.value} requires final review action "
                f"{expected_action.value if expected_action else 'none'}"
            )
        return self


class AcceptedProposalRelease(BaseModel):
    """Immutable linkage from an accepted proposal revision to a release."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["accepted-proposal-release-receipt-not-canonical-record"] = (
        "accepted-proposal-release-receipt-not-canonical-record"
    )
    receipt_id: str = Field(pattern=r"^proposal-release:[a-z0-9][a-z0-9:_-]+$")
    proposal_id: str = Field(pattern=r"^proposal:[a-z0-9][a-z0-9:_-]+$")
    proposal_revision: int = Field(ge=1)
    proposal_status: Literal["accepted"] = "accepted"
    decision_event_id: str = Field(pattern=r"^review:[a-z0-9][a-z0-9:_-]+$")
    proposal_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    release_build_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    published_record_ids: list[str] = Field(min_length=1)
    released_at: AwareDatetime


class HistoricalName(BaseModel):
    """A sourced name attestation with its own chronology and perspective.

    A name is not an identity key and does not inherit timeless validity merely because the
    associated place or geometry spans a longer interval.
    """

    model_config = ConfigDict(extra="forbid")

    name_id: str = Field(pattern=r"^name:[a-f0-9]{16}$")
    text: str = Field(min_length=1)
    language: str = Field(min_length=1)
    script: str | None = Field(default=None, pattern=r"^[A-Z][a-z]{3}$")
    name_kind: NameKind = NameKind.UNKNOWN
    valid_from: int
    valid_to: int
    date_precision: DatePrecision
    temporal_confidence: Confidence
    primary: bool = False
    perspective: str | None = None
    temporal_basis: Literal["attested", "feature_interval"] = "attested"
    source_refs: list[SourceReference] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self) -> HistoricalName:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical name years cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("Historical name valid_from must not be later than valid_to")
        return self


class HistoricalFeature(BaseModel):
    """Canonical JSON representation used at integration boundaries.

    Geometry uses RFC 7946 GeoJSON. Canonical analytical storage is GeoParquet.
    Years use historical notation: negative is BCE, positive is CE, and zero is invalid.
    """

    model_config = ConfigDict(extra="forbid")

    feature_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:_-]+$")
    kind: FeatureKind
    spatial_meaning: SpatialMeaning
    names: dict[str, str] = Field(min_length=1)
    name_attestations: list[HistoricalName] = Field(default_factory=list)
    valid_from: int
    valid_to: int
    date_precision: DatePrecision
    geometry: dict[str, Any]
    temporal_confidence: Confidence
    spatial_confidence: Confidence
    interpretive_confidence: Confidence
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    source_refs: list[SourceReference] = Field(min_length=1)
    themes: list[HistoricalTheme] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    wikidata_ids: list[str] = Field(default_factory=list)
    wikipedia_titles: dict[str, str] = Field(default_factory=dict)
    min_display_zoom: float = Field(default=0, ge=0, le=24)
    dispute_group: str | None = None
    perspective: str | None = None
    temporal_uncertainty: TemporalUncertainty | None = None
    spatial_uncertainty: SpatialUncertainty | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_historical_interval(self) -> HistoricalFeature:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical years use BCE/CE notation and cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from must be earlier than or equal to valid_to")
        if self.review_status == ReviewStatus.VERIFIED and len(self.source_refs) < 1:
            raise ValueError("A verified feature must retain its source")
        if len(self.entity_ids) != len(set(self.entity_ids)):
            raise ValueError("entity_ids must be unique")
        if len(self.themes) != len(set(self.themes)):
            raise ValueError("themes must be unique")
        if not self.name_attestations:
            attestations: list[HistoricalName] = []
            preferred_language = "en" if "en" in self.names else next(iter(self.names))
            for language, text in self.names.items():
                identity = "\x1f".join(
                    (self.feature_id, language, text, str(self.valid_from), str(self.valid_to))
                )
                attestations.append(
                    HistoricalName(
                        name_id=f"name:{hashlib.sha256(identity.encode()).hexdigest()[:16]}",
                        text=text,
                        language=language,
                        valid_from=self.valid_from,
                        valid_to=self.valid_to,
                        date_precision=self.date_precision,
                        temporal_confidence=self.temporal_confidence,
                        primary=language == preferred_language,
                        perspective=self.perspective,
                        temporal_basis="feature_interval",
                        source_refs=self.source_refs,
                    )
                )
            self.name_attestations = attestations
        name_ids = [attestation.name_id for attestation in self.name_attestations]
        if len(name_ids) != len(set(name_ids)):
            raise ValueError("Historical name IDs must be unique within a feature")
        for attestation in self.name_attestations:
            if attestation.valid_to < self.valid_from or attestation.valid_from > self.valid_to:
                raise ValueError("A historical name must overlap its feature interval")
        return self


class ThemeRole(StrEnum):
    """How strongly a thematic assertion should affect discovery and rendering."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTEXTUAL = "contextual"


class ThemeClassificationBasis(StrEnum):
    """The bounded evidence that permits a thematic classification."""

    EXPLICIT_SOURCE_TYPE = "explicit_source_type"
    EXPLICIT_SOURCE_RELATION = "explicit_source_relation"
    REVIEWED_EDITORIAL = "reviewed_editorial"


class ThemeRule(BaseModel):
    """A reviewed, deterministic rule over normalized structured fields.

    Every supplied selector is conjunctive. ``match_any`` is exact after value
    normalization; it is never a free-text or substring search.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^theme-rule:[a-z0-9][a-z0-9_-]+$")
    source_ids: list[str] = Field(default_factory=list)
    feature_kinds: list[FeatureKind] = Field(default_factory=list)
    spatial_meanings: list[SpatialMeaning] = Field(default_factory=list)
    property_path: str | None = Field(default=None, pattern=r"^properties\.[a-z][a-z0-9_]*$")
    match_any: list[str] = Field(default_factory=list)
    theme: HistoricalTheme
    subtheme: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    role: ThemeRole = ThemeRole.PRIMARY
    classification_basis: ThemeClassificationBasis
    confidence: Confidence
    review_status: ReviewStatus = ReviewStatus.PROVISIONAL
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_selectors(self) -> ThemeRule:
        if not any(
            (self.source_ids, self.feature_kinds, self.spatial_meanings, self.property_path)
        ):
            raise ValueError("A theme rule must declare at least one structured selector")
        if self.property_path and not self.match_any:
            raise ValueError("A property theme rule must declare match_any values")
        if self.match_any and not self.property_path:
            raise ValueError("match_any requires property_path")
        collections = (
            self.source_ids,
            self.feature_kinds,
            self.spatial_meanings,
            self.match_any,
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("Theme rule selector values must be unique")
        if self.review_status == ReviewStatus.REJECTED:
            raise ValueError("Rejected theme rules cannot be published")
        return self


class ThemeRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    authored_by: str = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    rules: list[ThemeRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rule_ids(self) -> ThemeRuleSet:
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Theme rule IDs must be unique")
        return self


class ThematicAssertion(BaseModel):
    """A sourced, time-bounded explanation for one feature appearing in a lens."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(pattern=r"^theme:[a-f0-9]{16}$")
    subject_id: str
    subject_kind: FeatureKind
    feature_ids: list[str] = Field(min_length=1)
    entity_ids: list[str] = Field(default_factory=list)
    theme: HistoricalTheme
    subtheme: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    role: ThemeRole
    valid_from: int
    valid_to: int
    classification_basis: ThemeClassificationBasis
    rule_id: str = Field(pattern=r"^theme-rule:[a-z0-9][a-z0-9_-]+$")
    matched_values: list[str] = Field(default_factory=list)
    confidence: Confidence
    review_status: ReviewStatus
    rationale: str = Field(min_length=1)
    source_refs: list[SourceReference] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_assertion(self) -> ThematicAssertion:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Thematic assertion years cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("Thematic assertion valid_from must not exceed valid_to")
        for values in (self.feature_ids, self.entity_ids, self.matched_values):
            if len(values) != len(set(values)):
                raise ValueError("Thematic assertion lists must contain unique values")
        if self.subject_id not in self.feature_ids:
            raise ValueError("A feature assertion must include its subject in feature_ids")
        if self.review_status == ReviewStatus.REJECTED:
            raise ValueError("Rejected thematic assertions cannot be published")
        return self


class WikidataSnak(BaseModel):
    """A bounded normalized qualifier/reference snak from one Wikidata statement."""

    model_config = ConfigDict(extra="forbid")

    predicate: str = Field(pattern=r"^P[1-9][0-9]*$")
    datatype: str | None = None
    value: Any


class WikidataReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_hash: str | None = None
    snaks: list[WikidataSnak] = Field(default_factory=list)


class EntityDateClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicate: str = Field(pattern=r"^P[1-9][0-9]*$")
    time: str
    year: int | None = None
    precision: int | None = None
    calendar_model: str | None = None
    before: int = Field(default=0, ge=0)
    after: int = Field(default=0, ge=0)
    rank: Literal["preferred", "normal", "deprecated"] = "normal"
    statement_id: str | None = None
    qualifiers: list[WikidataSnak] = Field(default_factory=list)
    references: list[WikidataReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_year_zero(self) -> EntityDateClaim:
        if self.year == 0:
            raise ValueError("Historical years cannot contain year zero")
        return self


class EntityRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicate: str = Field(pattern=r"^P[1-9][0-9]*$")
    relation_type: str
    target_entity_id: str = Field(pattern=r"^wikidata:Q[1-9][0-9]*$")
    rank: Literal["preferred", "normal", "deprecated"] = "normal"
    statement_id: str | None = None
    qualifiers: list[WikidataSnak] = Field(default_factory=list)
    references: list[WikidataReference] = Field(default_factory=list)


class WikipediaSitelink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl


class EntityCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: float | None = Field(default=None, ge=0)
    globe: str | None = None
    rank: Literal["preferred", "normal", "deprecated"] = "normal"


class HistoricalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    entity_type: str
    entity_kind: EntityKind = EntityKind.OTHER
    names: dict[str, str]
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    valid_from: int | None = None
    valid_to: int | None = None
    date_precision: DatePrecision | None = None
    temporal_uncertainty: TemporalUncertainty | None = None
    temporal_confidence: Confidence | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    wikidata_id: str | None = Field(default=None, pattern=r"^Q[1-9][0-9]*$")
    descriptions: dict[str, str] = Field(default_factory=dict)
    links: dict[str, HttpUrl] = Field(default_factory=dict)
    sitelinks: dict[str, WikipediaSitelink] = Field(default_factory=dict)
    date_claims: list[EntityDateClaim] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)
    commons_images: list[str] = Field(default_factory=list)
    commons_categories: list[str] = Field(default_factory=list)
    coordinates: list[EntityCoordinate] = Field(default_factory=list)
    redirects_from: list[str] = Field(default_factory=list)
    context_depth: Literal[0, 1] = 0
    discovered_from_entity_ids: list[str] = Field(default_factory=list)
    discovery_predicates: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def derive_entity_kind(cls, value: Any) -> Any:
        """Read pre-1.9 records without replacing their source-specific entity_type."""

        if not isinstance(value, dict) or value.get("entity_kind"):
            return value
        legacy_type = str(value.get("entity_type", ""))
        inferred = {
            "human": EntityKind.PERSON,
            "person": EntityKind.PERSON,
            "event": EntityKind.EVENT,
            "occurrence": EntityKind.EVENT,
            "historical_event": EntityKind.EVENT,
            "war": EntityKind.EVENT,
            "battle": EntityKind.EVENT,
            "treaty": EntityKind.EVENT,
            "business_or_organization": EntityKind.INSTITUTION,
            "organization": EntityKind.INSTITUTION,
            "institution": EntityKind.INSTITUTION,
            "written_work": EntityKind.WORK,
            "work": EntityKind.WORK,
            "book": EntityKind.WORK,
            "artifact": EntityKind.ARTIFACT,
            "route": EntityKind.ROUTE,
            "human_settlement": EntityKind.PLACE,
            "place": EntityKind.PLACE,
            "country": EntityKind.POLITY,
            "historical_country": EntityKind.POLITY,
            "sovereign_state": EntityKind.POLITY,
            "polity": EntityKind.POLITY,
            "concept": EntityKind.CONCEPT,
        }.get(legacy_type, EntityKind.OTHER)
        return {**value, "entity_kind": inferred}

    @model_validator(mode="after")
    def validate_entity_chronology(self) -> HistoricalEntity:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical entity years cannot contain year zero")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from > self.valid_to
        ):
            raise ValueError("Historical entity valid_from must not exceed valid_to")
        if self.date_precision is not None and (self.valid_from is None or self.valid_to is None):
            raise ValueError("Entity date_precision requires a complete validity interval")
        if self.temporal_uncertainty is not None and (
            self.valid_from is None or self.valid_to is None
        ):
            raise ValueError("Entity temporal_uncertainty requires a complete validity interval")
        if len(self.names) < 1:
            raise ValueError("Historical entities require at least one name")
        for values in (
            self.redirects_from,
            self.discovered_from_entity_ids,
            self.discovery_predicates,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Historical entity identifier lists must be unique")
        return self


class AssertionObjectKind(StrEnum):
    ENTITY = "entity"
    TEXT = "text"
    YEAR = "year"


class AssertionObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AssertionObjectKind
    entity_id: str | None = None
    value: str | None = None
    year: int | None = None

    @model_validator(mode="after")
    def validate_typed_value(self) -> AssertionObject:
        supplied = sum(item is not None for item in (self.entity_id, self.value, self.year))
        if supplied != 1:
            raise ValueError("An assertion object must contain exactly one typed value")
        if self.kind == AssertionObjectKind.ENTITY and self.entity_id is None:
            raise ValueError("An entity assertion object requires entity_id")
        if self.kind == AssertionObjectKind.TEXT and self.value is None:
            raise ValueError("A text assertion object requires value")
        if self.kind == AssertionObjectKind.YEAR and self.year is None:
            raise ValueError("A year assertion object requires year")
        if self.year == 0:
            raise ValueError("Historical assertion years cannot contain year zero")
        return self


class AssertionEvidenceBasis(StrEnum):
    PRIMARY_SOURCE_METADATA = "primary_source_metadata"
    AUTHORITY_METADATA = "authority_metadata"
    TERTIARY_SUMMARY = "tertiary_summary"
    SCHOLARLY_ASSERTION = "scholarly_assertion"
    REVIEWED_EDITORIAL_LINK = "reviewed_editorial_link"


class EvidenceAssertion(BaseModel):
    """One evidence-backed structured fact, never generated narrative prose."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(pattern=r"^assertion:[a-z0-9][a-z0-9:_-]+$")
    representation: Literal["structured_sourced_assertion"] = "structured_sourced_assertion"
    subject_entity_ids: list[str] = Field(min_length=1)
    feature_ids: list[str] = Field(default_factory=list)
    predicate: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    object: AssertionObject
    valid_from: int
    valid_to: int
    date_precision: DatePrecision
    temporal_uncertainty: TemporalUncertainty | None = None
    confidence: Confidence
    evidence_basis: AssertionEvidenceBasis
    review_status: ReviewStatus = ReviewStatus.PROVISIONAL
    source_refs: list[SourceReference] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_assertion(self) -> EvidenceAssertion:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical assertion years cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("Assertion valid_from must not exceed valid_to")
        for values in (self.subject_entity_ids, self.feature_ids):
            if len(values) != len(set(values)):
                raise ValueError("Evidence assertion identifier lists must be unique")
        if self.review_status == ReviewStatus.REJECTED:
            raise ValueError("Rejected evidence assertions cannot be published")
        return self


class ContentRole(StrEnum):
    PRIMARY_SOURCE = "primary_source"
    TERTIARY_SUMMARY = "tertiary_summary"
    PROJECT_INTERPRETATION = "project_interpretation"


class DossierKind(StrEnum):
    SOURCE_EXTRACT = "source_extract"
    GENERATED_EDITORIAL = "generated_editorial"


class HistoricalDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    dossier_kind: Literal[DossierKind.SOURCE_EXTRACT] = DossierKind.SOURCE_EXTRACT
    title: str
    language: str
    entity_ids: list[str] = Field(default_factory=list)
    content_role: ContentRole = ContentRole.TERTIARY_SUMMARY
    extract: str
    url: HttpUrl
    page_id: int
    revision_id: int | None = None
    revision_timestamp: datetime | None = None
    requested_titles: list[str] = Field(default_factory=list)
    redirects_from: list[str] = Field(default_factory=list)
    content_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_ref: SourceReference


class EvidencePassage(BaseModel):
    """An approved, byte-stable passage within one evidence document."""

    model_config = ConfigDict(extra="forbid")

    passage_id: str = Field(pattern=r"^passage:[a-z0-9][a-z0-9:_-]+$")
    source_field_path: str = Field(pattern=r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
    assertion_ids: list[str] = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_passage(self) -> EvidencePassage:
        if self.start_char >= self.end_char:
            raise ValueError("Evidence passage start_char must be before end_char")
        if len(self.assertion_ids) != len(set(self.assertion_ids)):
            raise ValueError("Evidence passage assertion IDs must be unique")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("Evidence passage text checksum does not match")
        return self


class EvidenceDocument(BaseModel):
    """One revision-pinned source document admitted to an evidence bundle."""

    model_config = ConfigDict(extra="forbid")

    source_ref: SourceReference
    source_revision_id: str = Field(min_length=1)
    source_revision_field_path: str = Field(
        pattern=r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$"
    )
    attribution: str = Field(min_length=1)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    passages: list[EvidencePassage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_document(self) -> EvidenceDocument:
        if self.source_ref.version != self.source_revision_id:
            raise ValueError("Evidence source revision must match source_ref.version")
        if self.source_ref.citation != self.attribution:
            raise ValueError("Evidence attribution must match the preserved source citation")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("Evidence document text checksum does not match")
        passage_ids = [passage.passage_id for passage in self.passages]
        if len(passage_ids) != len(set(passage_ids)):
            raise ValueError("Evidence passage IDs must be unique within a source")
        for passage in self.passages:
            if passage.end_char > len(self.text):
                raise ValueError(f"Evidence passage is outside its source: {passage.passage_id}")
            if self.text[passage.start_char : passage.end_char] != passage.text:
                raise ValueError(f"Evidence passage span does not match: {passage.passage_id}")
        return self


class ApprovedEvidenceBundle(BaseModel):
    """The complete and only historical context allowed into dossier generation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    bundle_id: str = Field(pattern=r"^evidence-bundle:[a-z0-9][a-z0-9:_-]+$")
    subject_entity_ids: list[str] = Field(min_length=1)
    feature_ids: list[str] = Field(default_factory=list)
    assertions: list[EvidenceAssertion] = Field(default_factory=list)
    sources: list[EvidenceDocument] = Field(default_factory=list)
    approved_by: str = Field(min_length=1)
    approved_at: AwareDatetime

    @model_validator(mode="after")
    def validate_bundle_graph(self) -> ApprovedEvidenceBundle:
        for values, label in (
            (self.subject_entity_ids, "subject entity"),
            (self.feature_ids, "feature"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Evidence bundle {label} IDs must be unique")
        assertion_ids = [assertion.assertion_id for assertion in self.assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("Evidence bundle assertion IDs must be unique")
        known_assertions = set(assertion_ids)
        passage_assertions: set[str] = set()
        passage_keys: list[tuple[str, str]] = []
        for source in self.sources:
            for passage in source.passages:
                passage_keys.append((source.source_ref.source_id, passage.passage_id))
                unknown = set(passage.assertion_ids) - known_assertions
                if unknown:
                    raise ValueError(
                        f"Evidence passage references unknown assertions: {sorted(unknown)}"
                    )
                passage_assertions.update(passage.assertion_ids)
        if len(passage_keys) != len(set(passage_keys)):
            raise ValueError("Evidence passage IDs must be unique within each source")
        if passage_assertions != known_assertions:
            missing = sorted(known_assertions - passage_assertions)
            raise ValueError(f"Evidence assertions have no approved passage: {missing}")
        if bool(self.assertions) != bool(self.sources):
            raise ValueError(
                "Evidence bundles must contain both assertions and sources, or neither"
            )
        return self


class EvidenceCitation(BaseModel):
    """An exact character span used to support one generated claim."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    passage_id: str = Field(pattern=r"^passage:[a-z0-9][a-z0-9:_-]+$")
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span_order(self) -> EvidenceCitation:
        if self.start_char >= self.end_char:
            raise ValueError("Citation start_char must be before end_char")
        return self


class DossierDraftClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^draft-claim:[a-z0-9][a-z0-9:_-]+$")
    text: str = Field(min_length=1)
    entity_ids: list[str] = Field(min_length=1)
    valid_from: int
    valid_to: int
    date_precision: DatePrecision
    supporting_assertion_ids: list[str] = Field(min_length=1)
    citations: list[EvidenceCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_shape(self) -> DossierDraftClaim:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Dossier claims use BCE/CE notation and cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("Dossier claim valid_from must not exceed valid_to")
        for values, label in (
            (self.entity_ids, "entity"),
            (self.supporting_assertion_ids, "supporting assertion"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Dossier claim {label} IDs must be unique")
        return self


class DossierEvidenceConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str = Field(pattern=r"^conflict:[a-z0-9][a-z0-9:_-]+$")
    assertion_ids: list[str] = Field(min_length=2)
    explanation: str = Field(min_length=1)
    citations: list[EvidenceCitation] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_assertions(self) -> DossierEvidenceConflict:
        if len(self.assertion_ids) != len(set(self.assertion_ids)):
            raise ValueError("Conflict assertion IDs must be unique")
        return self


class DossierDraftResult(StrEnum):
    DRAFT = "draft"
    NO_EVIDENCE = "no_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class DossierDraftContent(BaseModel):
    """Strict model output; provenance is added outside the model response."""

    model_config = ConfigDict(extra="forbid")

    result: DossierDraftResult
    title: str | None
    language: str = Field(min_length=1)
    claims: list[DossierDraftClaim]
    no_evidence_reason: str | None
    conflicts: list[DossierEvidenceConflict]

    @model_validator(mode="after")
    def validate_result(self) -> DossierDraftContent:
        if self.result == DossierDraftResult.DRAFT:
            if not self.title or not self.claims:
                raise ValueError("A dossier draft requires a title and at least one claim")
            if self.no_evidence_reason or self.conflicts:
                raise ValueError("A dossier draft cannot also be a terminal evidence result")
        elif self.result == DossierDraftResult.NO_EVIDENCE:
            if not self.no_evidence_reason:
                raise ValueError("A no-evidence result requires a reason")
            if self.title or self.claims or self.conflicts:
                raise ValueError("A no-evidence result cannot contain draft content or conflicts")
        else:
            if not self.conflicts:
                raise ValueError("A conflicting-evidence result requires at least one conflict")
            if self.title or self.claims or self.no_evidence_reason:
                raise ValueError("A conflicting-evidence result cannot contain draft content")
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Dossier draft claim IDs must be unique")
        conflict_ids = [conflict.conflict_id for conflict in self.conflicts]
        if len(conflict_ids) != len(set(conflict_ids)):
            raise ValueError("Dossier conflict IDs must be unique")
        return self


class EditorialState(StrEnum):
    MACHINE_DRAFTED = "machine_drafted"
    HUMAN_REVIEWED = "human_reviewed"
    REJECTED = "rejected"
    PUBLISHED = "published"


class HumanDossierReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewed_by: str = Field(min_length=1)
    reviewed_at: AwareDatetime
    notes: str = Field(min_length=1)
    reviewed_claim_ids: list[str] = Field(min_length=1)


class DossierGenerationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_identifier: str = Field(min_length=1)
    evidence_bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: AwareDatetime
    provider_response_id: str | None = None


class DossierDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    draft_id: str = Field(pattern=r"^dossier-draft:[a-f0-9]{16}$")
    editorial_state: Literal[
        EditorialState.MACHINE_DRAFTED,
        EditorialState.HUMAN_REVIEWED,
        EditorialState.REJECTED,
    ] = EditorialState.MACHINE_DRAFTED
    bundle_id: str = Field(pattern=r"^evidence-bundle:[a-z0-9][a-z0-9:_-]+$")
    content: DossierDraftContent
    generation: DossierGenerationProvenance
    review: HumanDossierReview | None = None
    rejection_reason: str | None = None
    rejected_by: str | None = None
    rejected_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_editorial_state(self) -> DossierDraft:
        if self.editorial_state == EditorialState.MACHINE_DRAFTED:
            if self.review or self.rejection_reason or self.rejected_by or self.rejected_at:
                raise ValueError("Machine drafts cannot contain review or rejection metadata")
        elif self.editorial_state == EditorialState.HUMAN_REVIEWED:
            if (
                not self.review
                or self.rejection_reason
                or self.rejected_by
                or self.rejected_at
            ):
                raise ValueError("Human-reviewed drafts require review metadata only")
            expected = [claim.claim_id for claim in self.content.claims]
            if sorted(self.review.reviewed_claim_ids) != sorted(expected):
                raise ValueError("Human review must cover every generated claim exactly once")
        elif (
            not self.rejection_reason
            or not self.rejected_by
            or not self.rejected_at
            or self.review
        ):
            raise ValueError(
                "Rejected drafts require actor, timestamp and reason, without a review"
            )
        return self


class PublishedEditorialDossier(BaseModel):
    """Immutable, human-approved editorial data, distinct from source extracts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    dossier_id: str = Field(pattern=r"^historyjoice:editorial:[a-f0-9]{16}$")
    source_draft_id: str = Field(pattern=r"^dossier-draft:[a-f0-9]{16}$")
    dossier_kind: Literal[DossierKind.GENERATED_EDITORIAL] = (
        DossierKind.GENERATED_EDITORIAL
    )
    editorial_state: Literal[EditorialState.PUBLISHED] = EditorialState.PUBLISHED
    title: str = Field(min_length=1)
    language: str = Field(min_length=1)
    entity_ids: list[str] = Field(min_length=1)
    feature_ids: list[str] = Field(default_factory=list)
    content_role: Literal[ContentRole.PROJECT_INTERPRETATION] = (
        ContentRole.PROJECT_INTERPRETATION
    )
    extract: str = Field(min_length=1)
    claims: list[DossierDraftClaim] = Field(min_length=1)
    content_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_sources: list[SourceReference] = Field(min_length=1)
    evidence_attributions: list[str] = Field(min_length=1)
    editorial_license_id: str = Field(min_length=1)
    editorial_attribution: str = Field(min_length=1)
    generation: DossierGenerationProvenance
    review: HumanDossierReview
    published_at: AwareDatetime


class PeriodSpatialCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    entity_id: str | None = None
    source_uri: HttpUrl | None = None


class HistoricalPeriodDefinition(BaseModel):
    """A source-attributed definition of a named period, not a universal era."""

    model_config = ConfigDict(extra="forbid")

    period_id: str = Field(pattern=r"^periodo:p[a-z0-9]+$")
    authority_id: str = Field(pattern=r"^periodo:p[a-z0-9]+$")
    labels: dict[str, list[str]] = Field(min_length=1)
    valid_from: int
    valid_to: int
    start_label: str
    stop_label: str
    spatial_coverage: list[PeriodSpatialCoverage] = Field(default_factory=list)
    spatial_coverage_description: str | None = None
    authority_citation: str = Field(min_length=1)
    authority_creators: list[str] = Field(default_factory=list)
    source_locator: str | None = None
    notes: list[str] = Field(default_factory=list)
    broader_period_ids: list[str] = Field(default_factory=list)
    narrower_period_ids: list[str] = Field(default_factory=list)
    same_as: list[HttpUrl] = Field(default_factory=list)
    source_ref: SourceReference

    @model_validator(mode="after")
    def validate_period(self) -> HistoricalPeriodDefinition:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical years cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be later than valid_to")
        if any(not values for values in self.labels.values()):
            raise ValueError("Period label language lists cannot be empty")
        return self


class ChronologyEntityIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    period_ids: list[str] = Field(default_factory=list)


class ChronologyBandContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    band_id: str
    valid_from: int
    valid_to: int
    path: str
    count: int = Field(ge=0)


class ChronologyShardContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: str = Field(pattern=r"^chronology/(definitions|entities)/\{shard\}\.json$")
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> ChronologyShardContract:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Chronology shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Chronology shards must be two lowercase hexadecimal characters")
        return self


class ChronologyCollections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definitions: ChronologyShardContract
    entities: ChronologyShardContract


class ChronologySharding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["sha256"] = "sha256"
    encoding: Literal["utf-8"] = "utf-8"
    prefix_length: Literal[2] = 2


class ChronologyIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["attributed-competing-period-definitions"] = (
        "attributed-competing-period-definitions"
    )
    sharding: ChronologySharding
    collections: ChronologyCollections
    time_bands: list[ChronologyBandContract] = Field(default_factory=list)


class FeatureContentLink(BaseModel):
    """Small map-selection join record stored in a deterministic JSON shard."""

    model_config = ConfigDict(extra="forbid")

    feature_id: str
    primary_entity_id: str
    entity_ids: list[str] = Field(min_length=1)
    available_entity_ids: list[str] = Field(default_factory=list)
    missing_entity_ids: list[str] = Field(default_factory=list)
    dossier_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)


class ContentShardContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: str = Field(pattern=r"^content/(links|entities|dossiers)/\{shard\}\.json$")
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> ContentShardContract:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Content shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Content shards must be two lowercase hexadecimal characters")
        return self


class ContentCollections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_links: ContentShardContract
    entities: ContentShardContract
    dossiers: ContentShardContract


class ContentLanguagePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: Literal["requested-language-then-configured-fallback"] = (
        "requested-language-then-configured-fallback"
    )
    available: list[str] = Field(default_factory=list)
    fallback_order: list[str] = Field(default_factory=list)
    no_indiscriminate_duplication: bool = True


class ContentSharding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["sha256"] = "sha256"
    encoding: Literal["utf-8"] = "utf-8"
    prefix_length: Literal[2] = 2


class ContentIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    sharding: ContentSharding
    collections: ContentCollections
    language_policy: ContentLanguagePolicy


class WikiContextRole(StrEnum):
    PERSON = "person"
    EVENT = "event"
    INSTITUTION = "institution"
    POLITY = "polity"
    PLACE = "place"
    THEME = "theme"
    OTHER = "other"


class WikiContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_entity_id: str
    role: WikiContextRole
    relationship_types: list[str] = Field(min_length=1)
    valid_from: int | None = None
    valid_to: int | None = None
    source_strength: Literal["referenced_statement", "wikidata_statement"]
    score: int = Field(ge=0, le=100)
    selection_reasons: list[str] = Field(min_length=1)
    dossier_ids: list[str] = Field(default_factory=list)


class WikiFeatureContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    seed_entity_ids: list[str] = Field(min_length=1)
    items: list[WikiContextItem] = Field(default_factory=list)


class WikiContextCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: Literal["context/features/{shard}.json"] = "context/features/{shard}.json"
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> WikiContextCollection:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Wiki context shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Wiki context shards must be two lowercase hexadecimal characters")
        return self


class WikiContextIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    sharding: ContentSharding
    feature_contexts: WikiContextCollection
    ranking_policy: dict[str, Any]


class RegionTimeEntry(BaseModel):
    """A discovery reference, not an assertion that a cell is a historical region."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    entry_type: Literal["map_feature", "wikidata_entity"]
    entity_id: str
    feature_id: str | None = None
    kind: str
    themes: list[HistoricalTheme] = Field(default_factory=list)
    valid_from: int
    valid_to: int
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    spatial_basis: Literal["feature_geometry_intersection", "wikidata_coordinate"]
    review_status: ReviewStatus | None = None
    temporal_confidence: ConfidenceGrade | None = None
    dossier_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_entry(self) -> RegionTimeEntry:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Regional discovery entries cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("Regional discovery interval is reversed")
        if self.entry_type == "map_feature" and not self.feature_id:
            raise ValueError("Map-feature discovery entries require feature_id")
        if self.entry_type == "wikidata_entity" and self.feature_id:
            raise ValueError("Standalone Wikidata discovery entries cannot name a feature")
        return self


class RegionTimeBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_id: str
    cell_id: str
    band_id: str
    bounds: tuple[float, float, float, float]
    valid_from: int
    valid_to: int
    entries: list[RegionTimeEntry] = Field(default_factory=list)


class RegionTimeCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: Literal["region-time/buckets/{shard}.json"] = "region-time/buckets/{shard}.json"
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> RegionTimeCollection:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Region-time shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Region-time shards must be two lowercase hexadecimal characters")
        return self


class RegionTimeBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    band_id: str = Field(pattern=r"^band-[0-9]{2}$")
    valid_from: int
    valid_to: int


class RegionTimeGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_degrees: Literal[10] = 10
    longitude_origin: Literal[-180] = -180
    latitude_origin: Literal[-90] = -90
    semantics: Literal["discovery-grid-not-historical-regions"] = (
        "discovery-grid-not-historical-regions"
    )


class RegionTimeIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    sharding: ContentSharding
    grid: RegionTimeGrid
    time_bands: list[RegionTimeBand]
    buckets: RegionTimeCollection
    maximum_results_per_selection: int = Field(default=60, ge=1, le=200)
    inclusion_policy: Literal["reviewed-features-and-dated-coordinate-entities"] = (
        "reviewed-features-and-dated-coordinate-entities"
    )
    causal_claims_excluded: Literal[True] = True


class CausalRelationship(StrEnum):
    """Interpretive relationships; deliberately separate from factual entity edges."""

    CAUSED = "caused"
    CONTRIBUTED_TO = "contributed_to"
    ENABLED = "enabled"
    CONSTRAINED = "constrained"
    ACCELERATED = "accelerated"
    TRIGGERED = "triggered"
    RESPONSE_TO = "response_to"
    FEEDBACK_WITH = "feedback_with"


class CausalEvidenceBasis(StrEnum):
    SCHOLARSHIP = "scholarship"
    PRIMARY_AND_SCHOLARSHIP = "primary_and_scholarship"


class CausalSourceReference(SourceReference):
    source_kind: Literal["scholarship", "primary_source"]
    license_reviewed: bool = False
    license_review_notes: str | None = None

    @model_validator(mode="after")
    def require_license_review(self) -> CausalSourceReference:
        if not self.license_reviewed or not self.license_review_notes:
            raise ValueError("Causal sources require an explicit licence review and review notes")
        return self


class CausalTemporalAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: int
    valid_to: int
    precision: DatePrecision
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self) -> CausalTemporalAnchor:
        if self.valid_from == 0 or self.valid_to == 0:
            raise ValueError("Historical years cannot contain year zero")
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be later than valid_to")
        return self


class CausalClaim(BaseModel):
    """An attributed historiographical argument, never an automatic KG fact."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^claim:[a-z0-9][a-z0-9:_-]+$")
    cause_entity_ids: list[str] = Field(min_length=1)
    effect_entity_ids: list[str] = Field(min_length=1)
    relationship: CausalRelationship
    mechanism_type: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    mechanism_summary: dict[str, str] = Field(min_length=1)
    cause_period: CausalTemporalAnchor
    effect_period: CausalTemporalAnchor
    evidence_basis: CausalEvidenceBasis
    confidence: Confidence
    perspective: str = Field(min_length=1)
    source_refs: list[CausalSourceReference] = Field(min_length=1)
    authored_by: str = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PROVISIONAL
    supporting_claim_ids: list[str] = Field(default_factory=list)
    counterclaim_ids: list[str] = Field(default_factory=list)
    long_range_synthesis: bool = False

    @model_validator(mode="after")
    def validate_claim(self) -> CausalClaim:
        causes = set(self.cause_entity_ids)
        effects = set(self.effect_entity_ids)
        if len(causes) != len(self.cause_entity_ids) or len(effects) != len(self.effect_entity_ids):
            raise ValueError("Causal entity IDs must be unique")
        if causes & effects and self.relationship != CausalRelationship.FEEDBACK_WITH:
            raise ValueError("A directed causal claim cannot cause itself")
        if self.cause_period.valid_from > self.effect_period.valid_to:
            raise ValueError("A causal claim cannot begin after its effect has ended")
        if len(self.supporting_claim_ids) != len(set(self.supporting_claim_ids)):
            raise ValueError("supporting_claim_ids must be unique")
        if len(self.counterclaim_ids) != len(set(self.counterclaim_ids)):
            raise ValueError("counterclaim_ids must be unique")
        if self.claim_id in {*self.supporting_claim_ids, *self.counterclaim_ids}:
            raise ValueError("A causal claim cannot reference itself")
        independent_reviewers = {
            reviewer for reviewer in self.reviewed_by if reviewer != self.authored_by
        }
        if self.review_status == ReviewStatus.VERIFIED and not independent_reviewers:
            raise ValueError("A verified causal claim requires an independent reviewer")
        unique_sources = {
            (reference.source_id, reference.record_id) for reference in self.source_refs
        }
        source_kinds = {reference.source_kind for reference in self.source_refs}
        if "scholarship" not in source_kinds:
            raise ValueError("Causal claims require at least one scholarly source")
        if self.evidence_basis == CausalEvidenceBasis.PRIMARY_AND_SCHOLARSHIP and (
            source_kinds != {"primary_source", "scholarship"}
        ):
            raise ValueError("A mixed evidence basis requires both primary and scholarly sources")
        if self.relationship == CausalRelationship.CAUSED and (
            self.review_status != ReviewStatus.VERIFIED or len(unique_sources) < 2
        ):
            raise ValueError("'caused' requires verified review and two distinct sources")
        gap = self.effect_period.valid_from - self.cause_period.valid_to
        if gap > 100 and (not self.long_range_synthesis or len(self.supporting_claim_ids) < 2):
            raise ValueError(
                "A century-spanning claim requires a synthesis flag and intermediate claims"
            )
        return self


class CausalPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_id: str = Field(pattern=r"^path:[a-z0-9][a-z0-9:_-]+$")
    titles: dict[str, str] = Field(min_length=1)
    summaries: dict[str, str] = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    perspective: str = Field(min_length=1)
    authored_by: str = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PROVISIONAL

    @model_validator(mode="after")
    def validate_path(self) -> CausalPath:
        if len(self.claim_ids) != len(set(self.claim_ids)):
            raise ValueError("A causal path cannot repeat a claim")
        independent_reviewers = {
            reviewer for reviewer in self.reviewed_by if reviewer != self.authored_by
        }
        if self.review_status == ReviewStatus.VERIFIED and not independent_reviewers:
            raise ValueError("A verified causal path requires an independent reviewer")
        return self


class CausalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    claims: list[CausalClaim] = Field(default_factory=list)
    paths: list[CausalPath] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> CausalDataset:
        claims = {claim.claim_id: claim for claim in self.claims}
        paths = {path.path_id: path for path in self.paths}
        if len(claims) != len(self.claims):
            raise ValueError("Causal claim IDs must be unique")
        if len(paths) != len(self.paths):
            raise ValueError("Causal path IDs must be unique")
        for claim in self.claims:
            referenced = {*claim.supporting_claim_ids, *claim.counterclaim_ids}
            missing = referenced - claims.keys()
            if missing:
                raise ValueError(
                    f"Causal claim {claim.claim_id} references missing claims: {sorted(missing)}"
                )
            if claim.long_range_synthesis and not _causal_claims_connect(
                claim, [claims[item] for item in claim.supporting_claim_ids]
            ):
                raise ValueError(
                    f"Supporting claims do not connect the long-range claim {claim.claim_id}"
                )
        for path in self.paths:
            missing = set(path.claim_ids) - claims.keys()
            if missing:
                raise ValueError(
                    f"Causal path {path.path_id} references missing claims: {sorted(missing)}"
                )
            materialized = [claims[item] for item in path.claim_ids]
            for left, right in pairwise(materialized):
                if not set(left.effect_entity_ids) & set(right.cause_entity_ids):
                    raise ValueError(
                        f"Causal path {path.path_id} is disconnected between "
                        f"{left.claim_id} and {right.claim_id}"
                    )
        return self


def _causal_claims_connect(parent: CausalClaim, claims: list[CausalClaim]) -> bool:
    """Return true when intermediate claims form a directed route across the parent claim."""

    reachable = set(parent.cause_entity_ids)
    remaining = list(claims)
    while remaining:
        progressed = False
        for claim in remaining[:]:
            if reachable & set(claim.cause_entity_ids):
                reachable.update(claim.effect_entity_ids)
                remaining.remove(claim)
                progressed = True
        if not progressed:
            break
    return bool(reachable & set(parent.effect_entity_ids))


class CausalEntityIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    incoming_claim_ids: list[str] = Field(default_factory=list)
    outgoing_claim_ids: list[str] = Field(default_factory=list)
    path_ids: list[str] = Field(default_factory=list)


class CausalShardContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: str = Field(pattern=r"^causal/(claims|entities|paths)/\{shard\}\.json$")
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> CausalShardContract:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Causal shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Causal shards must be two lowercase hexadecimal characters")
        return self


class CausalCollections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: CausalShardContract
    entities: CausalShardContract
    paths: CausalShardContract


class CausalIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    sharding: ContentSharding
    collections: CausalCollections


class ThemeFeatureIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    assertion_ids: list[str] = Field(default_factory=list)
    themes: list[HistoricalTheme] = Field(default_factory=list)


class ThemeShardContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: str = Field(pattern=r"^themes/(assertions|features)/\{shard\}\.json$")
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)


class ThemeCollections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assertions: ThemeShardContract
    features: ThemeShardContract


class ThemeIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["sourced-multi-label-thematic-assertions"] = (
        "sourced-multi-label-thematic-assertions"
    )
    sharding: ContentSharding
    collections: ThemeCollections


class AssertionAdjacency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    assertion_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ids(self) -> AssertionAdjacency:
        if len(self.assertion_ids) != len(set(self.assertion_ids)):
            raise ValueError("Assertion adjacency IDs must be unique")
        return self


class AssertionShardContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_template: str = Field(
        pattern=r"^assertions/(records|entities|features)/\{shard\}\.json$"
    )
    count: int = Field(ge=0)
    shards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shards(self) -> AssertionShardContract:
        if len(self.shards) != len(set(self.shards)):
            raise ValueError("Assertion shards must be unique")
        if any(not re.fullmatch(r"[a-f0-9]{2}", shard) for shard in self.shards):
            raise ValueError("Assertion shards must be two lowercase hexadecimal characters")
        return self


class AssertionCollections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: AssertionShardContract
    entities: AssertionShardContract
    features: AssertionShardContract


class AssertionIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["structured-sourced-facts-not-generated-prose"] = (
        "structured-sourced-facts-not-generated-prose"
    )
    sharding: ContentSharding
    collections: AssertionCollections


class LayerRole(StrEnum):
    MAP_SOURCE = "map_source"
    THEMATIC_LENS = "thematic_lens"
    CONFIDENCE_OVERLAY = "confidence_overlay"
    PROVENANCE_OVERLAY = "provenance_overlay"


class LayerDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str = Field(pattern=r"^layer:[a-z0-9][a-z0-9:_-]+$")
    role: LayerRole
    labels: dict[str, str] = Field(min_length=1)
    description: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    theme: HistoricalTheme | None = None
    confidence_axis: Literal["temporal", "spatial", "interpretive"] | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> LayerDefinition:
        if self.role == LayerRole.THEMATIC_LENS and self.theme is None:
            raise ValueError("Thematic layer definitions require a theme")
        if self.role != LayerRole.THEMATIC_LENS and self.theme is not None:
            raise ValueError("Only thematic layer definitions may declare a theme")
        if self.role == LayerRole.CONFIDENCE_OVERLAY and self.confidence_axis is None:
            raise ValueError("Confidence overlays require a confidence axis")
        if self.role != LayerRole.CONFIDENCE_OVERLAY and self.confidence_axis is not None:
            raise ValueError("Only confidence overlays may declare a confidence axis")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Layer source IDs must be unique")
        return self


class LayerCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    semantics: Literal["orthogonal-map-sources-lenses-and-evidence-overlays"] = (
        "orthogonal-map-sources-lenses-and-evidence-overlays"
    )
    layers: list[LayerDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> LayerCatalog:
        layer_ids = [layer.layer_id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("Layer IDs must be unique")
        present = {layer.role for layer in self.layers}
        required = {
            LayerRole.MAP_SOURCE,
            LayerRole.THEMATIC_LENS,
            LayerRole.CONFIDENCE_OVERLAY,
            LayerRole.PROVENANCE_OVERLAY,
        }
        if not required.issubset(present):
            raise ValueError("Layer catalog must declare every orthogonal layer role")
        return self


class IndicatorObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator_id: str
    entity_id: str
    year: int
    value: float | int | None
    unit: str
    original_geographic_unit: str
    spatial_mapping_valid: bool = False
    spatial_mapping_note: str
    source_ref: SourceReference

    @model_validator(mode="after")
    def reject_year_zero(self) -> IndicatorObservation:
        if self.year == 0:
            raise ValueError("Historical years cannot contain year zero")
        return self


class CoverageCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    bounds: tuple[float, float, float, float]
    valid_from: int
    valid_to: int
    layer: str
    feature_count: int = Field(ge=0)
    confidence_counts: dict[ConfidenceGrade, int]
    reviewed_count: int = Field(ge=0)


class SourceRegistryEntry(BaseModel):
    """Public policy record; inclusion here is not proof that a source was ingested."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    enabled: bool
    adapter: str
    roles: list[SourceRole] = Field(min_length=1)
    title: str
    publisher: str
    url: HttpUrl
    license_id: str
    license_reviewed: bool
    commercial_redistribution: CommercialRedistribution
    distribution_tier: DistributionTier = DistributionTier.OPEN_CORE
    redistribution_conditions: list[str] = Field(default_factory=list)
    separates_media_rights: bool = False
    version: str | None = None
    expected_checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    temporal_scope: str | None = None
    geographic_scope: str | None = None
    release_policy: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    entries: list[SourceRegistryEntry]


class ArtifactFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    media_type: str
    bytes: int = Field(ge=0)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cache_control: str


class RawSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    filename: str
    original_url: HttpUrl
    object_key: str
    bytes: int = Field(ge=0)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_at: datetime
    etag: str | None = None
    last_modified: str | None = None


class BuildManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.10.0"
    build_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    minimum_year: int
    maximum_year: int
    sources: list[SourceReference]
    raw_snapshots: list[RawSnapshot] = Field(default_factory=list)
    artifacts: list[ArtifactFile]
    rejected_record_count: int = Field(ge=0)
    coverage_path: str
    attribution_path: str
    quality_path: str = "quality.json"
    content_index_path: str = "content/index.json"
    causal_index_path: str = "causal/index.json"
    chronology_index_path: str = "chronology/index.json"
    source_registry_path: str = "source-registry.json"
    coverage_priorities_path: str = "coverage-priorities.json"
    wiki_context_index_path: str = "context/index.json"
    region_time_index_path: str = "region-time/index.json"
    theme_index_path: str = "themes/index.json"
    search_index_path: str = "search/index.json"
    assertion_index_path: str = "assertions/index.json"
    layer_catalog_path: str = "layers/index.json"


class LatestPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    build_id: str
    manifest: str = Field(pattern=r"^builds/[a-z0-9_-]+/manifest\.json$")
    manifest_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: datetime
