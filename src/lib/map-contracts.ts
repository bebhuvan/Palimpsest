import type { SourceReference } from '$lib/release-contracts';

export interface LayerDefinition {
  layer_id: string;
  role: 'map_source' | 'thematic_lens' | 'confidence_overlay' | 'provenance_overlay';
  labels: Record<string, string>;
  description: string;
  source_ids: string[];
  theme?: string | null;
  confidence_axis?: 'temporal' | 'spatial' | 'interpretive' | null;
}

export interface LayerCatalog {
  schema_version: string;
  semantics: 'orthogonal-map-sources-lenses-and-evidence-overlays';
  layers: LayerDefinition[];
}

export type HistoricalMapRightsScope = 'metadata' | 'media' | 'georeference';

export interface HistoricalMapRights {
  scope: HistoricalMapRightsScope;
  license_id: string;
  attribution: string;
  rights_uri?: string | null;
}

export interface HistoricalMapRightsApproval {
  scope: HistoricalMapRightsScope;
  status: 'approved';
  decision_id: string;
  reviewed_by: string;
  reviewed_at: string;
  rationale: string;
}

export interface HistoricalMapMetadata {
  schema_version: '1.0.0';
  map_id: string;
  manifest_id: string;
  canvas_id: string;
  annotation_id: string;
  label: string;
  depicted_date: string;
  providers: string[];
  required_statement: string;
  metadata_rights: HistoricalMapRights;
  image_rights: HistoricalMapRights;
  georeference_rights: HistoricalMapRights;
  georeference_confidence: { grade: string; rationale: string };
  known_limitations: string[];
  release_rights_approvals: HistoricalMapRightsApproval[];
  rendering?: {
    protocol: 'iiif-georeference-maplibre-image-v1';
    image_path: string;
    image_checksum_sha256: string;
    coordinates: [[number, number], [number, number], [number, number], [number, number]];
  } | null;
}

export interface IntegrationIndex {
  schema_version: '1.0.0';
  semantics: 'build-time-reviewed-source-integrations';
  authority_matches_path: string;
  authority_match_count: number;
  historical_maps_path: string;
  historical_map_count: number;
}

export interface AuthorityMatch {
  schema_version: '1.0.0';
  match_id: string;
  subject_id: string;
  authority_id: string;
  authority_namespace: string;
  label: string;
  relation: 'exact_match' | 'close_match' | 'candidate';
  review_status: 'proposed' | 'accepted' | 'rejected';
  confidence_score: number;
  confidence: { grade: string; rationale: string };
  source_ref: SourceReference;
  rights: {
    scope: 'metadata';
    license_id: string;
    attribution: string;
    rights_uri?: string | null;
  };
}

export interface HistoricalPeriodDefinition {
  period_id: string;
  authority_id: string;
  labels: Record<string, string[]>;
  valid_from: number;
  valid_to: number;
  start_label: string;
  stop_label: string;
  spatial_coverage: Array<{ label: string; entity_id?: string; source_uri?: string }>;
  spatial_coverage_description?: string;
  authority_citation: string;
  authority_creators: string[];
  source_locator?: string;
  notes: string[];
  broader_period_ids: string[];
  narrower_period_ids: string[];
  same_as: string[];
  source_ref: SourceReference;
}

export interface ChronologyEntityIndex {
  entity_id: string;
  period_ids: string[];
}

export interface ChronologyIndex {
  schema_version: string;
  semantics: 'attributed-competing-period-definitions';
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'definitions' | 'entities',
    { path_template: string; count: number; shards: string[] }
  >;
  time_bands: Array<{
    band_id: string;
    valid_from: number;
    valid_to: number;
    path: string;
    count: number;
  }>;
}
