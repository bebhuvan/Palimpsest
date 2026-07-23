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
}

export interface SearchRecord {
  entity_id: string;
  dossier_ids?: string[];
  content_shard?: string;
  feature_ids: string[];
  kind: string;
  themes?: string[];
  source_ids?: string[];
  latitude: number;
  longitude: number;
  names: Record<string, string>;
  name_attestations?: HistoricalNameAttestation[];
  valid_from: number;
  valid_to: number;
}

export interface StaticSearchIndex {
  schema_version: string;
  semantics: 'lazy-static-search-over-release-records';
  normalization: 'unicode-nfkd-lowercase-alphanumeric-spaces';
  minimum_query_length: 2;
  name_ngrams: {
    length: 2;
    paths: Record<string, string>;
  };
  records: {
    path_template: string;
    count: number;
    shards: string[];
  };
  features: {
    path_template: string;
    count: number;
    shards: string[];
  };
  pages: {
    path_template: string;
    page_size: number;
    count: number;
    pages: string[];
  };
  time_bands: Array<{
    band_id: string;
    valid_from: number;
    valid_to: number;
    path: string;
    count: number;
  }>;
  compression: 'gzip';
}

export interface HistoricalNameAttestation {
  name_id: string;
  feature_id: string;
  text: string;
  language: string;
  script?: string | null;
  name_kind: 'endonym' | 'exonym' | 'official' | 'conventional' | 'transliterated' | 'translated' | 'short' | 'unknown';
  valid_from: number;
  valid_to: number;
  date_precision: string;
  temporal_confidence: string;
  primary: boolean;
  perspective?: string | null;
  temporal_basis: 'attested' | 'feature_interval';
  source_ids: string[];
}

export function searchableNames(record: SearchRecord): string[] {
  const attested = record.name_attestations?.map((name) => name.text) ?? [];
  return Array.from(new Set([...attested, ...Object.values(record.names)]));
}

export function nameForYear(
  record: SearchRecord,
  year: number,
  featureId?: string
): HistoricalNameAttestation | null {
  const candidates = (record.name_attestations ?? [])
    .filter((name) => name.valid_from <= year && name.valid_to >= year)
    .filter((name) => !featureId || name.feature_id === featureId)
    .sort(compareHistoricalNames);
  return candidates[0] ?? null;
}

export function closestNameForYear(record: SearchRecord, year: number): HistoricalNameAttestation | null {
  const candidates = [...(record.name_attestations ?? [])].sort((left, right) => {
    const leftDistance = year < left.valid_from ? left.valid_from - year : year > left.valid_to ? year - left.valid_to : 0;
    const rightDistance = year < right.valid_from ? right.valid_from - year : year > right.valid_to ? year - right.valid_to : 0;
    return leftDistance - rightDistance || compareHistoricalNames(left, right);
  });
  return candidates[0] ?? null;
}

export function displayNameForYear(record: SearchRecord, year: number): string {
  return nameForYear(record, year)?.text ?? closestNameForYear(record, year)?.text ?? Object.values(record.names)[0] ?? record.entity_id;
}

function compareHistoricalNames(left: HistoricalNameAttestation, right: HistoricalNameAttestation): number {
  const leftRank = left.primary ? 0 : left.name_kind === 'endonym' ? 1 : left.name_kind === 'official' ? 2 : 3;
  const rightRank = right.primary ? 0 : right.name_kind === 'endonym' ? 1 : right.name_kind === 'official' ? 2 : 3;
  return leftRank - rightRank || left.text.localeCompare(right.text);
}

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
  relationships?: Array<{ relation_type: string; target_entity_id: string }>;
  sitelinks?: Record<string, { language: string; title: string; url: string }>;
  commons_images?: string[];
  source_refs: SourceReference[];
}

export interface HistoricalDossier {
  dossier_id: string;
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
}

