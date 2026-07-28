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
  EntityReadingEligibility,
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
  AuthorityMatch,
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
  EntityReadingEligibility,
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
  AuthorityMatch,
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
  loadAuthorityMatches,
  loadHistoricalMapImage,
  loadHistoricalMaps,
  loadLayerCatalog
} from '$lib/map-data';

export {
  loadCausalContext,
  loadChronologyContext,
  loadContentBundle,
  loadEvidenceAssertions,
  loadFeatureContent,
  loadRegionalContext,
  loadThemeAssertions,
  loadWikiContext
} from '$lib/historical-context-data';
