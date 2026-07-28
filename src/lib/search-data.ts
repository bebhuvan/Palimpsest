import type { LoadedRelease } from '$lib/release-contracts';
import {
  artifact,
  artifactShard,
  artifactUrl,
  fetchVerifiedArtifact,
  loadJsonArtifact
} from '$lib/release-data';
import {
  searchableNames,
  type SearchRecord,
  type StaticSearchIndex
} from '$lib/search-records';

const staticSearchIndexCache = new Map<string, Promise<StaticSearchIndex>>();
const staticSearchArrayCache = new Map<string, Promise<SearchRecord[]>>();
const staticSearchRecordShardCache = new Map<string, Promise<Record<string, SearchRecord>>>();
const staticSearchFeatureShardCache = new Map<string, Promise<Record<string, string>>>();

export async function loadSearchIndex(
  release: LoadedRelease,
  path: string
): Promise<SearchRecord[]> {
  const bytes = await fetchVerifiedArtifact(release, path);
  return new TextDecoder()
    .decode(bytes)
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as SearchRecord);
}

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
        index.semantics !== 'lazy-static-search-over-release-records'
        || index.compression !== 'gzip'
        || index.name_ngrams.length !== 2
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
  return loadCompressedSearchArray(
    release,
    index.pages.path_template.replace('{page}', page)
  );
}

export async function loadSearchRecord(
  release: LoadedRelease,
  index: StaticSearchIndex,
  identifiers: { entityId?: string | null; featureId?: string | null }
): Promise<SearchRecord | null> {
  let entityId = identifiers.entityId || null;
  if (!entityId && identifiers.featureId) {
    const featureShard = await artifactShard(identifiers.featureId, 2);
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

  const recordShard = await artifactShard(entityId, 2);
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
      const stream = new Blob([bytes])
        .stream()
        .pipeThrough(new DecompressionStream('gzip'));
      const decoded = await new Response(stream).arrayBuffer();
      return JSON.parse(new TextDecoder().decode(decoded)) as SearchRecord[];
    });
    staticSearchArrayCache.set(url, pending);
  }
  return pending;
}
