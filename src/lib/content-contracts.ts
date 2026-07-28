import type { SourceReference } from '$lib/release-contracts';

export interface HistoricalEntity {
  entity_id: string;
  entity_type: string;
  entity_kind?: 'person' | 'event' | 'institution' | 'work' | 'artifact' | 'route' | 'place' | 'polity' | 'concept' | 'other';
  names: Record<string, string>;
  aliases?: Record<string, string[]>;
  descriptions: Record<string, string>;
  valid_from: number | null;
  valid_to: number | null;
  wikidata_id?: string;
  links: Record<string, string>;
  relationships?: Array<{
    relation_type: string;
    target_entity_id: string;
    qualifiers?: Array<{ predicate: string; datatype?: string | null; value: unknown }>;
  }>;
  sitelinks?: Record<string, { language: string; title: string; url: string }>;
  commons_images?: string[];
  source_refs: SourceReference[];
}

export interface HistoricalDossier {
  dossier_id: string;
  dossier_kind?: 'source_extract';
  title: string;
  language: string;
  entity_ids?: string[];
  content_role?: 'primary_source' | 'tertiary_summary' | 'project_interpretation';
  extract: string;
  url: string;
  page_id: number;
  revision_id?: number;
  revision_timestamp?: string;
  content_checksum_sha256?: string;
  source_ref: SourceReference;
}

export interface PublishedEditorialDossier {
  dossier_id: string;
  source_draft_id: string;
  dossier_kind: 'generated_editorial';
  editorial_state: 'published';
  title: string;
  language: string;
  entity_ids: string[];
  feature_ids: string[];
  content_role: 'project_interpretation';
  extract: string;
  content_checksum_sha256: string;
  evidence_sources: SourceReference[];
  evidence_attributions: string[];
  editorial_license_id: string;
  editorial_attribution: string;
}

export interface RestatementTimelineEntry {
  year_text: string;
  sort_year: number;
  text: string;
}

/**
 * A plain-English restatement of exactly one source dossier revision.
 *
 * It adds no claim the source did not make, so it needs no per-claim review. What it carries
 * instead is the closed-world report proving it stayed inside its source, and the source revision
 * it is bound to. A release drops any restatement whose source has since changed.
 */
export interface DossierRestatement {
  restatement_id: string;
  dossier_id: string;
  dossier_kind: 'restatement';
  content_role: 'source_restatement';
  language: string;
  headline: string;
  text: string;
  timeline: RestatementTimelineEntry[];
  entity_ids: string[];
  source_revision_id?: number | null;
  source_content_checksum_sha256: string;
  content_checksum_sha256: string;
  generation: {
    prompt_version: string;
    model_identifier: string;
    generated_at: string;
  };
  validation: {
    policy_version: string;
    source_chars: number;
    restatement_chars: number;
  };
}

export interface ContentRelationship {
  type: string;
  target_entity_id: string;
  label?: string;
  reason?: string;
}

export interface FeatureContentLink {
  feature_id: string;
  primary_entity_id: string;
  entity_ids: string[];
  available_entity_ids: string[];
  missing_entity_ids: string[];
  dossier_ids: string[];
  related_entity_ids: string[];
  /** Absent in releases built before reader-facing join eligibility was published. */
  reading_eligibility?: EntityReadingEligibility[];
}

export interface EntityReadingEligibility {
  entity_id: string;
  identity_basis: 'source_asserted';
  identity_relation: 'exact_match' | 'place_continuity' | 'broader_topic';
  temporal_overlap: 'overlaps' | 'none' | 'unknown';
  reading_eligible: boolean;
  reason_codes: string[];
}

export interface ContentIndex {
  schema_version: string;
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'feature_links' | 'entities' | 'dossiers',
    { path_template: string; count: number; shards: string[] }
  > & {
    /** Absent in releases built before the restatement tier existed. */
    restatements?: { path_template: string; count: number; shards: string[] };
  };
  language_policy: {
    selection: string;
    available: string[];
    fallback_order: string[];
    no_indiscriminate_duplication: boolean;
  };
}

export interface ContentBundle {
  entities: Map<string, HistoricalEntity>;
  dossiers: Map<string, HistoricalDossier>;
  featureLinks: Map<string, FeatureContentLink>;
  hasEntities: boolean;
  hasDossiers: boolean;
  hasFeatureLinks: boolean;
}

export interface SelectedContent {
  link: FeatureContentLink;
  entities: HistoricalEntity[];
  dossiers: HistoricalDossier[];
  /** Keyed by the dossier ID each restatement was derived from. */
  restatements: Map<string, DossierRestatement>;
}
