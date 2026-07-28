export interface SearchRecord {
  entity_id: string;
  dossier_ids?: string[];
  content_shard?: string;
  feature_ids: string[];
  kind: string;
  themes?: string[];
  source_ids?: string[];
  year_dossier_years?: number[];
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