export interface ContentIndex {
  schema_version: string;
  sharding: { algorithm: 'sha256'; encoding: 'utf-8'; prefix_length: number };
  collections: Record<
    'feature_links' | 'entities' | 'dossiers',
    { path_template: string; count: number; shards: string[] }
  >;
  language_policy: {
    selection: string;
    available: string[];
    fallback_order: string[];
    no_indiscriminate_duplication: boolean;
  };
}

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
    kind: 'entity' | 'text' | 'year';
    entity_id?: string | null;
    value?: string | null;
    year?: number | null;
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
  evidence_basis: 'primary_source_metadata' | 'authority_metadata' | 'scholarly_assertion' | 'reviewed_editorial_link';
  review_status: string;
  source_refs: SourceReference[];
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
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export async function loadRelease(dataBase: string): Promise<LoadedRelease> {
  const latestResponse = await fetch(joinUrl(dataBase, 'latest.json'), { cache: 'no-cache' });
  if (!latestResponse.ok) throw new Error(`Could not load latest release (${latestResponse.status})`);
  const latest = (await latestResponse.json()) as LatestPointer;

  if (!latest.schema_version.startsWith('1.')) {
    throw new Error(`Unsupported data schema ${latest.schema_version}`);
  }

  const manifestResponse = await fetch(joinUrl(dataBase, latest.manifest), { cache: 'force-cache' });
  if (!manifestResponse.ok) throw new Error(`Could not load release manifest (${manifestResponse.status})`);
  const manifestBytes = await manifestResponse.arrayBuffer();
  const actualChecksum = await sha256Hex(manifestBytes);
  if (actualChecksum !== latest.manifest_checksum_sha256) {
    throw new Error('Release manifest checksum did not match latest.json');
  }

  const manifest = JSON.parse(new TextDecoder().decode(manifestBytes)) as BuildManifest;
  if (manifest.build_id !== latest.build_id) throw new Error('Release pointer and manifest build IDs differ');
  const buildBase = joinUrl(dataBase, latest.manifest.replace(/\/manifest\.json$/, ''));
  return { latest, manifest, buildBase };
}

export function artifact(release: LoadedRelease, path: string): Artifact | undefined {
  return release.manifest.artifacts.find((item) => item.path === path);
}

export function artifactUrl(release: LoadedRelease, path: string): string {
  return joinUrl(release.buildBase, path);
}

export async function loadJsonArtifact<T>(release: LoadedRelease, path: string): Promise<T> {
  const bytes = await fetchVerifiedArtifact(release, path);
  return JSON.parse(new TextDecoder().decode(bytes)) as T;
}

/** Parses line-delimited JSON incrementally so large release files never require one giant string. */
export async function loadNdjson<T>(url: string): Promise<T[]> {
  const response = await fetch(url, { cache: 'force-cache' });
  if (!response.ok) throw new Error(`Could not load ${url.split('/').at(-1)} (${response.status})`);
  if (!response.body) {
    return (await response.text()).split('\n').filter(Boolean).map((line) => JSON.parse(line) as T);
  }

  const records: T[] = [];
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let remainder = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const lines = `${remainder}${value}`.split('\n');
    remainder = lines.pop() ?? '';
    for (const line of lines) if (line.trim()) records.push(JSON.parse(line) as T);
  }
  if (remainder.trim()) records.push(JSON.parse(remainder) as T);
  return records;
}

export async function loadSearchIndex(release: LoadedRelease, path: string): Promise<SearchRecord[]> {
  const bytes = await fetchVerifiedArtifact(release, path);
  return new TextDecoder()
    .decode(bytes)
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as SearchRecord);
}

const staticSearchIndexCache = new Map<string, Promise<StaticSearchIndex>>();
const staticSearchArrayCache = new Map<string, Promise<SearchRecord[]>>();
const staticSearchRecordShardCache = new Map<string, Promise<Record<string, SearchRecord>>>();
const staticSearchFeatureShardCache = new Map<string, Promise<Record<string, string>>>();

export async function loadStaticSearchIndex(
  release: LoadedRelease
): Promise<StaticSearchIndex | null> {
  const path = release.manifest.search_index_path;
  if (!path || !artifact(release, path)) return null;
  const url = artifactUrl(release, path);
  let pending = staticSearchIndexCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<StaticSearchIndex>(release, path).then((index) => {
      if (
        index.semantics !== 'lazy-static-search-over-release-records' ||
        index.compression !== 'gzip' ||
        index.name_ngrams.length !== 2
      ) {
        throw new Error('This release has an unsupported static search contract.');
      }
      return index;
    });
    staticSearchIndexCache.set(url, pending);
  }
  return pending;
}

