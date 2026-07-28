<script lang="ts">
  import { onMount } from 'svelte';
  import { replaceState } from '$app/navigation';
  import type { GeoJSONFeature, GeoJSONSource, Map as MapLibreMap, MapGeoJSONFeature } from 'maplibre-gl';
  import type { Protocol } from 'pmtiles';
  import type { FeatureCollection, Point, Polygon } from 'geojson';
  import HistoricalTimeline from '$lib/components/HistoricalTimeline.svelte';
  import InstrumentRail from '$lib/components/InstrumentRail.svelte';
  import ProjectAboutDialog from '$lib/components/ProjectAboutDialog.svelte';
  import SearchOverlay from '$lib/components/SearchOverlay.svelte';
  import ViewPanel from '$lib/components/ViewPanel.svelte';
  import RecordDiscoverySections from '$lib/components/RecordDiscoverySections.svelte';
  import RecordAuthorityConnections from '$lib/components/RecordAuthorityConnections.svelte';
  import RecordEvidence from '$lib/components/RecordEvidence.svelte';
  import RecordIdentityHeader from '$lib/components/RecordIdentityHeader.svelte';
  import RecordInterpretiveContext from '$lib/components/RecordInterpretiveContext.svelte';
  import RecordPrimaryReading from '$lib/components/RecordPrimaryReading.svelte';
  import RecordStructuredFacts from '$lib/components/RecordStructuredFacts.svelte';
  import RecordThematicReading from '$lib/components/RecordThematicReading.svelte';
  import {
    artifact,
    artifactUrl,
    closestNameForYear,
    displayNameForYear,
    loadContentBundle,
    loadAuthorityMatches,
    loadChronologyContext,
    loadFeatureContent,
    loadHistoricalMapImage,
    loadHistoricalMaps,
    loadJsonArtifact,
    loadRelease,
    loadLayerCatalog,
    loadRegionalContext,
    loadSearchIndex,
    loadSearchRecord,
    loadSearchTimeBand,
    loadStaticSearchIndex,
    loadWikiContext,
    nameForYear,
    normalizeSearchQuery,
    searchStaticRecords,
    searchableNames,
    type AttributionReport,
    type AuthorityMatch,
    type ContentBundle,
    type CausalClaim,
    type CausalPath,
    type CoverageCell,
    type EvidenceAssertion,
    type FeatureContentLink,
    type DossierRestatement,
    type HistoricalDossier,
    type HistoricalEntity,
    type HistoricalMapMetadata,
    type HistoricalPeriodDefinition,
    type LoadedRelease,
    type LayerCatalog,
    type QualityReport,
    type SearchRecord,
    type StaticSearchIndex,
    type SelectedRegionalContext,
    type SelectedWikiContext,
    type SourceReference,
    type ThematicAssertion
  } from '$lib/data';
  import {
    eraForYear,
    eraLabel,
    formatRange,
    formatYear,
    MAXIMUM_YEAR,
    normalizeYear,
    stepYear,
    type Era
  } from '$lib/history';
  import {
    HISTORICAL_LENSES,
    isHistoricalLens,
    lensDefinition,
    recordMatchesLens,
    type HistoricalLens
  } from '$lib/lenses';
  import LensMark from '$lib/components/LensMark.svelte';
  import {
    applyLayerModePresentation,
    applyMapYearPresentation,
    COVERAGE_EDGE_LAYER,
    COVERAGE_FILL_LAYER,
    COVERAGE_SOURCE,
    HISTORICAL_MAP_IMAGE_LAYER,
    HISTORICAL_MAP_IMAGE_SOURCE,
    HISTORY_LAYERS,
    lensAccent,
    MAP_SOURCE,
    THEME_DISCOVERY_SOURCE,
    installReviewedHistoryLayers
  } from '$lib/map-presentation';
  import { bindMapInteractions } from '$lib/map-interactions';
  import { availableYears, loadYearIndex } from '$lib/year-data';
  import { humanize } from '$lib/reader-presentation';
  import type { MapSelection as Selection } from '$lib/selection-contracts';
  import { loadSelectionSupplement } from '$lib/selection-reading';
  import {
    FIRST_OHM_LABEL_LAYER,
    historyMapStyle,
    updateOhmYear,
    type HistoricalLayerMode
  } from '$lib/ohm';
  import 'maplibre-gl/dist/maplibre-gl.css';

  const DATA_BASE = (import.meta.env.VITE_DATA_BASE as string | undefined) || '/data';

  let mapContainer: HTMLDivElement;
  let aboutDialog: ProjectAboutDialog;
  let searchOverlay: SearchOverlay;
  let searchOpen = false;
  let viewOpen = false;
  let map: MapLibreMap | null = null;
  let pmtilesProtocol: Protocol | null = null;
  let removeMapInteractions: (() => void) | null = null;
  let release: LoadedRelease | null = null;
  let staticSearchIndex: StaticSearchIndex | null = null;
  let searchIndex: SearchRecord[] = [];
  let searchResults: SearchRecord[] = [];
  let coverage: CoverageCell[] = [];
  let searchQuery = '';
  let selectedYear = 1200;
  let activeEra: Era = eraForYear(selectedYear);
  let selected: Selection | null = null;
  let selectedEntity: HistoricalEntity | null = null;
  let linkedEntities: HistoricalEntity[] = [];
  let selectedDossiers: HistoricalDossier[] = [];
  let selectedRestatements: Map<string, DossierRestatement> = new Map();
  let selectedLink: FeatureContentLink | null = null;
  let selectedCausalClaims: CausalClaim[] = [];
  let selectedCausalPaths: CausalPath[] = [];
  let selectedPeriods: HistoricalPeriodDefinition[] = [];
  let selectedWikiContext: SelectedWikiContext | null = null;
  let selectedRegionalContext: SelectedRegionalContext | null = null;
  let selectedThematicAssertions: ThematicAssertion[] = [];
  let selectedEvidenceAssertions: EvidenceAssertion[] = [];
  let authorityMatches: AuthorityMatch[] = [];
  let layerCatalog: LayerCatalog | null = null;
  let historicalMaps: HistoricalMapMetadata[] = [];
  let selectedHistoricalMapId = '';
  let historicalMapVisible = false;
  let historicalMapLoading = false;
  let historicalMapError = '';
  let historicalMapObjectUrl: string | null = null;
  let historicalMapRequest = 0;
  let selectedFeatureStateId: string | null = null;
  let hoveredFeatureStateId: string | null = null;
  let contentPromise: Promise<ContentBundle> | null = null;
  let contentLoading = false;
  let contentError = '';
  let loading = true;
  let loadingEra = false;
  let errorMessage = '';
  let mapReady = false;
  let playing = false;
  let playTimer: ReturnType<typeof setInterval> | null = null;
  let quality: QualityReport | null = null;
  let attributions: AttributionReport | null = null;
  let reducedMotion = false;
  let detailLimitReached = false;
  let mapAnnouncement = '';
  let linkedRecordToRestore: SearchRecord | null = null;
  let layerMode: HistoricalLayerMode = 'combined';
  let activeLens: HistoricalLens = 'all';
  let evidenceOverlay: 'none' | 'confidence' | 'provenance' = 'none';
  let yearsWithDossier: Set<number> = new Set();

  $: activeHistoricalMap = historicalMaps.find(
    (historicalMap) => historicalMap.map_id === selectedHistoricalMapId
  ) ?? null;
  $: activeLensDefinition = lensDefinition(activeLens);
  $: dossierYear = yearsWithDossier.has(selectedYear) ? selectedYear : null;
  $: activeDatedRecords = searchIndex.filter(
    (record) => record.valid_from <= selectedYear && record.valid_to >= selectedYear
  );
  $: activeLensRecordCount = activeDatedRecords.filter(
    (record) => recordMatchesLens(record, activeLens)
  ).length;
  $: lensCounts = new Map(
    HISTORICAL_LENSES.map((lens) => [
      lens.id,
      activeDatedRecords.filter((record) => recordMatchesLens(record, lens.id)).length
    ])
  );
  $: selectedSource = selected?.sourceRole === 'reviewed' ? sourceForFeature(selected) : null;
  $: selectedPrimaryEligibility = selectedLink?.reading_eligibility?.find(
    (decision) => decision.entity_id === selectedLink?.primary_entity_id
  );
  $: selectedSearchRecord = selected?.sourceRole === 'reviewed'
    ? searchIndex.find((record) => record.entity_id === selected?.entityId || record.feature_ids.includes(selected?.featureId ?? ''))
    : undefined;
  $: alternateNames = selected?.sourceRole === 'reviewed'
    ? Array.from(new Set([
        ...(selectedSearchRecord?.name_attestations ?? [])
          .filter((name) => name.valid_from <= selectedYear && name.valid_to >= selectedYear)
          .map((name) => name.text),
        ...(selectedPrimaryEligibility?.reading_eligible
          ? Object.values(selectedEntity?.names ?? {})
          : []),
        ...(selectedPrimaryEligibility?.reading_eligible
          ? Object.values(selectedEntity?.aliases ?? {}).flat()
          : [])
      ])).filter((name) => name !== selected?.name)
    : [];
  $: selectedRelationships = selectedEntity?.relationships ?? [];
  $: elsewhere = selected?.sourceRole === 'reviewed' ? elsewhereAtThisTime(selected) : [];
  $: visibleThematicAssertions = selectedThematicAssertions.filter(
    (assertion) => activeLens === 'all' || assertion.theme === activeLens
  );
  $: selectedAuthorityMatches = (() => {
    if (selected?.sourceRole !== 'reviewed') return [];
    const subjectIds = new Set([
      selected.featureId,
      selected.entityId,
      selected.wikidataId,
      selected.wikidataId ? `wikidata:${selected.wikidataId}` : undefined,
      selectedEntity?.entity_id,
      selectedEntity?.wikidata_id,
      selectedEntity?.wikidata_id ? `wikidata:${selectedEntity.wikidata_id}` : undefined,
      selectedLink?.primary_entity_id,
      ...(selectedLink?.entity_ids ?? [])
    ].filter(Boolean));
    return authorityMatches.filter((match) => subjectIds.has(match.subject_id));
  })();

  function scoreResult(record: SearchRecord, query: string): number {
    const names = searchableNames(record).map(normalizeSearchQuery);
    if (names.includes(query)) return 0;
    if (names.some((name) => name.startsWith(query))) return 1;
    return 2;
  }

  function mergeSearchRecords(records: SearchRecord[]): void {
    const merged = new Map(searchIndex.map((record) => [record.entity_id, record]));
    for (const record of records) merged.set(record.entity_id, record);
    searchIndex = [...merged.values()];
  }

  let searchRequest = 0;
  async function updateSearchResults(): Promise<void> {
    const request = ++searchRequest;
    const query = normalizeSearchQuery(searchQuery);
    if (query.length < 2 || !release) {
      searchResults = [];
      return;
    }
    try {
      const candidates = staticSearchIndex
        ? await searchStaticRecords(release, staticSearchIndex, query)
        : searchIndex.filter((record) =>
            searchableNames(record).some((name) =>
              normalizeSearchQuery(name).includes(query)
            )
          );
      if (request !== searchRequest) return;
      mergeSearchRecords(candidates);
      searchResults = candidates
        .filter((record) => recordMatchesLens(record, activeLens))
        .sort((left, right) => scoreResult(left, query) - scoreResult(right, query))
        .slice(0, 8);
    } catch {
      if (request === searchRequest) searchResults = [];
    }
  }

  async function updateSearchTimeBand(year: number): Promise<void> {
    if (!release || !staticSearchIndex) return;
    const records = await loadSearchTimeBand(release, staticSearchIndex, year);
    if (year !== selectedYear) return;
    const retained = searchResults.filter(
      (record) => !records.some((candidate) => candidate.entity_id === record.entity_id)
    );
    searchIndex = [...records, ...retained];
    updateThemeDiscoveryLayer();
  }

  function displayName(record: SearchRecord): string {
    return displayNameForYear(record, selectedYear);
  }

  function availableYearForRecord(record: SearchRecord, preferredYear: number): number {
    if (nameForYear(record, preferredYear)) return preferredYear;
    const closest = closestNameForYear(record, preferredYear);
    if (!closest) return preferredYear < record.valid_from || preferredYear > record.valid_to ? record.valid_from : preferredYear;
    if (preferredYear < closest.valid_from) return closest.valid_from;
    if (preferredYear > closest.valid_to) return closest.valid_to;
    return preferredYear;
  }

  function numberProperty(properties: Record<string, unknown>, key: string): number {
    return Number(properties[key] ?? 0);
  }

  function selectionFromFeature(
    feature: MapGeoJSONFeature | GeoJSONFeature,
    longitude?: number,
    latitude?: number
  ): Selection {
    const properties = feature.properties as Record<string, unknown>;
    const wikidataId = properties.wikidata_id ? String(properties.wikidata_id) : undefined;
    const featureId = String(properties.feature_id ?? feature.id ?? '');
    const entityId = properties.primary_entity_id ? String(properties.primary_entity_id) : wikidataId;
    const record = searchIndex.find((item) =>
      item.feature_ids.includes(featureId) || item.entity_id === entityId
    );
    const nameAttestation = record
      ? nameForYear(record, selectedYear, featureId) ?? nameForYear(record, selectedYear) ?? undefined
      : undefined;
    return {
      sourceRole: 'reviewed',
      featureId,
      entityId,
      name: nameAttestation?.text ?? String(properties.name ?? 'Unnamed place'),
      kind: String(properties.kind ?? 'historical feature'),
      validFrom: numberProperty(properties, 'valid_from'),
      validTo: numberProperty(properties, 'valid_to'),
      spatialMeaning: String(properties.spatial_meaning ?? 'unknown'),
      temporalConfidence: String(properties.temporal_confidence ?? 'unknown'),
      spatialConfidence: String(properties.spatial_confidence ?? 'unknown'),
      interpretiveConfidence: String(properties.interpretive_confidence ?? 'unknown'),
      reviewStatus: String(properties.review_status ?? 'unreviewed'),
      wikidataId,
      disputeGroup: properties.dispute_group ? String(properties.dispute_group) : undefined,
      contentShard: properties.content_shard ? String(properties.content_shard) : undefined,
      sourceId: properties.source_id ? String(properties.source_id) : undefined,
      sourceReference:
        properties.source_id && properties.source_title && properties.source_url
          ? {
              source_id: String(properties.source_id),
              record_id: properties.source_record_id
                ? String(properties.source_record_id)
                : undefined,
              title: String(properties.source_title),
              publisher: String(properties.source_publisher ?? properties.source_id),
              url: String(properties.source_url),
              license_id: String(properties.license_id ?? ''),
              citation: String(properties.source_citation ?? properties.source_title),
              version: properties.source_version
                ? String(properties.source_version)
                : undefined
            }
          : undefined,
      yearDossierYears: Array.isArray(properties.year_dossier_years)
        ? properties.year_dossier_years.map(Number).filter(Number.isFinite)
        : [],
      nameAttestation,
      longitude: longitude ?? record?.longitude,
      latitude: latitude ?? record?.latitude
    };
  }

  function selectionFromSearch(record: SearchRecord, year: number): Selection {
    const nameAttestation = nameForYear(record, year) ?? undefined;
    const featureId = nameAttestation?.feature_id ?? record.feature_ids.find((id) => {
      const parts = id.split(':');
      const from = Number(parts.at(-3));
      const to = Number(parts.at(-2));
      return Number.isFinite(from) && Number.isFinite(to) && from <= year && to >= year;
    }) ?? record.feature_ids[0] ?? '';
    const featureParts = featureId.split(':');
    const featureFrom = Number(featureParts.at(-3));
    const featureTo = Number(featureParts.at(-2));
    const wikidataId = record.entity_id.match(/(?:^|:)(Q\d+)$/)?.[1];
    return {
      sourceRole: 'reviewed',
      featureId,
      entityId: record.entity_id,
      name: nameAttestation?.text ?? displayNameForYear(record, year),
      kind: record.kind,
      validFrom: Number.isFinite(featureFrom) ? featureFrom : record.valid_from,
      validTo: Number.isFinite(featureTo) ? featureTo : record.valid_to,
      spatialMeaning: 'unknown',
      temporalConfidence: 'unknown',
      spatialConfidence: 'unknown',
      interpretiveConfidence: 'unknown',
      reviewStatus: 'unreviewed',
      yearDossierYears: record.year_dossier_years ?? [],
      wikidataId,
      nameAttestation,
      longitude: record.longitude,
      latitude: record.latitude
    };
  }

  function optionalProperty(properties: Record<string, unknown>, key: string): string | undefined {
    const value = properties[key];
    return value === undefined || value === null || value === '' ? undefined : String(value);
  }

  function historicalYearFromOhmDecimal(value: unknown): number | null {
    const decimal = Number(value);
    if (!Number.isFinite(decimal)) return null;
    const astronomicalYear = Math.floor(decimal);
    return astronomicalYear <= 0 ? astronomicalYear - 1 : astronomicalYear;
  }

  function selectionFromOhmFeature(
    feature: MapGeoJSONFeature,
    longitude?: number,
    latitude?: number
  ): Selection {
    const properties = feature.properties as Record<string, unknown>;
    const sourceLayer = feature.sourceLayer || 'historical detail';
    const elementId = optionalProperty(properties, 'osm_id') ?? optionalProperty(properties, 'id');
    const groupId = optionalProperty(properties, 'group_id');
    const from = historicalYearFromOhmDecimal(properties.start_decdate);
    const to = historicalYearFromOhmDecimal(properties.end_decdate);
    const datesComplete = from !== null && to !== null;
    const dateLabel = datesComplete
      ? formatRange(from, to)
      : from !== null
        ? `From ${formatYear(from)} · no end supplied`
        : to !== null
          ? `Until ${formatYear(to)} · no start supplied`
          : 'No date interval supplied in the live tile';
    return {
      sourceRole: 'ohm',
      featureId: `ohm:${sourceLayer}:${elementId ?? 'unidentified'}:${groupId ?? '0'}`,
      name: optionalProperty(properties, 'name') ?? optionalProperty(properties, 'name_en') ?? 'Unnamed OHM feature',
      kind: optionalProperty(properties, 'type') ?? sourceLayer,
      validFrom: from ?? selectedYear,
      validTo: to ?? selectedYear,
      dateLabel,
      spatialMeaning: 'ohm_contributor_detail',
      temporalConfidence: 'not assessed by Palimpsest',
      spatialConfidence: 'not assessed by Palimpsest',
      interpretiveConfidence: 'not assessed by Palimpsest',
      reviewStatus: 'live contributor record',
      longitude,
      latitude,
      ohm: {
        sourceLayer,
        elementId,
        startDate: optionalProperty(properties, 'start_date'),
        endDate: optionalProperty(properties, 'end_date'),
        source: optionalProperty(properties, 'source'),
        sourceRef: optionalProperty(properties, 'source_ref'),
        license: optionalProperty(properties, 'license'),
        copyright: optionalProperty(properties, 'copyright'),
        attribution: optionalProperty(properties, 'attribution'),
        changeset: optionalProperty(properties, 'changeset'),
        datesComplete
      }
    };
  }

  function updateUrl(): void {
    const url = new URL(window.location.href);
    url.searchParams.set('year', String(selectedYear));
    if (selected?.sourceRole === 'reviewed' && selected.featureId) url.searchParams.set('feature', selected.featureId);
    else url.searchParams.delete('feature');
    if (selected?.entityId) url.searchParams.set('entity', selected.entityId);
    else url.searchParams.delete('entity');
    if (activeLens === 'all') url.searchParams.delete('lens');
    else url.searchParams.set('lens', activeLens);
    replaceState(url, {});
  }

  function updateMapYear(): void {
    if (!map) return;
    applyMapYearPresentation(map, selectedYear, activeLens, evidenceOverlay);
    updateThemeDiscoveryLayer();
    updateCoverageLayer();
  }

  function applyLayerMode(): void {
    if (!map) return;
    detailLimitReached = applyLayerModePresentation(map, layerMode, activeLens);
  }

  function setLayerMode(mode: HistoricalLayerMode): void {
    layerMode = mode;
    applyLayerMode();
    const description = {
      combined: 'OpenHistoricalMap detail with reviewed reconstructions.',
      'historical-detail': 'OpenHistoricalMap contributor detail only.',
      reviewed: 'Reviewed reconstructions over neutral physical geography.'
    }[mode];
    mapAnnouncement = `Map layers changed. ${description}`;
  }

  function setLens(lens: HistoricalLens): void {
    if (lens === activeLens) return;
    activeLens = lens;
    if (selected) clearSelection();
    else updateUrl();
    updateMapYear();
    applyLayerMode();
    const definition = lensDefinition(lens);
    const classifiedCount = searchIndex.filter(
      (record) =>
        record.valid_from <= selectedYear &&
        record.valid_to >= selectedYear &&
        recordMatchesLens(record, lens)
    ).length;
    mapAnnouncement = `${definition.label} lens selected. ${definition.description} ${
      lens === 'all'
        ? ''
        : classifiedCount
          ? `${classifiedCount} release records are classified at ${formatYear(selectedYear)}.`
          : `No release records are classified at ${formatYear(selectedYear)}.`
    }`;
    void updateSearchResults();
  }

  function setEvidenceOverlay(overlay: 'none' | 'confidence' | 'provenance'): void {
    evidenceOverlay = overlay;
    updateMapYear();
    mapAnnouncement = overlay === 'none'
      ? 'Evidence overlay off.'
      : `${overlay === 'confidence' ? 'Interpretive confidence' : 'Source provenance'} overlay selected. The active historical lens remains unchanged.`;
  }

  function removeHistoricalMapLayer(): void {
    if (map?.getLayer(HISTORICAL_MAP_IMAGE_LAYER)) {
      map.removeLayer(HISTORICAL_MAP_IMAGE_LAYER);
    }
    if (map?.getSource(HISTORICAL_MAP_IMAGE_SOURCE)) {
      map.removeSource(HISTORICAL_MAP_IMAGE_SOURCE);
    }
    if (historicalMapObjectUrl) {
      URL.revokeObjectURL(historicalMapObjectUrl);
      historicalMapObjectUrl = null;
    }
  }

  async function updateHistoricalMapOverlay(): Promise<void> {
    const request = ++historicalMapRequest;
    removeHistoricalMapLayer();
    historicalMapError = '';
    if (!historicalMapVisible || !activeHistoricalMap || !release || !mapReady || !map) {
      historicalMapLoading = false;
      return;
    }
    historicalMapLoading = true;
    try {
      const bytes = await loadHistoricalMapImage(release, activeHistoricalMap);
      if (
        request !== historicalMapRequest ||
        !historicalMapVisible ||
        !activeHistoricalMap.rendering ||
        !map
      ) {
        return;
      }
      const imageArtifact = artifact(release, activeHistoricalMap.rendering.image_path);
      const objectUrl = URL.createObjectURL(
        new Blob([bytes], { type: imageArtifact?.media_type ?? 'image/png' })
      );
      historicalMapObjectUrl = objectUrl;
      map.addSource(HISTORICAL_MAP_IMAGE_SOURCE, {
        type: 'image',
        url: objectUrl,
        coordinates: activeHistoricalMap.rendering.coordinates
      });
      map.addLayer(
        {
          id: HISTORICAL_MAP_IMAGE_LAYER,
          type: 'raster',
          source: HISTORICAL_MAP_IMAGE_SOURCE,
          paint: { 'raster-opacity': 0.68, 'raster-fade-duration': 0 }
        },
        map.getLayer(FIRST_OHM_LABEL_LAYER) ? FIRST_OHM_LABEL_LAYER : undefined
      );
      mapAnnouncement = `${activeHistoricalMap.label} historical map image enabled. It is a source depiction, not authoritative geography.`;
    } catch (error) {
      historicalMapVisible = false;
      historicalMapError = error instanceof Error
        ? error.message
        : 'The approved historical map image could not be loaded.';
      removeHistoricalMapLayer();
    } finally {
      if (request === historicalMapRequest) historicalMapLoading = false;
    }
  }

  function toggleHistoricalMap(): void {
    historicalMapVisible = !historicalMapVisible;
    void updateHistoricalMapOverlay();
    if (!historicalMapVisible) {
      mapAnnouncement = 'Historical map image off.';
    }
  }

  function selectHistoricalMap(mapId: string): void {
    selectedHistoricalMapId = mapId;
    if (historicalMapVisible) void updateHistoricalMapOverlay();
  }

  function setYear(candidate: number): void {
    const next = normalizeYear(candidate, selectedYear);
    const nextEra = eraForYear(next);
    selectedYear = next;
    void updateSearchTimeBand(next);
    if (selected?.sourceRole === 'reviewed') {
      const record = searchIndex.find((item) =>
        item.entity_id === selected?.entityId || item.feature_ids.includes(selected?.featureId ?? '')
      );
      const attestation = record ? nameForYear(record, next) : null;
      if (record && attestation) {
        if (attestation.feature_id !== selected.featureId) {
          setSelection(selectionFromSearch(record, next));
        } else {
          selected = { ...selected, name: attestation.text, nameAttestation: attestation };
        }
      }
    } else if (
      selected?.sourceRole === 'ohm' && selected.ohm?.datesComplete &&
      (next < selected.validFrom || next > selected.validTo)
    ) {
      clearSelection();
    }
    updateUrl();
    mapAnnouncement = `Map updated to ${formatYear(next)}. Shapes are source snapshots; boundaries are not interpolated.`;
    if (map) updateOhmYear(map, next, activeLens);
    if (selected?.sourceRole === 'reviewed') void refreshChronology(selected);
    else if (selected?.sourceRole === 'ohm') void refreshRegionalContext(selected);

    if (nextEra !== activeEra) {
      activeEra = nextEra;
      void loadEra(nextEra);
    } else {
      updateMapYear();
    }
  }

  function togglePlayback(): void {
    playing = !playing;
    if (!playing) {
      stopPlayback();
      return;
    }
    playTimer = setInterval(() => {
      if (selectedYear >= MAXIMUM_YEAR) {
        playing = false;
        stopPlayback();
        return;
      }
      setYear(stepYear(selectedYear, selectedYear < 1500 ? 25 : selectedYear < 1900 ? 10 : 1));
    }, reducedMotion ? 1000 : 520);
  }

  function stopPlayback(): void {
    if (playTimer) clearInterval(playTimer);
    playTimer = null;
  }

  function chooseSearchResult(record: SearchRecord): void {
    const year = availableYearForRecord(record, selectedYear);
    setYear(year);
    setSelection(selectionFromSearch(record, year));
    map?.flyTo({
      center: [record.longitude, record.latitude],
      zoom: Math.max(map.getZoom(), 4.1),
      duration: reducedMotion ? 0 : 900
    });
    searchQuery = displayName(record);
  }

  function setSelection(next: Selection): void {
    if (selectedFeatureStateId && map?.getSource(MAP_SOURCE)) {
      map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: selectedFeatureStateId }, { selected: false });
    }
    selected = next;
    selectedFeatureStateId = next.sourceRole === 'reviewed' ? next.featureId || null : null;
    if (selectedFeatureStateId && map?.getSource(MAP_SOURCE)) {
      map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: selectedFeatureStateId }, { selected: true });
    }
    updateUrl();
    updateMapPadding(true);
    void resolveSelectionContent(next);
    void hydrateSelectedSearchRecord(next);
  }

  async function hydrateSelectedSearchRecord(selection: Selection): Promise<void> {
    if (!release || !staticSearchIndex || selection.sourceRole !== 'reviewed') return;
    const record = await loadSearchRecord(release, staticSearchIndex, {
      entityId: selection.entityId,
      featureId: selection.featureId
    });
    if (!record) return;
    mergeSearchRecords([record]);
    if (selected?.featureId !== selection.featureId) return;
    const attestation =
      nameForYear(record, selectedYear, selection.featureId) ??
      nameForYear(record, selectedYear) ??
      undefined;
    selected = {
      ...selected,
      name: attestation?.text ?? selected.name,
      nameAttestation: attestation,
      longitude: selected.longitude ?? record.longitude,
      latitude: selected.latitude ?? record.latitude
    };
  }

  function setHoveredFeature(featureId: string | null): void {
    if (!map?.getSource(MAP_SOURCE) || hoveredFeatureStateId === featureId) return;
    if (hoveredFeatureStateId) {
      map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: hoveredFeatureStateId }, { hover: false });
    }
    hoveredFeatureStateId = featureId;
    if (hoveredFeatureStateId) {
      map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: hoveredFeatureStateId }, { hover: true });
    }
  }

  function refreshSelectionFromMap(): void {
    if (!map || selected?.sourceRole !== 'reviewed' || !selected.featureId || !map.getSource(MAP_SOURCE)) return;
    const match = map.querySourceFeatures(MAP_SOURCE, {
      sourceLayer: 'history',
      filter: ['==', ['get', 'feature_id'], selected.featureId] as never
    })[0];
    if (!match) return;
    const mapped = selectionFromFeature(match);
    selected = {
      ...mapped,
      entityId: mapped.entityId ?? selected.entityId,
      contentShard: mapped.contentShard ?? selected.contentShard,
      longitude: selected.longitude ?? mapped.longitude,
      latitude: selected.latitude ?? mapped.latitude
    };
  }

  function clearSelection(): void {
    if (selectedFeatureStateId && map?.getSource(MAP_SOURCE)) {
      map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: selectedFeatureStateId }, { selected: false });
    }
    selected = null;
    selectedEntity = null;
    linkedEntities = [];
    selectedDossiers = [];
    selectedRestatements = new Map();
    selectedLink = null;
    selectedCausalClaims = [];
    selectedCausalPaths = [];
    selectedPeriods = [];
    selectedWikiContext = null;
    selectedRegionalContext = null;
    selectedThematicAssertions = [];
    selectedEvidenceAssertions = [];
    selectedFeatureStateId = null;
    contentError = '';
    updateUrl();
    updateMapPadding(false);
  }

  // Keep the selected geometry inside the map's visible window rather than under the
  // reading surface. The view panel deliberately does not shift the map: it is a global
  // control, not a response to a particular feature, so moving the world under it would
  // be motion the reader did not ask for.
  function updateMapPadding(reading: boolean): void {
    if (!map || window.innerWidth < 861) return;
    const readerPadding = window.innerWidth < 1180 ? 392 : 452;
    map.easeTo({
      padding: { top: 0, bottom: 0, left: 0, right: reading ? readerPadding : 0 },
      duration: reducedMotion ? 0 : 320
    });
  }

  function toggleViewPanel(): void {
    viewOpen = !viewOpen;
  }

  function openSearch(): void {
    searchOverlay?.focusSearch();
  }

  async function resolveSelectionContent(selection: Selection): Promise<void> {
    selectedEntity = null;
    linkedEntities = [];
    selectedDossiers = [];
    selectedRestatements = new Map();
    selectedLink = null;
    selectedCausalClaims = [];
    selectedCausalPaths = [];
    selectedPeriods = [];
    selectedWikiContext = null;
    selectedRegionalContext = null;
    selectedThematicAssertions = [];
    selectedEvidenceAssertions = [];
    contentError = '';
    if (selection.sourceRole === 'ohm') {
      if (release) {
        contentLoading = true;
        try {
          selectedRegionalContext = await loadRegionalContextForSelection(
            release,
            selection
          );
        } catch {
          selectedRegionalContext = null;
        }
      }
      contentLoading = false;
      return;
    }
    if (!release) return;
    contentLoading = true;
    try {
      if (release.manifest.content_index_path) {
        const content = await loadFeatureContent(release, selection.featureId, selection.contentShard);
        if (selected?.featureId !== selection.featureId) return;
        selectedLink = content?.link ?? null;
        linkedEntities = content?.entities ?? [];
        selectedEntity = linkedEntities.find((entity) =>
          entity.entity_id === content?.link.primary_entity_id ||
          entity.entity_id === selection.entityId ||
          entity.wikidata_id === selection.wikidataId
        ) ?? linkedEntities[0] ?? null;
        selectedDossiers = content?.dossiers ?? [];
        selectedRestatements = content?.restatements ?? new Map();
        const entityIds = content?.link.entity_ids ?? [
          selection.entityId,
          selection.wikidataId ? `wikidata:${selection.wikidataId}` : undefined
        ].filter(Boolean) as string[];
        // Core reading material is ready. Optional historical context continues
        // below without keeping the sidebar behind a loading state.
        contentLoading = false;
        const supplement = await loadSelectionSupplement(
          release,
          selection,
          entityIds,
          selectedYear
        );
        if (selected?.featureId !== selection.featureId) return;
        selectedCausalClaims = supplement.causalClaims;
        selectedCausalPaths = supplement.causalPaths;
        selectedPeriods = supplement.periods;
        selectedWikiContext = supplement.wikiContext;
        selectedRegionalContext = supplement.regionalContext;
        selectedThematicAssertions = supplement.thematicAssertions;
        selectedEvidenceAssertions = supplement.evidenceAssertions;
        return;
      }
      contentPromise ??= loadContentBundle(release);
      const bundle = await contentPromise;
      if (selected?.featureId !== selection.featureId) return;
      const link = bundle.featureLinks.get(selection.featureId) ?? null;
      const entityCandidates = [
        ...(link?.entity_ids ?? []),
        selection.entityId,
        selection.wikidataId,
        selection.wikidataId ? `wikidata:${selection.wikidataId}` : undefined
      ].filter(Boolean) as string[];
      selectedLink = link;
      selectedEntity = entityCandidates.map((id) => bundle.entities.get(id)).find(Boolean) ?? null;
      linkedEntities = selectedEntity ? [selectedEntity] : [];
      selectedDossiers = (link?.dossier_ids ?? [])
        .map((id) => bundle.dossiers.get(id))
        .filter((item): item is HistoricalDossier => Boolean(item));
      const supplement = await loadSelectionSupplement(
        release,
        selection,
        entityCandidates,
        selectedYear
      );
      if (selected?.featureId !== selection.featureId) return;
      selectedCausalClaims = supplement.causalClaims;
      selectedCausalPaths = supplement.causalPaths;
      selectedPeriods = supplement.periods;
      selectedWikiContext = supplement.wikiContext;
      selectedRegionalContext = supplement.regionalContext;
      selectedThematicAssertions = supplement.thematicAssertions;
      selectedEvidenceAssertions = supplement.evidenceAssertions;
    } catch (error) {
      contentError = error instanceof Error ? error.message : 'The reading material could not be loaded.';
    } finally {
      contentLoading = false;
    }
  }

  async function refreshChronology(selection: Selection): Promise<void> {
    if (!release) return;
    const entityIds = selectedLink?.entity_ids ?? [
      selection.entityId,
      selection.wikidataId ? `wikidata:${selection.wikidataId}` : undefined
    ].filter(Boolean) as string[];
    try {
      const [periods, wikiContext, regionalContext] = await Promise.all([
        loadChronologyContext(release, entityIds, selectedYear),
        loadWikiContext(release, selection.featureId, selectedYear),
        loadRegionalContextForSelection(release, selection)
      ]);
      if (selected?.featureId === selection.featureId) {
        selectedPeriods = periods;
        selectedWikiContext = wikiContext;
        selectedRegionalContext = regionalContext;
      }
    } catch {
      // The main content request surfaces verified-artifact failures; timeline scrubbing stays usable.
    }
  }

  async function refreshRegionalContext(selection: Selection): Promise<void> {
    if (!release) return;
    try {
      const regionalContext = await loadRegionalContextForSelection(release, selection);
      if (selected?.featureId === selection.featureId) {
        selectedRegionalContext = regionalContext;
      }
    } catch {
      // Live OHM reading remains usable if an optional immutable context shard fails.
    }
  }

  function sourceForFeature(selection: Selection): SourceReference | null {
    if (selection.sourceReference) return selection.sourceReference;
    const sourceId = selection.sourceId ?? selection.featureId.split(':')[0];
    return release?.manifest.sources.find((source) => source.source_id === sourceId) ?? null;
  }

  function loadRegionalContextForSelection(
    loadedRelease: LoadedRelease,
    selection: Selection
  ): Promise<SelectedRegionalContext | null> {
    if (selection.longitude === undefined || selection.latitude === undefined) {
      return Promise.resolve(null);
    }
    return loadRegionalContext(
      loadedRelease,
      selection.longitude,
      selection.latitude,
      selectedYear,
      selection.featureId
    );
  }

  function elsewhereAtThisTime(selection: Selection): SearchRecord[] {
    const candidates = searchIndex.filter((record) =>
      (record.name_attestations?.length
        ? Boolean(nameForYear(record, selectedYear))
        : record.valid_from <= selectedYear && record.valid_to >= selectedYear) &&
      !record.feature_ids.includes(selection.featureId) && record.entity_id !== selection.entityId
    );
    const origin = candidates.find((record) => displayName(record) === selection.name)?.longitude ?? 0;
    const chosen: SearchRecord[] = [];
    for (const offset of [90, 180, 270]) {
      const target = ((origin + offset + 540) % 360) - 180;
      const next = candidates
        .filter((record) => !chosen.includes(record))
        .sort((a, b) => angularDistance(a.longitude, target) - angularDistance(b.longitude, target))[0];
      if (next) chosen.push(next);
    }
    return chosen;
  }

  function angularDistance(left: number, right: number): number {
    const difference = Math.abs(left - right) % 360;
    return Math.min(difference, 360 - difference);
  }

  function coverageGapsForYear(year: number): FeatureCollection<Polygon> {
    const features: FeatureCollection<Polygon>['features'] = [];
    for (let longitude = -180; longitude < 180; longitude += 30) {
      for (let latitude = -60; latitude < 90; latitude += 30) {
        const covered = coverage.some((cell) =>
          cell.bounds[0] === longitude && cell.bounds[1] === latitude &&
          cell.valid_from <= year && cell.valid_to >= year && cell.feature_count > 0
        );
        if (!covered) {
          features.push({
            type: 'Feature',
            properties: { coverage: 'missing' },
            geometry: {
              type: 'Polygon',
              coordinates: [[[longitude, latitude], [longitude + 30, latitude], [longitude + 30, latitude + 30], [longitude, latitude + 30], [longitude, latitude]]]
            }
          });
        }
      }
    }
    return { type: 'FeatureCollection', features };
  }

  function updateCoverageLayer(): void {
    const source = map?.getSource(COVERAGE_SOURCE) as GeoJSONSource | undefined;
    if (source) source.setData(coverageGapsForYear(selectedYear));
  }

  function themeDiscoveryPoints(): FeatureCollection<Point> {
    if (activeLens === 'all') return { type: 'FeatureCollection', features: [] };
    return {
      type: 'FeatureCollection',
      features: searchIndex
        .filter(
          (record) =>
            record.valid_from <= selectedYear &&
            record.valid_to >= selectedYear &&
            recordMatchesLens(record, activeLens)
        )
        .map((record) => ({
          type: 'Feature' as const,
          id: record.entity_id,
          properties: {
            feature_id: record.feature_ids[0],
            primary_entity_id: record.entity_id,
            name: displayNameForYear(record, selectedYear),
            kind: record.kind,
            themes: record.themes ?? [],
            valid_from: record.valid_from,
            valid_to: record.valid_to,
            spatial_meaning: 'location',
            review_status: 'provisional',
            source_id: record.source_ids?.[0]
          },
          geometry: {
            type: 'Point' as const,
            coordinates: [record.longitude, record.latitude]
          }
        }))
    };
  }

  function updateThemeDiscoveryLayer(): void {
    const source = map?.getSource(THEME_DISCOVERY_SOURCE) as GeoJSONSource | undefined;
    if (source) source.setData(themeDiscoveryPoints());
  }

  async function loadEra(era: Era): Promise<void> {
    if (!map || !release || !mapReady) return;
    loadingEra = true;
    try {
      setHoveredFeature(null);
      for (const layer of HISTORY_LAYERS) if (map.getLayer(layer)) map.removeLayer(layer);
      if (map.getSource(MAP_SOURCE)) map.removeSource(MAP_SOURCE);

      const tilePath = `tiles/${era}.pmtiles`;
      // eraLabel is prefixed "Archive · ", which read as "no archive · 1500–1799 map archive".
      if (!artifact(release, tilePath)) {
        throw new Error(`This release has no map archive for ${eraLabel(era).replace('Archive · ', '')}.`);
      }
      const absoluteTileUrl = new URL(artifactUrl(release, tilePath), window.location.href).href;
      const beforeLabels = map.getLayer(FIRST_OHM_LABEL_LAYER) ? FIRST_OHM_LABEL_LAYER : undefined;
      installReviewedHistoryLayers(map, {
        sourceUrl: `pmtiles://${absoluteTileUrl}`,
        themeDiscoveryData: themeDiscoveryPoints(),
        beforeLayerId: beforeLabels,
        year: selectedYear,
        lens: activeLens,
        evidenceOverlay,
        selectedFeatureId: selectedFeatureStateId
      });
      applyLayerMode();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Could not load this historical layer.';
    } finally {
      loadingEra = false;
    }
  }

  async function openAbout(): Promise<void> {
    aboutDialog?.open();
    if (!release || quality || attributions) return;
    const qualityPromise = release.manifest.quality_path
      ? loadJsonArtifact<QualityReport>(release, release.manifest.quality_path)
      : Promise.resolve(null);
    const attributionPromise = loadJsonArtifact<AttributionReport>(release, release.manifest.attribution_path);
    [quality, attributions] = await Promise.all([qualityPromise, attributionPromise]);
  }

  async function restoreLinkedSelection(): Promise<void> {
    const url = new URL(window.location.href);
    const entityId = url.searchParams.get('entity');
    const featureId = url.searchParams.get('feature');
    let record = searchIndex.find((item) =>
      (entityId && item.entity_id === entityId) || (featureId && item.feature_ids.includes(featureId))
    );
    if (!record && release && staticSearchIndex && (entityId || featureId)) {
      record = (await loadSearchRecord(release, staticSearchIndex, { entityId, featureId })) ?? undefined;
      if (record) mergeSearchRecords([record]);
    }
    if (record) {
      linkedRecordToRestore = record;
      const year = availableYearForRecord(record, selectedYear);
      if (year !== selectedYear) {
        selectedYear = year;
        activeEra = eraForYear(year);
      }
      searchQuery = displayNameForYear(record, year);
      setSelection(selectionFromSearch(record, year));
      map?.jumpTo({ center: [record.longitude, record.latitude], zoom: 4.1 });
    }
  }

  async function initialise(): Promise<void> {
    try {
      reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const queryYear = Number(new URL(window.location.href).searchParams.get('year'));
      const queryLens = new URL(window.location.href).searchParams.get('lens');
      if (Number.isFinite(queryYear) && queryYear !== 0) selectedYear = normalizeYear(queryYear);
      if (isHistoricalLens(queryLens)) activeLens = queryLens;
      activeEra = eraForYear(selectedYear);
      release = await loadRelease(DATA_BASE);

      staticSearchIndex = await loadStaticSearchIndex(release);
      // A year page is offered only when the release actually carries one; the index is
      // one small fetch and answers that without probing for a file.
      void loadYearIndex(release).then((index) => {
        yearsWithDossier = availableYears(index);
      });
      const layerCatalogPromise = loadLayerCatalog(release).then((catalog) => {
        layerCatalog = catalog;
      });
      const historicalMapsPromise = loadHistoricalMaps(release).then((maps) => {
        historicalMaps = maps;
        selectedHistoricalMapId = maps[0]?.map_id ?? '';
      }).catch((error: unknown) => {
        historicalMaps = [];
        historicalMapError = error instanceof Error
          ? error.message
          : 'Historical map release metadata could not be loaded.';
      });
      const authorityMatchesPromise = loadAuthorityMatches(release)
        .then((matches) => {
          authorityMatches = matches;
        })
        .catch(() => {
          // Authority links are optional context. A malformed optional artifact must
          // not prevent the independently verified map release from opening.
          authorityMatches = [];
        });
      const searchArtifact = artifact(release, 'search.ndjson');
      const searchPromise = staticSearchIndex
        ? loadSearchTimeBand(release, staticSearchIndex, selectedYear).then(async (records) => {
            searchIndex = records;
            updateThemeDiscoveryLayer();
            await restoreLinkedSelection();
          })
        : searchArtifact
          ? loadSearchIndex(release, searchArtifact.path).then(async (records) => {
              searchIndex = records;
              updateThemeDiscoveryLayer();
              await restoreLinkedSelection();
            })
          : Promise.resolve();
      const coveragePromise = loadJsonArtifact<CoverageCell[]>(release, release.manifest.coverage_path).then((cells) => {
        coverage = cells;
        updateCoverageLayer();
      });

      const [{ default: maplibregl }, { Protocol }] = await Promise.all([import('maplibre-gl'), import('pmtiles')]);
      // Reading embedded metadata avoids the PMTiles adapter's invalid-bounds warning for a
      // truthful single-point archive; the point coordinates themselves remain unchanged.
      pmtilesProtocol = new Protocol({ metadata: true });
      maplibregl.addProtocol('pmtiles', pmtilesProtocol.tile);
      map = new maplibregl.Map({
        container: mapContainer,
        center: [17, 25],
        zoom: 1.7,
        minZoom: 1,
        maxZoom: 18,
        renderWorldCopies: false,
        attributionControl: false,
        fadeDuration: reducedMotion ? 0 : 180,
        // Bootstrap with the complete, stable base style. Apply a thematic lens only
        // after MapLibre has loaded it so an empty lens cannot suppress physical geography.
        style: historyMapStyle(selectedYear)
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
      map.on('load', () => {
        mapReady = true;
        updateOhmYear(map!, selectedYear, activeLens);
        applyLayerMode();
        if (historicalMapVisible) void updateHistoricalMapOverlay();
        const pixels = new Uint8Array(12 * 12 * 4);
        for (const [x, y] of [[2, 2], [8, 8]]) {
          const offset = (y * 12 + x) * 4;
          pixels[offset] = 61;
          pixels[offset + 1] = 72;
          pixels[offset + 2] = 64;
          pixels[offset + 3] = 42;
        }
        map?.addImage('coverage-hatch', { width: 12, height: 12, data: pixels });
        map?.addSource(COVERAGE_SOURCE, { type: 'geojson', data: coverageGapsForYear(selectedYear) });
        map?.addLayer({
          id: COVERAGE_FILL_LAYER,
          type: 'fill',
          source: COVERAGE_SOURCE,
          paint: { 'fill-pattern': 'coverage-hatch', 'fill-opacity': 0.72 }
        }, FIRST_OHM_LABEL_LAYER);
        map?.addLayer({
          id: COVERAGE_EDGE_LAYER,
          type: 'line',
          source: COVERAGE_SOURCE,
          paint: { 'line-color': '#4c5552', 'line-opacity': 0.12, 'line-width': 0.5, 'line-dasharray': [2, 3] }
        }, FIRST_OHM_LABEL_LAYER);
        void loadEra(activeEra);
        if (linkedRecordToRestore) {
          map?.jumpTo({ center: [linkedRecordToRestore.longitude, linkedRecordToRestore.latitude], zoom: 4.1 });
        }
      });
      removeMapInteractions = bindMapInteractions(map, {
        onReviewedFeature: (feature, longitude, latitude) => {
          setSelection(selectionFromFeature(feature, longitude, latitude));
        },
        onOhmFeature: (feature, longitude, latitude) => {
          setSelection(selectionFromOhmFeature(feature, longitude, latitude));
        },
        onHoveredFeature: setHoveredFeature,
        onDetailLimitChange: (reached) => (detailLimitReached = reached),
        onReviewedSourceLoaded: refreshSelectionFromMap,
        onResize: () => updateMapPadding(Boolean(selected)),
        reviewedDetailVisible: () => layerMode !== 'historical-detail'
      });
      await Promise.allSettled([
        searchPromise,
        coveragePromise,
        layerCatalogPromise,
        historicalMapsPromise,
        authorityMatchesPromise
      ]);
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'The historical map could not start.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void initialise();
    return () => {
      stopPlayback();
      removeMapInteractions?.();
      removeMapInteractions = null;
      historicalMapRequest += 1;
      removeHistoricalMapLayer();
      map?.remove();
      pmtilesProtocol = null;
    };
  });
</script>

<svelte:head>
  <title>Palimpsest — A world history map</title>
  <meta name="description" content="Read historical geography across more than five thousand years, with its sources and uncertainties intact." />
</svelte:head>

<a class="skip-link" href="#timeline">Skip to timeline controls</a>

<main class:reading={selected} class="app-shell">
  <div
    class="map"
    bind:this={mapContainer}
    data-historical-map-overlay={historicalMapVisible ? selectedHistoricalMapId : 'off'}
    aria-label={`Interactive historical world map for ${formatYear(selectedYear)}`}
  ></div>

  <InstrumentRail
    {activeLens}
    {selectedYear}
    {lensCounts}
    {viewOpen}
    {searchOpen}
    onLensSelect={setLens}
    onSearchOpen={openSearch}
    onViewToggle={toggleViewPanel}
    onAbout={openAbout}
  />

  <ViewPanel
    open={viewOpen}
    {selectedYear}
    {activeEra}
    {loadingEra}
    {layerMode}
    {evidenceOverlay}
    layerCatalogReady={Boolean(layerCatalog)}
    {historicalMaps}
    {selectedHistoricalMapId}
    {historicalMapVisible}
    {historicalMapLoading}
    {historicalMapError}
    {activeHistoricalMap}
    onClose={toggleViewPanel}
    onLayerModeSelect={setLayerMode}
    onEvidenceOverlaySelect={setEvidenceOverlay}
    onHistoricalMapSelect={selectHistoricalMap}
    onHistoricalMapToggle={toggleHistoricalMap}
  />

  <SearchOverlay
    bind:this={searchOverlay}
    bind:open={searchOpen}
    bind:query={searchQuery}
    results={searchResults}
    {selectedYear}
    onQueryChange={updateSearchResults}
    onResultSelect={chooseSearchResult}
  />

  <div class="map-key" aria-label="Map key">
    {#if evidenceOverlay !== 'none'}
      <span><i class="overlay"></i>{evidenceOverlay === 'confidence' ? 'Confidence' : 'Provenance'}</span>
    {/if}
    {#if activeLens !== 'all'}
      <span><i class="theme" style={`--lens-accent: ${lensAccent(activeLens)}`}></i><LensMark lens={activeLens} size={12} /> In lens</span>
    {:else}
      <span><i class="control"></i>Control</span>
    {/if}
    <span><i class="soft"></i>Approximate</span>
    <span><i class="gap"></i>No coverage</span>
  </div>

  {#if detailLimitReached}<p class="detail-limit" role="status">Reviewed geometry stops at zoom 7 · contributor detail continues</p>{/if}

  {#if selected}
    <aside class="reading-surface" id="reading-surface" aria-labelledby="record-title" tabindex="-1">
      <RecordIdentityHeader
        name={selected.name}
        kindLabel={selected.sourceRole === 'ohm' ? 'OpenHistoricalMap detail' : humanize(selected.kind)}
        {alternateNames}
        onClose={clearSelection}
      />

      <div class="record-scroll">
        <div class="record-dates">
          <time class="hj-numeral">{selected.dateLabel ?? formatRange(selected.validFrom, selected.validTo)}</time>
          <span>{humanize(selected.reviewStatus)}</span>
        </div>

        {#if selected.sourceRole === 'reviewed'}
          <RecordStructuredFacts
            assertions={selectedPrimaryEligibility?.identity_relation === 'broader_topic'
              ? []
              : selectedEvidenceAssertions}
            {linkedEntities}
            {selectedYear}
          />
          {#if dossierYear !== null && selected.yearDossierYears?.includes(dossierYear)}
            <section class="hj-section year-thread" aria-label={`Continue into ${formatYear(dossierYear)}`}>
              <p class="hj-section-label">Continue the year</p>
              <p class="hj-note">This mapped event has an explicit editorial link to the {formatYear(dossierYear)} dossier.</p>
              <a class="hj-link" href={`/year?year=${dossierYear}`}>Read the {formatYear(dossierYear)} treatment <span aria-hidden="true">→</span></a>
            </section>
          {/if}
          <RecordAuthorityConnections matches={selectedAuthorityMatches} />
        {/if}

        <RecordPrimaryReading
          selection={selected}
          {selectedYear}
          entity={selectedEntity}
          dossiers={selectedDossiers}
          restatements={selectedRestatements}
          link={selectedLink}
          loading={contentLoading}
          error={contentError}
        />

        <RecordInterpretiveContext
          wikiContext={selectedWikiContext}
          periods={selectedPeriods}
          causalClaims={selectedCausalClaims}
          causalPaths={selectedCausalPaths}
          {selectedYear}
        />

        {#if selected.sourceRole === 'reviewed'}
          <details class="record-apparatus-group">
            <summary>Classification, confidence and provenance</summary>
            <RecordThematicReading
              {activeLens}
              lens={activeLensDefinition}
              assertions={visibleThematicAssertions}
              reviewed={true}
              {contentLoading}
            />
            <RecordEvidence
              temporalConfidence={selected.temporalConfidence}
              spatialConfidence={selected.spatialConfidence}
              interpretiveConfidence={selected.interpretiveConfidence}
              disputeGroup={selected.disputeGroup}
              source={selectedSource}
            />
          </details>
        {/if}

        <RecordDiscoverySections
          relationships={selectedRelationships}
          {linkedEntities}
          {searchIndex}
          regionalContext={selectedRegionalContext}
          {elsewhere}
          {selectedYear}
          onRecordSelect={chooseSearchResult}
        />

        {#if selected.sourceRole === 'reviewed'}
          <a class="text-record-link" href={`/browse?year=${selectedYear}&entity=${encodeURIComponent(selected.entityId ?? '')}&q=${encodeURIComponent(selected.name)}${activeLens !== 'all' ? `&lens=${activeLens}` : ''}`}>Open this record in the text view <span aria-hidden="true">→</span></a>
        {/if}
      </div>
    </aside>
  {/if}

  {#if loading}<div class="loading-state"><span></span><p>Opening release data</p></div>{/if}
  {#if errorMessage}
    <div class="error-toast" role="alert">
      <div><strong>Map unavailable</strong><p>{errorMessage}</p></div>
      <button onclick={() => (errorMessage = '')} aria-label="Dismiss error">×</button>
    </div>
  {/if}

  <HistoricalTimeline
    {selectedYear}
    {playing}
    {coverage}
    {dossierYear}
    onYearSelect={setYear}
    onPlaybackToggle={togglePlayback}
  />

  <p class="hj-sr-only" aria-live="polite">{mapAnnouncement}</p>

  <ProjectAboutDialog bind:this={aboutDialog} {release} {quality} {attributions} />
</main>

<svelte:window onkeydown={(event) => {
  if (event.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'SELECT' && document.activeElement?.tagName !== 'TEXTAREA') {
    event.preventDefault();
    openSearch();
  }
}} />


<style>
  /* The map is the only illuminated object. Every control recedes into slate so the
     cartography reads as the lit surface of an instrument rather than as one more
     panel competing with five others. */
  :global(html), :global(body) { width: 100%; height: 100%; overflow: hidden; }
  :global(.maplibregl-ctrl-bottom-right) { right: 14px; bottom: calc(var(--timeline-height) + 12px); }
  :global(.maplibregl-ctrl-group) {
    overflow: hidden;
    border: 1px solid var(--line-strong);
    border-radius: 0;
    background: var(--surface);
    box-shadow: 0 2px 8px rgb(20 23 42 / 0.08);
  }
  :global(.maplibregl-ctrl-group button) { width: 30px; height: 30px; background-color: var(--surface); }
  :global(.maplibregl-ctrl-group button + button) { border-top: 1px solid var(--line); }
  :global(.maplibregl-ctrl-group button:hover) { background-color: var(--accent-soft); }
  :global(.maplibregl-ctrl-attrib) { display: none; }

  .skip-link {
    position: fixed;
    z-index: 100;
    top: var(--s-2);
    left: var(--s-2);
    padding: var(--s-3) var(--s-4);
    transform: translateY(-160%);
    background: var(--accent);
    color: #fff;
    font-size: var(--t-sm);
    font-weight: 600;
    text-decoration: none;
  }
  .skip-link:focus { transform: none; }

  .app-shell { position: relative; width: 100vw; height: 100dvh; overflow: hidden; background: var(--bg); }
  .map { border-left: 1px solid var(--line-strong); }

  .map { position: absolute; inset: 0 0 var(--timeline-height) var(--rail-width); }

  /* A single quiet key rather than six floating cards. */
  .map-key {
    position: absolute;
    z-index: 4;
    right: var(--s-4);
    bottom: calc(var(--timeline-height) + var(--s-3));
    display: flex;
    gap: var(--s-4);
    padding: 7px var(--s-3);
    border: 1px solid var(--line-strong);
    background: rgb(255 255 255 / 0.92);
    color: var(--text-dim);
    font-size: var(--t-xs);
    box-shadow: 0 2px 10px rgb(20 23 42 / 0.06);
    backdrop-filter: blur(6px);
  }
  .reading .map-key { right: calc(var(--reader-width) + var(--s-4)); }
  .map-key span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
  .map-key i { display: inline-block; flex: none; width: 18px; height: 9px; }
  .map-key .overlay { background: linear-gradient(90deg, var(--conf-a), var(--conf-c), var(--conf-d)); }
  .map-key .control { border: 1px solid var(--text-dim); background: rgb(84 91 115 / 0.12); }
  .map-key .theme { border: 2px solid var(--accent); background: var(--accent-soft); }
  .map-key .soft { border: 1px dashed var(--text-faint); background: rgb(84 91 115 / 0.06); }
  .map-key .gap { opacity: 0.9; background-image: radial-gradient(circle, var(--text-faint) 0.9px, transparent 1px); background-size: 6px 6px; }

  .detail-limit {
    position: absolute;
    z-index: 5;
    top: var(--s-3);
    right: var(--s-4);
    margin: 0;
    padding: 6px var(--s-3);
    border: 1px solid var(--line-strong);
    background: rgb(255 255 255 / 0.92);
    color: var(--text-dim);
    font-size: var(--t-xs);
    box-shadow: 0 2px 10px rgb(20 23 42 / 0.06);
    backdrop-filter: blur(6px);
  }
  .reading .detail-limit { right: calc(var(--reader-width) + var(--s-4)); }

  /* The reading surface: the one bright paper object, set against the slate. */
  .reading-surface {
    position: absolute;
    z-index: 9;
    inset: 0 0 var(--timeline-height) auto;
    width: var(--reader-width);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-left: 1px solid var(--line-strong);
    background: var(--surface);
    color: var(--text);
    box-shadow: -18px 0 44px rgb(20 23 42 / 0.07);
  }

  .record-scroll {
    min-height: 0;
    flex: 1 1 auto;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: var(--line-strong) transparent;
    /* The previous panel hard-clipped its last paragraph mid-sentence against the
       timeline. The surface now stops above it and the content simply scrolls. */
    padding-bottom: var(--s-7);
  }

  .record-dates {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--s-4);
    padding: var(--s-3) var(--s-6);
    border-bottom: 1px solid var(--line);
    background: var(--bg-sunk);
    color: var(--text-dim);
    font-size: var(--t-xs);
    font-weight: 500;
    letter-spacing: 0.03em;
  }
  .record-dates span { color: var(--text-faint); text-transform: capitalize; }

  .record-apparatus-group {
    border-bottom: 1px solid var(--line);
    padding: var(--s-4) var(--s-6);
  }
  .record-apparatus-group > summary {
    cursor: pointer;
    color: var(--text-dim);
    font-size: var(--t-sm);
    font-weight: 600;
  }
  .record-apparatus-group[open] { padding: 0; }
  .record-apparatus-group[open] > summary {
    padding: var(--s-4) var(--s-6);
    border-bottom: 1px solid var(--line);
  }

  .text-record-link {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--s-4);
    margin: 0;
    padding: var(--s-5) var(--s-6);
    background: var(--accent-soft);
    color: var(--accent);
    font-size: var(--t-sm);
    font-weight: 600;
    text-decoration: none;
    transition: background 0.18s var(--ease), color 0.18s var(--ease);
  }
  .text-record-link span { font-size: var(--t-md); transition: transform 0.18s var(--ease); }
  .text-record-link:hover { background: var(--accent); color: #fff; }
  .text-record-link:hover span { transform: translateX(4px); }

  .loading-state {
    position: absolute;
    z-index: 20;
    inset: 0;
    display: grid;
    place-content: center;
    justify-items: center;
    gap: var(--s-3);
    background: var(--bg);
  }
  .loading-state > span {
    width: 26px;
    height: 26px;
    border: 1px solid var(--line-strong);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  .loading-state p { margin: 0; color: var(--text-faint); font-size: var(--t-xs); letter-spacing: 0.1em; text-transform: uppercase; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .error-toast {
    position: absolute;
    z-index: 18;
    top: var(--s-4);
    right: var(--s-4);
    width: min(400px, calc(100vw - 32px));
    display: flex;
    justify-content: space-between;
    gap: var(--s-4);
    padding: var(--s-4);
    border: 1px solid var(--conf-d);
    border-left-width: 3px;
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 20px 48px rgb(20 23 42 / 0.10);
  }
  .error-toast strong { font-size: var(--t-sm); font-weight: 600; }
  .error-toast p { margin: var(--s-1) 0 0; color: var(--text-dim); font-size: var(--t-xs); line-height: var(--lh-body); }
  .error-toast button { border: 0; background: none; color: var(--text-dim); cursor: pointer; font-size: 18px; line-height: 1; }
  .error-toast button:hover { color: var(--text); }

  @media (max-width: 1180px) {
    :global(:root) { --reader-width: 392px; }
  }

  @media (max-width: 860px) {
    /* On a phone the rail becomes a bottom tool strip: the map keeps the whole
       viewport above it, which is the only proportion that works at this size. */
    :global(:root) { --timeline-height: 104px; }
    .map { inset: 0 0 calc(var(--timeline-height) + 56px) 0; }
    .map-key, .reading .map-key { right: auto; bottom: calc(var(--timeline-height) + 64px); left: var(--s-2); gap: var(--s-3); max-width: calc(100vw - 16px); overflow-x: auto; }
    .detail-limit, .reading .detail-limit { top: var(--s-2); right: var(--s-2); }
    .reading-surface {
      inset: auto 0 calc(var(--timeline-height) + 56px) 0;
      width: 100%;
      height: min(56dvh, 520px);
      border-top: 1px solid var(--line);
      border-left: 0;
      box-shadow: 0 -20px 48px rgb(20 23 42 / 0.12);
    }
    .record-dates { padding: var(--s-2) var(--s-4); }
    .record-apparatus-group { padding-inline: var(--s-4); }
    .record-apparatus-group[open] > summary { padding-inline: var(--s-4); }
    .text-record-link { padding: var(--s-4); }
    :global(.maplibregl-ctrl-bottom-right) { right: 6px; bottom: calc(var(--timeline-height) + 64px); }
  }
</style>
