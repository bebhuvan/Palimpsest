import type {
  Artifact,
  BuildManifest,
  LatestPointer,
  LoadedRelease,
  SourceReference
} from '$lib/release-contracts';
import type {
  ContentBundle,
  ContentIndex,
  DossierRestatement,
  FeatureContentLink,
  HistoricalDossier,
  HistoricalEntity,
  PublishedEditorialDossier,
  SelectedContent
} from '$lib/content-contracts';
import type {
  AssertionAdjacency,
  AssertionIndex,
  CausalClaim,
  CausalContext,
  CausalEntityIndex,
  CausalIndex,
  CausalPath,
  EvidenceAssertion,
  RegionTimeBucket,
  RegionTimeEntry,
  RegionTimeIndex,
  SelectedRegionalContext,
  SelectedWikiContext,
  ThematicAssertion,
  ThemeFeatureIndex,
  ThemeIndex,
  WikiFeatureContext,
  WikiContextIndex
} from '$lib/context-contracts';
import type {
  ChronologyEntityIndex,
  ChronologyIndex,
  HistoricalMapMetadata,
  HistoricalPeriodDefinition,
  IntegrationIndex,
  LayerCatalog
} from '$lib/map-contracts';
import { searchableNames } from '$lib/search-records';
import type {
  SearchRecord,
  StaticSearchIndex
} from '$lib/search-records';

export type {
  Artifact,
  AttributionReport,
  BuildManifest,
  CoverageCell,
  LatestPointer,
  LoadedRelease,
  QualityReport,
  SourceReference
} from '$lib/release-contracts';
export type {
  ContentBundle,
  ContentIndex,
  ContentRelationship,
  DossierRestatement,
  FeatureContentLink,
  HistoricalDossier,
  HistoricalEntity,
  PublishedEditorialDossier,
  RestatementTimelineEntry,
  SelectedContent
} from '$lib/content-contracts';
export type {
  AssertionAdjacency,
  AssertionIndex,
  CausalClaim,
  CausalContext,
  CausalEntityIndex,
  CausalIndex,
  CausalPath,
  CausalTemporalAnchor,
  EvidenceAssertion,
  RegionTimeBucket,
  RegionTimeEntry,
  RegionTimeIndex,
  SelectedRegionalContext,
  SelectedWikiContext,
  ThematicAssertion,
  ThemeFeatureIndex,
  ThemeIndex,
  WikiContextIndex,
  WikiContextItem,
  WikiContextRole,
  WikiFeatureContext
} from '$lib/context-contracts';
export type {
  ChronologyEntityIndex,
  ChronologyIndex,
  HistoricalMapMetadata,
  HistoricalMapRights,
  HistoricalMapRightsApproval,
  HistoricalMapRightsScope,
  HistoricalPeriodDefinition,
  LayerCatalog,
  LayerDefinition
} from '$lib/map-contracts';
export {
  closestNameForYear,
  displayNameForYear,
  nameForYear,
  searchableNames
} from '$lib/search-records';
export type {
  HistoricalNameAttestation,
  SearchRecord,
  StaticSearchIndex
} from '$lib/search-records';

import {
  artifact,
  artifactShard as contentShard,
  artifactUrl,
  fetchVerifiedArtifact,
  loadJsonArtifact,
  loadNdjson
} from '$lib/release-data';

export {
  artifact,
  artifactUrl,
  loadJsonArtifact,
  loadNdjson,
  loadRelease
} from '$lib/release-data';
export {
  loadSearchIndex,
  loadSearchPage,
  loadSearchRecord,
  loadSearchTimeBand,
  loadStaticSearchIndex,
  normalizeSearchQuery,
  searchStaticRecords
} from '$lib/search-data';
export {
  loadHistoricalMapImage,
  loadHistoricalMaps,
  loadLayerCatalog
} from '$lib/map-data';