export function normalizeSearchQuery(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

export async function searchStaticRecords(
  release: LoadedRelease,
  index: StaticSearchIndex,
  query: string
): Promise<SearchRecord[]> {
  const normalized = normalizeSearchQuery(query);
  const characters = Array.from(normalized);
  let token = '';
  for (let position = 0; position < characters.length - 1; position += 1) {
    const candidate = `${characters[position]}${characters[position + 1]}`;
    if (!candidate.includes(' ')) {
      token = candidate;
      break;
    }
  }
  if (!token) return [];
  const path = index.name_ngrams.paths[token];
  if (!path) return [];
  const records = await loadCompressedSearchArray(release, path);
  return records.filter((record) =>
    searchableNames(record).some((name) =>
      normalizeSearchQuery(name).includes(normalized)
    )
  );
}

export async function loadSearchTimeBand(
  release: LoadedRelease,
  index: StaticSearchIndex,
  year: number
): Promise<SearchRecord[]> {
  const band = index.time_bands.find(
    (candidate) => candidate.valid_from <= year && candidate.valid_to >= year
  );
  return band ? loadCompressedSearchArray(release, band.path) : [];
}

export async function loadSearchPage(
  release: LoadedRelease,
  index: StaticSearchIndex,
  pageNumber: number
): Promise<SearchRecord[]> {
  const page = index.pages.pages[pageNumber];
  if (!page) return [];
  const path = index.pages.path_template.replace('{page}', page);
  return loadCompressedSearchArray(release, path);
}

export async function loadSearchRecord(
  release: LoadedRelease,
  index: StaticSearchIndex,
  identifiers: { entityId?: string | null; featureId?: string | null }
): Promise<SearchRecord | null> {
  let entityId = identifiers.entityId || null;
  if (!entityId && identifiers.featureId) {
    const featureShard = await contentShard(identifiers.featureId, 2);
    if (!index.features.shards.includes(featureShard)) return null;
    const featurePath = index.features.path_template.replace('{shard}', featureShard);
    const featureUrl = artifactUrl(release, featurePath);
    let pendingFeatures = staticSearchFeatureShardCache.get(featureUrl);
    if (!pendingFeatures) {
      pendingFeatures = loadJsonArtifact<Record<string, string>>(release, featurePath);
      staticSearchFeatureShardCache.set(featureUrl, pendingFeatures);
    }
    entityId = (await pendingFeatures)[identifiers.featureId] ?? null;
  }
  if (!entityId) return null;
  const recordShard = await contentShard(entityId, 2);
  if (!index.records.shards.includes(recordShard)) return null;
  const recordPath = index.records.path_template.replace('{shard}', recordShard);
  const recordUrl = artifactUrl(release, recordPath);
  let pendingRecords = staticSearchRecordShardCache.get(recordUrl);
  if (!pendingRecords) {
    pendingRecords = loadJsonArtifact<Record<string, SearchRecord>>(release, recordPath);
    staticSearchRecordShardCache.set(recordUrl, pendingRecords);
  }
  return (await pendingRecords)[entityId] ?? null;
}

async function loadCompressedSearchArray(
  release: LoadedRelease,
  path: string
): Promise<SearchRecord[]> {
  const url = artifactUrl(release, path);
  let pending = staticSearchArrayCache.get(url);
  if (!pending) {
    pending = fetchVerifiedArtifact(release, path).then(async (bytes) => {
      if (typeof DecompressionStream === 'undefined') {
        throw new Error('This browser cannot open the compressed search index.');
      }
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
      const decoded = await new Response(stream).arrayBuffer();
      return JSON.parse(new TextDecoder().decode(decoded)) as SearchRecord[];
    });
    staticSearchArrayCache.set(url, pending);
  }
  return pending;
}

const contentIndexCache = new Map<string, Promise<ContentIndex>>();
const contentShardCache = new Map<string, Promise<Record<string, unknown>>>();
const causalIndexCache = new Map<string, Promise<CausalIndex>>();
const causalShardCache = new Map<string, Promise<Record<string, unknown>>>();
const chronologyIndexCache = new Map<string, Promise<ChronologyIndex>>();
const chronologyShardCache = new Map<string, Promise<Record<string, unknown>>>();
const chronologyBandCache = new Map<string, Promise<string[]>>();
const wikiContextIndexCache = new Map<string, Promise<WikiContextIndex>>();
const wikiContextShardCache = new Map<string, Promise<Record<string, unknown>>>();
const regionTimeIndexCache = new Map<string, Promise<RegionTimeIndex>>();
const regionTimeShardCache = new Map<string, Promise<Record<string, unknown>>>();
const themeIndexCache = new Map<string, Promise<ThemeIndex>>();
const themeShardCache = new Map<string, Promise<Record<string, unknown>>>();
const assertionIndexCache = new Map<string, Promise<AssertionIndex>>();
const assertionShardCache = new Map<string, Promise<Record<string, unknown>>>();

export async function loadLayerCatalog(release: LoadedRelease): Promise<LayerCatalog | null> {
  const path = release.manifest.layer_catalog_path;
  return path ? loadJsonArtifact<LayerCatalog>(release, path) : null;
}

/** Load structured sourced facts joined to one selected map feature. */
export async function loadEvidenceAssertions(
  release: LoadedRelease,
  featureId: string
): Promise<EvidenceAssertion[]> {
  const indexPath = release.manifest.assertion_index_path;
  if (!indexPath) return [];
  const indexUrl = artifactUrl(release, indexPath);
  let pendingIndex = assertionIndexCache.get(indexUrl);
  if (!pendingIndex) {
    pendingIndex = loadJsonArtifact<AssertionIndex>(release, indexPath);
    assertionIndexCache.set(indexUrl, pendingIndex);
  }
  const index = await pendingIndex;
  const featureShard = await contentShard(featureId, index.sharding.prefix_length);
  const featureRecords = await loadAssertionShard(release, index, 'features', featureShard);
  const adjacency = featureRecords[featureId] as AssertionAdjacency | undefined;
  if (!adjacency) return [];
  const idsByShard = new Map<string, string[]>();
  for (const assertionId of adjacency.assertion_ids) {
    const shard = await contentShard(assertionId, index.sharding.prefix_length);
    idsByShard.set(shard, [...(idsByShard.get(shard) ?? []), assertionId]);
  }
  return (
    await Promise.all(
      [...idsByShard].map(async ([shard, assertionIds]) => {
        const values = await loadAssertionShard(release, index, 'records', shard);
        return assertionIds.flatMap((id) =>
          values[id] ? [values[id] as EvidenceAssertion] : []
        );
      })
    )
  ).flat();
}

async function loadAssertionShard(
  release: LoadedRelease,
  index: AssertionIndex,
  collection: 'records' | 'entities' | 'features',
  shard: string
): Promise<Record<string, unknown>> {
  const contract = index.collections[collection];
  if (!contract.shards.includes(shard)) return {};
  const path = contract.path_template.replace('{shard}', shard);
  const url = artifactUrl(release, path);
  let pending = assertionShardCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<Record<string, unknown>>(release, path);
    assertionShardCache.set(url, pending);
  }
  return pending;
}

