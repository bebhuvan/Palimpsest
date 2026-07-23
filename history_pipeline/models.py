from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


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


class HistoricalDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dossier_id: str
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