const MAX_VISIBLE_CONTEXT_ITEMS = 20;
const MAX_VISIBLE_LINKED_ENTITIES = 12;
const MAX_VISIBLE_RELATIONSHIP_TARGETS = 12;

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
  const directlyLinkedIds = [
    link.primary_entity_id,
    ...link.available_entity_ids
  ]
    .filter((entityId, position, values) => values.indexOf(entityId) === position)
    .filter((entityId) => link.available_entity_ids.includes(entityId))
    .slice(0, MAX_VISIBLE_LINKED_ENTITIES);
  const [directlyLinkedEntities, dossiers, restatementRecords] = await Promise.all([
    loadContentRecords<HistoricalEntity>(release, index, 'entities', directlyLinkedIds),
    loadContentRecords<HistoricalDossier>(release, index, 'dossiers', link.dossier_ids),
    // Restatements are sharded by their source dossier ID, so this reuses the same shard keys and
    // adds no round trip beyond the shards a reader would fetch anyway.
    index.collections.restatements
      ? loadContentRecords<DossierRestatement>(release, index, 'restatements', link.dossier_ids)
      : Promise.resolve([])
  ]);
  const restatements = new Map(
    restatementRecords.map((restatement) => [restatement.dossier_id, restatement])
  );
  const primaryEntity =
    directlyLinkedEntities.find(
      (entity) => entity.entity_id === link.primary_entity_id
    ) ?? directlyLinkedEntities[0];
  const relationshipTargetIds = [
    ...new Set(
      (primaryEntity?.relationships ?? []).map(
        (relationship) => relationship.target_entity_id
      )
    )
  ]
    .filter((entityId) => !directlyLinkedIds.includes(entityId))
    .slice(0, MAX_VISIBLE_RELATIONSHIP_TARGETS);
  const relationshipEntities = relationshipTargetIds.length
    ? await loadContentRecords<HistoricalEntity>(
        release,
        index,
        'entities',
        relationshipTargetIds
      )
    : [];
  const entities = [
    ...new Map(
      [...directlyLinkedEntities, ...relationshipEntities].map((entity) => [
        entity.entity_id,
        entity
      ])
    ).values()
  ];
  return { link, entities, dossiers, restatements };
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
  collection: 'entities' | 'dossiers' | 'restatements',
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
  collection: 'feature_links' | 'entities' | 'dossiers' | 'restatements',
  shard: string
): Promise<Record<string, unknown>> {
  const contract = index.collections[collection];
  if (!contract || !contract.shards.includes(shard)) return {};
  const path = contract.path_template.replace('{shard}', shard);
  const url = artifactUrl(release, path);
  let pending = contentShardCache.get(url);
  if (!pending) {
    pending = loadJsonArtifact<Record<string, unknown>>(release, path);
    contentShardCache.set(url, pending);
  }
  return pending;
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
  const visibleItems = activeItems.slice(0, MAX_VISIBLE_CONTEXT_ITEMS);
  const contentIndex = await loadContentIndex(release, contentPath);
  const [entities, dossiers] = await Promise.all([
    loadContentRecords<HistoricalEntity>(release, contentIndex, 'entities', visibleItems.map((item) => item.context_entity_id)),
    loadContentRecords<HistoricalDossier>(release, contentIndex, 'dossiers', [...new Set(visibleItems.flatMap((item) => item.dossier_ids))])
  ]);
  const entitiesById = new Map(entities.map((entity) => [entity.entity_id, entity]));
  const dossiersById = new Map(dossiers.map((dossier) => [dossier.dossier_id, dossier]));
  return {
    context,
    total_items: activeItems.length,
    items: visibleItems.flatMap((item) => {
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
  const visibleEntries = entries.slice(0, MAX_VISIBLE_CONTEXT_ITEMS);
  const contentIndex = await loadContentIndex(release, contentPath);
  const entityIds = visibleEntries
    .filter((entry) => entry.entry_type === 'wikidata_entity')
    .map((entry) => entry.entity_id);
  const dossierIds = [
    ...new Set(
      visibleEntries
        .filter((entry) => entry.entry_type === 'wikidata_entity')
        .flatMap((entry) => entry.dossier_ids)
    )
  ];
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