/** Load the auditable reasons that place one selected feature in thematic lenses. */
export async function loadThemeAssertions(
  release: LoadedRelease,
  featureId: string
): Promise<ThematicAssertion[]> {
  const indexPath = release.manifest.theme_index_path;
  if (!indexPath) return [];
  const indexUrl = artifactUrl(release, indexPath);
  let pendingIndex = themeIndexCache.get(indexUrl);
  if (!pendingIndex) {
    pendingIndex = loadJsonArtifact<ThemeIndex>(release, indexPath);
    themeIndexCache.set(indexUrl, pendingIndex);
  }
  const index = await pendingIndex;
  const featureShard = await contentShard(featureId, index.sharding.prefix_length);
  const featureRecords = await loadThemeShard(release, index, 'features', featureShard);
  const feature = featureRecords[featureId] as ThemeFeatureIndex | undefined;
  if (!feature) return [];
  const idsByShard = new Map<string, string[]>();
  for (const assertionId of feature.assertion_ids) {
    const shard = await contentShard(assertionId, index.sharding.prefix_length);
    idsByShard.set(shard, [...(idsByShard.get(shard) ?? []), assertionId]);
  }
  return (
    await Promise.all(
      [...idsByShard].map(async ([shard, assertionIds]) => {
        const values = await loadThemeShard(release, index, 'assertions', shard);
        return assertionIds.flatMap((id) =>
          values[id] ? [values[id] as ThematicAssertion] : []
        );
      })
    )
  ).flat();
}

