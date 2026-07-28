import type {
  HistoricalDossier,
  HistoricalEntity
} from '$lib/content-contracts';
import type { SourceReference } from '$lib/release-contracts';

export type WikiContextRole = 'person' | 'event' | 'institution' | 'polity' | 'place' | 'theme' | 'other';

export interface WikiContextItem {
  context_entity_id: string;
  role: WikiContextRole;
  relationship_types: string[];
  valid_from: number | null;
  valid_to: number | null;
  source_strength: 'referenced_statement' | 'wikidata_statement';
  score: number;
  selection_reasons: string[];
  dossier_ids: string[];
}

export interface WikiFeatureContext {
  feature_id: string;
  seed_entity_ids: string[];
  items: WikiContextItem[];
}

export interface WikiContextIndex {
  schema_version: string;
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  feature_contexts: { path_template: string; count: number; shards: string[] };
  ranking_policy: {
    algorithm: string;
    maximum_entities_per_feature: number;
    temporal_margin_years: number;
    role_quotas: Record<WikiContextRole, number>;
    evidence_basis: string;
    causal_claims_excluded: boolean;
  };
}

export interface SelectedWikiContext {
  context: WikiFeatureContext;
  items: Array<WikiContextItem & { entity: HistoricalEntity; dossiers: HistoricalDossier[] }>;
  total_items: number;
}

export interface RegionTimeEntry {
  entry_id: string;
  entry_type: 'map_feature' | 'wikidata_entity';
  entity_id: string;
  feature_id: string | null;
  kind: string;
  themes: string[];
  valid_from: number;
  valid_to: number;
  longitude: number;
  latitude: number;
  spatial_basis: 'feature_geometry_intersection' | 'wikidata_coordinate';
  review_status: string | null;
  temporal_confidence: string | null;
  dossier_ids: string[];
  source_ids: string[];
}

export interface RegionTimeBucket {
  bucket_id: string;
  cell_id: string;
  band_id: string;
  bounds: [number, number, number, number];
  valid_from: number;
  valid_to: number;
  entries: RegionTimeEntry[];
}

export interface RegionTimeIndex {
  schema_version: string;
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  grid: {
    cell_degrees: 10;
    longitude_origin: -180;
    latitude_origin: -90;
    semantics: 'discovery-grid-not-historical-regions';
  };
  time_bands: Array<{ band_id: string; valid_from: number; valid_to: number }>;
  buckets: { path_template: string; count: number; shards: string[] };
  maximum_results_per_selection: number;
  inclusion_policy: 'reviewed-features-and-dated-coordinate-entities';
  causal_claims_excluded: true;
}

export interface SelectedRegionalContext {
  bucket: RegionTimeBucket;
  entries: RegionTimeEntry[];
  entities: Map<string, HistoricalEntity>;
  dossiers: Map<string, HistoricalDossier>;
}

export interface CausalTemporalAnchor {
  valid_from: number;
  valid_to: number;
  precision: string;
  rationale: string;
}

export interface CausalClaim {
  claim_id: string;
  cause_entity_ids: string[];
  effect_entity_ids: string[];
  relationship: 'caused' | 'contributed_to' | 'enabled' | 'constrained' | 'accelerated' | 'triggered' | 'response_to' | 'feedback_with';
  mechanism_type: string;
  mechanism_summary: Record<string, string>;
  cause_period: CausalTemporalAnchor;
  effect_period: CausalTemporalAnchor;
  evidence_basis: 'scholarship' | 'primary_and_scholarship';
  confidence: { grade: string; rationale: string };
  perspective: string;
  source_refs: SourceReference[];
  authored_by: string;
  reviewed_by: string[];
  review_status: string;
  supporting_claim_ids: string[];
  counterclaim_ids: string[];
  long_range_synthesis: boolean;
}

export interface CausalPath {
  path_id: string;
  titles: Record<string, string>;
  summaries: Record<string, string>;
  claim_ids: string[];
  perspective: string;
  authored_by: string;
  reviewed_by: string[];
  review_status: string;
}

export interface CausalEntityIndex {
  entity_id: string;
  incoming_claim_ids: string[];
  outgoing_claim_ids: string[];
  path_ids: string[];
}

export interface CausalIndex {
  schema_version: string;
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'claims' | 'entities' | 'paths',
    { path_template: string; count: number; shards: string[] }
  >;
}

export interface CausalContext {
  adjacency: CausalEntityIndex[];
  claims: CausalClaim[];
  paths: CausalPath[];
}

export interface ThematicAssertion {
  assertion_id: string;
  subject_id: string;
  subject_kind: string;
  feature_ids: string[];
  entity_ids: string[];
  theme: 'power' | 'belief' | 'knowledge' | 'culture' | 'trade';
  subtheme: string;
  role: 'primary' | 'secondary' | 'contextual';
  valid_from: number;
  valid_to: number;
  classification_basis: 'explicit_source_type' | 'explicit_source_relation' | 'reviewed_editorial';
  rule_id: string;
  matched_values: string[];
  confidence: { grade: string; rationale: string };
  review_status: string;
  rationale: string;
  source_refs: SourceReference[];
}

export interface ThemeFeatureIndex {
  feature_id: string;
  assertion_ids: string[];
  themes: string[];
}

export interface ThemeIndex {
  schema_version: string;
  semantics: 'sourced-multi-label-thematic-assertions';
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'assertions' | 'features',
    { path_template: string; count: number; shards: string[] }
  >;
}

export interface EvidenceAssertion {
  assertion_id: string;
  representation: 'structured_sourced_assertion';
  subject_entity_ids: string[];
  feature_ids: string[];
  predicate: string;
  object: {
    kind: 'entity' | 'text' | 'year' | 'number_range';
    entity_id?: string | null;
    value?: string | null;
    year?: number | null;
    value_from?: number | null;
    value_to?: number | null;
    unit?: string | null;
  };
  valid_from: number;
  valid_to: number;
  date_precision: string;
  temporal_uncertainty?: {
    earliest_start?: number | null;
    latest_start?: number | null;
    earliest_end?: number | null;
    latest_end?: number | null;
    circa: boolean;
    rationale: string;
  } | null;
  confidence: { grade: string; rationale: string };
  evidence_basis: 'primary_source_metadata' | 'authority_metadata' | 'tertiary_summary' | 'scholarly_assertion' | 'reviewed_editorial_link';
  review_status: string;
  source_refs: SourceReference[];
  source_excerpt?: string | null;
  source_excerpt_checksum_sha256?: string | null;
  source_citations?: string[];
  restatement?: {
    assertion_id: string;
    text: string;
    source_excerpt_checksum_sha256: string;
    prompt_version: string;
    prompt_sha256: string;
    provider: string;
    model_identifier: string;
    generated_at: string;
    provider_response_id?: string | null;
  } | null;
}

export interface AssertionAdjacency {
  subject_id: string;
  assertion_ids: string[];
}

export interface AssertionIndex {
  schema_version: string;
  semantics: 'structured-sourced-facts-not-generated-prose';
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'records' | 'entities' | 'features',
    { path_template: string; count: number; shards: string[] }
  >;
}
