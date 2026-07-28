export interface LatestPointer {
  schema_version: string;
  build_id: string;
  generated_at: string;
  manifest: string;
  manifest_checksum_sha256: string;
}

export interface Artifact {
  path: string;
  media_type: string;
  bytes: number;
  checksum_sha256: string;
}

export interface SourceReference {
  source_id: string;
  title: string;
  publisher: string;
  url: string;
  license_id: string;
  citation: string;
  version?: string;
  record_id?: string;
  retrieved_at?: string;
  checksum_sha256?: string;
  modified?: boolean;
}

export interface BuildManifest {
  schema_version: string;
  build_id: string;
  generated_at: string;
  minimum_year: number;
  maximum_year: number;
  sources: SourceReference[];
  artifacts: Artifact[];
  rejected_record_count: number;
  coverage_path: string;
  attribution_path: string;
  quality_path?: string;
  content_index_path?: string;
  causal_index_path?: string;
  chronology_index_path?: string;
  source_registry_path?: string;
  coverage_priorities_path?: string;
  wiki_context_index_path?: string;
  region_time_index_path?: string;
  theme_index_path?: string;
  search_index_path?: string;
  assertion_index_path?: string;
  layer_catalog_path?: string;
  /** Optional: a release carrying no year pages is complete, not degraded. */
  year_index_path?: string;
}

export interface CoverageCell {
  cell_id: string;
  bounds: [number, number, number, number];
  valid_from: number;
  valid_to: number;
  layer: string;
  feature_count: number;
  confidence_counts: Record<string, number>;
  reviewed_count: number;
}

export interface QualityReport {
  accepted_feature_count?: number;
  accepted_indicator_count?: number;
  rejected_record_count?: number;
  rejections_by_reason?: Record<string, number>;
  validation_issues_by_code?: Record<string, number>;
  [key: string]: unknown;
}

export interface AttributionReport extends Array<SourceReference> {}

export interface LoadedRelease {
  latest: LatestPointer;
  manifest: BuildManifest;
  buildBase: string;
}