async function loadThemeShard(
  release: LoadedRelease,
  index: ThemeIndex,
  collection: 'assertions' | 'features',
  shard: string
): Promise<Record<string, unknown>> {
  const contract = index.collections[collection];
  if (!contract.shards.includes(shard)) return {};
  const path = contract.path_template.replace('{shard}', shard);
  const url = artifactUrl(release, path);
  let pending = themeShardCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<Record<string, unknown>>(release, path);
    themeShardCache.set(url, pending);
  }
  return pending;
}

/** Fetch only the small immutable shards needed by one selected map feature. */
export async function loadFeatureContent(
  release: LoadedRelease,
  featureId: string,
  shardHint?: string
): Promise<SelectedContent | null> {
  const indexPath = release.manifest.content_index_path;
  if (!indexPath) return null;
  const index = await loadContentIndex(release, indexPath);
  const linkShard = shardHint || (await contentShard(featureId, index.sharding.prefix_length));
  const links = await loadContentShard(release, index, 'feature_links', linkShard);
  const link = links[featureId] as FeatureContentLink | undefined;
  if (!link) return null;
  const [entities, dossiers] = await Promise.all([
    loadContentRecords<HistoricalEntity>(release, index, 'entities', [...new Set([...link.available_entity_ids, ...link.related_entity_ids])]),
    loadContentRecords<HistoricalDossier>(release, index, 'dossiers', link.dossier_ids)
  ]);
  return { link, entities, dossiers };
}

async function loadContentIndex(release: LoadedRelease, path: string): Promise<ContentIndex> {
  const url = artifactUrl(release, path);
  let pending = contentIndexCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<ContentIndex>(release, path);
    contentIndexCache.set(url, pending);
  }
  return pending;
}

async function loadContentRecords<T>(
  release: LoadedRelease,
  index: ContentIndex,
  collection: 'entities' | 'dossiers',
  ids: string[]
): Promise<T[]> {
  const idsByShard = new Map<string, string[]>();
  for (const id of ids) {
    const shard = await contentShard(id, index.sharding.prefix_length);
    idsByShard.set(shard, [...(idsByShard.get(shard) || []), id]);
  }
  return (
    await Promise.all(
      [...idsByShard].map(async ([shard, shardIds]) => {
        const values = await loadContentShard(release, index, collection, shard);
        return shardIds.flatMap((id) => (values[id] ? [values[id] as T] : []));
      })
    )
  ).flat();
}

async function loadContentShard(
  release: LoadedRelease,
  index: ContentIndex,
  collection: 'feature_links' | 'entities' | 'dossiers',
  shard: string
): Promise<Record<string, unknown>> {
  const contract = index.collections[collection];
  if (!contract.shards.includes(shard)) return {};
  const path = contract.path_template.replace('{shard}', shard);
  const url = artifactUrl(release, path);
  let pending = contentShardCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<Record<string, unknown>>(release, path);
    contentShardCache.set(url, pending);
  }
  return pending;
}

async function contentShard(identifier: string, prefixLength: number): Promise<string> {
  return (await sha256Hex(new TextEncoder().encode(identifier).buffer)).slice(0, prefixLength);
}

