import type { LoadedRelease } from '$lib/release-contracts';
import type {
  AuthorityMatch,
  HistoricalMapMetadata,
  IntegrationIndex,
  LayerCatalog
} from '$lib/map-contracts';
import {
  artifact,
  fetchVerifiedArtifact,
  loadJsonArtifact
} from '$lib/release-data';

export async function loadLayerCatalog(
  release: LoadedRelease
): Promise<LayerCatalog | null> {
  const path = release.manifest.layer_catalog_path;
  return path ? loadJsonArtifact<LayerCatalog>(release, path) : null;
}

function approvedHistoricalMap(
  release: LoadedRelease,
  historicalMap: HistoricalMapMetadata
): boolean {
  const rendering = historicalMap.rendering;
  if (!rendering) return false;
  const approvalScopes = historicalMap.release_rights_approvals.map(
    (approval) => approval.status === 'approved' && approval.scope
  );
  if (
    approvalScopes.join(',') !== 'metadata,media,georeference'
    || new Set(
      historicalMap.release_rights_approvals.map((approval) => approval.decision_id)
    ).size !== 3
  ) {
    return false;
  }
  if (
    historicalMap.metadata_rights.scope !== 'metadata'
    || historicalMap.image_rights.scope !== 'media'
    || historicalMap.georeference_rights.scope !== 'georeference'
    || historicalMap.known_limitations.length === 0
  ) {
    return false;
  }
  if (
    !rendering.image_path.startsWith('historical-maps/')
    || rendering.image_path.includes('..')
    || rendering.image_path.includes('://')
  ) {
    return false;
  }
  const imageArtifact = artifact(release, rendering.image_path);
  const coordinateKeys = new Set(
    rendering.coordinates.map(([longitude, latitude]) => `${longitude},${latitude}`)
  );
  return Boolean(
    imageArtifact
    && imageArtifact.checksum_sha256 === rendering.image_checksum_sha256
    && rendering.coordinates.length === 4
    && coordinateKeys.size === 4
    && rendering.coordinates.every(
      ([longitude, latitude]) =>
        Number.isFinite(longitude)
        && Number.isFinite(latitude)
        && longitude >= -180
        && longitude <= 180
        && latitude >= -90
        && latitude <= 90
    )
  );
}

/** Return only release-published maps whose three rights scopes passed review. */
export async function loadHistoricalMaps(
  release: LoadedRelease
): Promise<HistoricalMapMetadata[]> {
  const indexPath = 'integrations/index.json';
  if (!artifact(release, indexPath)) return [];
  const index = await loadJsonArtifact<IntegrationIndex>(release, indexPath);
  if (
    index.semantics !== 'build-time-reviewed-source-integrations'
    || !artifact(release, index.historical_maps_path)
  ) {
    return [];
  }
  const bytes = await fetchVerifiedArtifact(release, index.historical_maps_path);
  const maps = new TextDecoder()
    .decode(bytes)
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as HistoricalMapMetadata);
  if (maps.length !== index.historical_map_count) {
    throw new Error('Historical-map integration count did not match its release index.');
  }
  return maps.filter((historicalMap) => approvedHistoricalMap(release, historicalMap));
}

/**
 * Load only editorially accepted authority identities.
 *
 * Proposed/rejected candidates are deliberately unavailable to reader components,
 * even if a malformed release includes them in the integration artifact.
 */
export async function loadAuthorityMatches(
  release: LoadedRelease
): Promise<AuthorityMatch[]> {
  const indexPath = 'integrations/index.json';
  if (!artifact(release, indexPath)) return [];
  const index = await loadJsonArtifact<IntegrationIndex>(release, indexPath);
  if (
    index.semantics !== 'build-time-reviewed-source-integrations'
    || !artifact(release, index.authority_matches_path)
  ) {
    return [];
  }
  const bytes = await fetchVerifiedArtifact(release, index.authority_matches_path);
  const matches = new TextDecoder()
    .decode(bytes)
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as AuthorityMatch);
  if (matches.length !== index.authority_match_count) {
    throw new Error('Authority-match integration count did not match its release index.');
  }
  return matches.filter(
    (match) =>
      match.review_status === 'accepted'
      && (match.relation === 'exact_match' || match.relation === 'close_match')
      && match.rights.scope === 'metadata'
      && Boolean(match.source_ref.url)
  );
}

export async function loadHistoricalMapImage(
  release: LoadedRelease,
  historicalMap: HistoricalMapMetadata
): Promise<ArrayBuffer> {
  if (!approvedHistoricalMap(release, historicalMap) || !historicalMap.rendering) {
    throw new Error('Historical map image does not have complete release approval.');
  }
  return fetchVerifiedArtifact(release, historicalMap.rendering.image_path);
}