/** Load bounded historical context only after a map feature is selected. */
export async function loadWikiContext(
  release: LoadedRelease,
  featureId: string,
  year: number
): Promise<SelectedWikiContext | null> {
  const contextPath = release.manifest.wiki_context_index_path;
  const contentPath = release.manifest.content_index_path;
  if (!contextPath || !contentPath) return null;
  const contextUrl = artifactUrl(release, contextPath);
  let pendingIndex = wikiContextIndexCache.get(contextUrl);
  if (!pendingIndex) {
    pendingIndex = loadJsonArtifact<WikiContextIndex>(release, contextPath);
    wikiContextIndexCache.set(contextUrl, pendingIndex);
  }
  const contextIndex = await pendingIndex;
  const shard = await contentShard(featureId, contextIndex.sharding.prefix_length);
  if (!contextIndex.feature_contexts.shards.includes(shard)) return null;
  const shardPath = contextIndex.feature_contexts.path_template.replace('{shard}', shard);
  const shardUrl = artifactUrl(release, shardPath);
  let pendingShard = wikiContextShardCache.get(shardUrl);
  if (!pendingShard) {
    pendingShard = loadJsonArtifact<Record<string, unknown>>(release, shardPath);
    wikiContextShardCache.set(shardUrl, pendingShard);
  }
  const context = (await pendingShard)[featureId] as WikiFeatureContext | undefined;
  if (!context) return null;
  const margin = contextIndex.ranking_policy.temporal_margin_years;
  const activeItems = context.items.filter((item) => {
    if (item.relationship_types.some((relation) => relation === 'predecessor' || relation === 'successor')) return true;
    if (item.valid_from === null && item.valid_to === null) return true;
    const start = item.valid_from ?? item.valid_to ?? year;
    const end = item.valid_to ?? item.valid_from ?? year;
    return start <= year + margin && end >= year - margin;
  });
  const contentIndex = await loadContentIndex(release, contentPath);
  const [entities, dossiers] = await Promise.all([
    loadContentRecords<HistoricalEntity>(release, contentIndex, 'entities', activeItems.map((item) => item.context_entity_id)),
    loadContentRecords<HistoricalDossier>(release, contentIndex, 'dossiers', [...new Set(activeItems.flatMap((item) => item.dossier_ids))])
  ]);
  const entitiesById = new Map(entities.map((entity) => [entity.entity_id, entity]));
  const dossiersById = new Map(dossiers.map((dossier) => [dossier.dossier_id, dossier]));
  return {
    context,
    items: activeItems.flatMap((item) => {
      const entity = entitiesById.get(item.context_entity_id);
      return entity ? [{ ...item, entity, dossiers: item.dossier_ids.flatMap((id) => dossiersById.get(id) ?? []) }] : [];
    })
  };
}

/** Resolve one coarse discovery cell and time band; cells are not historical regions. */
export async function loadRegionalContext(
  release: LoadedRelease,
  longitude: number,
  latitude: number,
  year: number,
  excludeFeatureId?: string
): Promise<SelectedRegionalContext | null> {
  const indexPath = release.manifest.region_time_index_path;
  const contentPath = release.manifest.content_index_path;
  if (!indexPath || !contentPath) return null;
  const indexUrl = artifactUrl(release, indexPath);
  let pendingIndex = regionTimeIndexCache.get(indexUrl);
  if (!pendingIndex) {
    pendingIndex = loadJsonArtifact<RegionTimeIndex>(release, indexPath);
    regionTimeIndexCache.set(indexUrl, pendingIndex);
  }
  const index = await pendingIndex;
  const band = index.time_bands.find((item) => item.valid_from <= year && item.valid_to >= year);
  if (!band) return null;
  const cellId = regionCellId(longitude, latitude, index.grid.cell_degrees);
  const bucketId = `${band.band_id}|${cellId}`;
  const shard = await contentShard(bucketId, index.sharding.prefix_length);
  if (!index.buckets.shards.includes(shard)) return null;
  const shardPath = index.buckets.path_template.replace('{shard}', shard);
  const shardUrl = artifactUrl(release, shardPath);
  let pendingShard = regionTimeShardCache.get(shardUrl);
  if (!pendingShard) {
    pendingShard = loadJsonArtifact<Record<string, unknown>>(release, shardPath);
    regionTimeShardCache.set(shardUrl, pendingShard);
  }
  const bucket = (await pendingShard)[bucketId] as RegionTimeBucket | undefined;
  if (!bucket) return null;
  const entries = bucket.entries
    .filter((entry) => entry.valid_from <= year && entry.valid_to >= year)
    .filter((entry) => entry.feature_id !== excludeFeatureId)
    .sort((left, right) =>
      Number(right.kind === 'event') - Number(left.kind === 'event') ||
      Number(Boolean(right.dossier_ids.length)) - Number(Boolean(left.dossier_ids.length)) ||
      regionalDistance(left, longitude, latitude) - regionalDistance(right, longitude, latitude) ||
      left.entry_id.localeCompare(right.entry_id)
    )
    .slice(0, index.maximum_results_per_selection);
  const contentIndex = await loadContentIndex(release, contentPath);
  const entityIds = entries
    .filter((entry) => entry.entry_type === 'wikidata_entity')
    .map((entry) => entry.entity_id);
  const dossierIds = [...new Set(entries.flatMap((entry) => entry.dossier_ids))];
  const [entities, dossiers] = await Promise.all([
    loadContentRecords<HistoricalEntity>(release, contentIndex, 'entities', entityIds),
    loadContentRecords<HistoricalDossier>(release, contentIndex, 'dossiers', dossierIds)
  ]);
  return {
    bucket,
    entries,
    entities: new Map(entities.map((entity) => [entity.entity_id, entity])),
    dossiers: new Map(dossiers.map((dossier) => [dossier.dossier_id, dossier]))
  };
}

function regionCellId(longitude: number, latitude: number, cellDegrees: number): string {
  const boundedLongitude = Math.min(180, Math.max(-180, longitude));
  const boundedLatitude = Math.min(90, Math.max(-90, latitude));
  const longitudeIndex = Math.min(360 / cellDegrees - 1, Math.floor((boundedLongitude + 180) / cellDegrees));
  const latitudeIndex = Math.min(180 / cellDegrees - 1, Math.floor((boundedLatitude + 90) / cellDegrees));
  return `g${cellDegrees}:${longitudeIndex}:${latitudeIndex}`;
}

function regionalDistance(entry: RegionTimeEntry, longitude: number, latitude: number): number {
  const latitudeScale = Math.cos((latitude * Math.PI) / 180);
  return Math.hypot((entry.longitude - longitude) * latitudeScale, entry.latitude - latitude);
}

/** Resolve only the competing period definitions linked to this place and selected year. */
export async function loadChronologyContext(
  release: LoadedRelease,
  entityIds: string[],
  year: number
): Promise<HistoricalPeriodDefinition[]> {
  const indexPath = release.manifest.chronology_index_path;
  if (!indexPath || !entityIds.length) return [];
  const index = await loadChronologyIndex(release, indexPath);
  const entities = await loadChronologyRecords<ChronologyEntityIndex>(
    release,
    index,
    'entities',
    [...new Set(entityIds)]
  );
  const linkedPeriodIds = new Set(entities.flatMap((entity) => entity.period_ids));
  if (!linkedPeriodIds.size) return [];
  const band = index.time_bands.find(
    (candidate) => candidate.valid_from <= year && candidate.valid_to >= year
  );
  if (!band) return [];
  const bandUrl = artifactUrl(release, band.path);
  let pendingBand = chronologyBandCache.get(bandUrl);
  if (!pendingBand) {
    pendingBand = loadJsonArtifact<string[]>(release, band.path);
    chronologyBandCache.set(bandUrl, pendingBand);
  }
  const activePeriodIds = (await pendingBand).filter((periodId) =>
    linkedPeriodIds.has(periodId)
  );
  const definitions = await loadChronologyRecords<HistoricalPeriodDefinition>(
    release,
    index,
    'definitions',
    activePeriodIds
  );
  return definitions.sort(
    (left, right) =>
      left.valid_to - left.valid_from - (right.valid_to - right.valid_from) ||
      left.period_id.localeCompare(right.period_id)
  );
}

async function loadChronologyIndex(
  release: LoadedRelease,
  path: string
): Promise<ChronologyIndex> {
  const url = artifactUrl(release, path);
  let pending = chronologyIndexCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<ChronologyIndex>(release, path);
    chronologyIndexCache.set(url, pending);
  }
  return pending;
}

async function loadChronologyRecords<T>(
  release: LoadedRelease,
  index: ChronologyIndex,
  collection: 'definitions' | 'entities',
  ids: string[]
): Promise<T[]> {
  const idsByShard = new Map<string, string[]>();
  for (const id of ids) {
    const shard = await contentShard(id, index.sharding.prefix_length);
    idsByShard.set(shard, [...(idsByShard.get(shard) || []), id]);
  }
  return (
    await Promise.all(
      [...idsByShard].map(async ([shard, shardIds]) => {
        const contract = index.collections[collection];
        if (!contract.shards.includes(shard)) return [];
        const path = contract.path_template.replace('{shard}', shard);
        const url = artifactUrl(release, path);
        let pending = chronologyShardCache.get(url);
        if (!pending) {
          pending = loadJsonArtifact<Record<string, unknown>>(release, path);
          chronologyShardCache.set(url, pending);
        }
        const values = await pending;
        return shardIds.flatMap((id) => (values[id] ? [values[id] as T] : []));
      })
    )
  ).flat();
}

/** Fetch the causal adjacency and only the claim/path shards touching selected entities. */
export async function loadCausalContext(
  release: LoadedRelease,
  entityIds: string[]
): Promise<CausalContext> {
  const indexPath = release.manifest.causal_index_path;
  if (!indexPath || !entityIds.length) return { adjacency: [], claims: [], paths: [] };
  const index = await loadCausalIndex(release, indexPath);
  const adjacency = await loadCausalRecords<CausalEntityIndex>(release, index, 'entities', entityIds);
  const claimIds = [...new Set(adjacency.flatMap((record) => [
    ...record.incoming_claim_ids,
    ...record.outgoing_claim_ids
  ]))];
  const pathIds = [...new Set(adjacency.flatMap((record) => record.path_ids))];
  const [claims, paths] = await Promise.all([
    loadCausalRecords<CausalClaim>(release, index, 'claims', claimIds),
    loadCausalRecords<CausalPath>(release, index, 'paths', pathIds)
  ]);
  return { adjacency, claims, paths };
}

async function loadCausalIndex(release: LoadedRelease, path: string): Promise<CausalIndex> {
  const url = artifactUrl(release, path);
  let pending = causalIndexCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<CausalIndex>(release, path);
    causalIndexCache.set(url, pending);
  }
  return pending;
}

async function loadCausalRecords<T>(
  release: LoadedRelease,
  index: CausalIndex,
  collection: 'claims' | 'entities' | 'paths',
  ids: string[]
): Promise<T[]> {
  const idsByShard = new Map<string, string[]>();
  for (const id of ids) {
    const shard = await contentShard(id, index.sharding.prefix_length);
    idsByShard.set(shard, [...(idsByShard.get(shard) || []), id]);
  }
  return (
    await Promise.all(
      [...idsByShard].map(async ([shard, shardIds]) => {
        const contract = index.collections[collection];
        if (!contract.shards.includes(shard)) return [];
        const path = contract.path_template.replace('{shard}', shard);
        const url = artifactUrl(release, path);
        let pending = causalShardCache.get(url);
        if (!pending) {
          pending = loadJsonArtifact<Record<string, unknown>>(release, path);
          causalShardCache.set(url, pending);
        }
        const values = await pending;
        return shardIds.flatMap((id) => (values[id] ? [values[id] as T] : []));
      })
    )
  ).flat();
}

async function fetchVerifiedArtifact(release: LoadedRelease, path: string): Promise<ArrayBuffer> {
  const declared = artifact(release, path);
  if (!declared) throw new Error(`Release manifest does not declare ${path}`);
  const response = await fetch(artifactUrl(release, path), { cache: 'force-cache' });
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== declared.bytes || (await sha256Hex(bytes)) !== declared.checksum_sha256) {
    throw new Error(`Release artifact checksum did not match for ${path}`);
  }
  return bytes;
}

function indexEntity(map: Map<string, HistoricalEntity>, entity: HistoricalEntity): void {
  map.set(entity.entity_id, entity);
  if (entity.wikidata_id) {
    map.set(entity.wikidata_id, entity);
    map.set(`wikidata:${entity.wikidata_id}`, entity);
  }
}

/** Optional reading content is deliberately fetched only after a reader opens a record. */
export async function loadContentBundle(release: LoadedRelease): Promise<ContentBundle> {
  const entityArtifact = artifact(release, 'entities.ndjson');
  const dossierArtifact = artifact(release, 'dossiers.ndjson');
  const linkArtifact = artifact(release, 'feature-content.ndjson');

  const [entityRecords, dossierRecords, linkRecords] = await Promise.all([
    entityArtifact
      ? loadNdjson<HistoricalEntity>(artifactUrl(release, entityArtifact.path))
      : Promise.resolve([]),
    dossierArtifact
      ? loadNdjson<HistoricalDossier>(artifactUrl(release, dossierArtifact.path))
      : Promise.resolve([]),
    linkArtifact
      ? loadNdjson<FeatureContentLink>(artifactUrl(release, linkArtifact.path))
      : Promise.resolve([])
  ]);

  const entities = new Map<string, HistoricalEntity>();
  for (const entity of entityRecords) indexEntity(entities, entity);
  return {
    entities,
    dossiers: new Map(dossierRecords.map((dossier) => [dossier.dossier_id, dossier])),
    featureLinks: new Map(linkRecords.map((link) => [link.feature_id, link])),
    hasEntities: Boolean(entityArtifact),
    hasDossiers: Boolean(dossierArtifact),
    hasFeatureLinks: Boolean(linkArtifact)
  };
}
