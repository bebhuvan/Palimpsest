<script lang="ts">
  import { onMount } from 'svelte';
  import { replaceState } from '$app/navigation';
  import type { GeoJSONFeature, GeoJSONSource, Map as MapLibreMap, MapGeoJSONFeature } from 'maplibre-gl';
  import type { Protocol } from 'pmtiles';
  import type { FeatureCollection, Point, Polygon } from 'geojson';
  import {
    artifact,
    artifactUrl,
    closestNameForYear,
    displayNameForYear,
    loadContentBundle,
    loadCausalContext,
    loadChronologyContext,
    loadEvidenceAssertions,
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
    loadThemeAssertions,
    loadWikiContext,
    nameForYear,
    normalizeSearchQuery,
    searchStaticRecords,
    searchableNames,
    type AttributionReport,
    type ContentBundle,
    type CausalClaim,
    type CausalPath,
    type CoverageCell,
    type EvidenceAssertion,
    type FeatureContentLink,
    type HistoricalDossier,
    type HistoricalEntity,
    type HistoricalMapMetadata,
    type HistoricalNameAttestation,
    type HistoricalPeriodDefinition,
    type LoadedRelease,
    type LayerCatalog,
    type QualityReport,
    type SearchRecord,
    type StaticSearchIndex,
    type RegionTimeEntry,
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
    MINIMUM_YEAR,
    normalizeYear,
    parseYearInput,
    scaleForYear,
    stepYear,
    TIMELINE_BANDS,
    TIMELINE_MAX,
    yearForScale,
    type Era
  } from '$lib/history';
  import {
    HISTORICAL_LENSES,
    isHistoricalLens,
    lensDefinition,
    recordMatchesLens,
    reviewedLensFilter,
    type HistoricalLens
  } from '$lib/lenses';
  import {
    FIRST_OHM_LABEL_LAYER,
    historyMapStyle,
    OHM_COPYRIGHT_URL,
    OHM_INTERACTIVE_LAYER_IDS,
    setOhmLayerVisibility,
    updateOhmYear,
    type HistoricalLayerMode
  } from '$lib/ohm';
  import 'maplibre-gl/dist/maplibre-gl.css';

  type Selection = {
    sourceRole: 'reviewed' | 'ohm';
    featureId: string;
    entityId?: string;
    name: string;
    kind: string;
    validFrom: number;
    validTo: number;
    spatialMeaning: string;
    temporalConfidence: string;
    spatialConfidence: string;
    interpretiveConfidence: string;
    reviewStatus: string;
    wikidataId?: string;
    disputeGroup?: string;
    contentShard?: string;
    sourceId?: string;
    nameAttestation?: HistoricalNameAttestation;
    dateLabel?: string;
    longitude?: number;
    latitude?: number;
    ohm?: {
      sourceLayer: string;
      elementId?: string;
      startDate?: string;
      endDate?: string;
      source?: string;
      sourceRef?: string;
      license?: string;
      copyright?: string;
      attribution?: string;
      changeset?: string;
      datesComplete: boolean;
    };
  };

  const DATA_BASE = (import.meta.env.VITE_DATA_BASE as string | undefined) || '/data';
  const MAP_SOURCE = 'historical-world';
  const THEME_DISCOVERY_SOURCE = 'theme-discovery-points';
  const COVERAGE_SOURCE = 'coverage-gaps';
  const HISTORICAL_MAP_IMAGE_SOURCE = 'historical-map-image';
  const HISTORICAL_MAP_IMAGE_LAYER = 'historical-map-image-raster';
  const FILL_LAYER = 'history-fill';
  const LINE_LAYER = 'history-line';
  const SOFT_LINE_LAYER = 'history-soft-line';
  const CONTESTED_LAYER = 'history-contested-line';
  const SELECTED_HALO_LAYER = 'history-selected-halo';
  const SELECTED_LAYER = 'history-selected-line';
  const REVIEWED_LABEL_LAYER = 'history-reviewed-label';
  const REVIEWED_PLACE_POINT_LAYER = 'history-reviewed-place-point';
  const REVIEWED_PLACE_LABEL_LAYER = 'history-reviewed-place-label';
  const THEME_FILL_LAYER = 'history-theme-fill';
  const THEME_LINE_LAYER = 'history-theme-line';
  const THEME_DISCOVERY_LAYER = 'history-theme-discovery';
  const THEME_POINT_LAYER = 'history-theme-point';
  const THEME_LABEL_LAYER = 'history-theme-label';
  const COVERAGE_FILL_LAYER = 'coverage-gap-fill';
  const COVERAGE_EDGE_LAYER = 'coverage-gap-edge';
  const HISTORY_LAYERS = [THEME_LABEL_LAYER, REVIEWED_PLACE_LABEL_LAYER, REVIEWED_LABEL_LAYER, THEME_POINT_LAYER, THEME_DISCOVERY_LAYER, REVIEWED_PLACE_POINT_LAYER, SELECTED_LAYER, SELECTED_HALO_LAYER, THEME_LINE_LAYER, THEME_FILL_LAYER, CONTESTED_LAYER, SOFT_LINE_LAYER, LINE_LAYER, FILL_LAYER];
  const SOFT_MEANINGS = ['claim', 'territorial_claim', 'cultural_region', 'influence_zone', 'mobility_range', 'seasonal_use', 'network', 'unknown_extent', 'unknown', 'tributary_relationship'];
  const POINT_KINDS = ['settlement', 'archaeological_site', 'event'];

  let mapContainer: HTMLDivElement;
  let aboutDialog: HTMLDialogElement;
  let exactYearInput: HTMLInputElement;
  let searchInput: HTMLInputElement;
  let map: MapLibreMap | null = null;
  let pmtilesProtocol: Protocol | null = null;
  let release: LoadedRelease | null = null;
  let staticSearchIndex: StaticSearchIndex | null = null;
  let searchIndex: SearchRecord[] = [];
  let searchResults: SearchRecord[] = [];
  let coverage: CoverageCell[] = [];
  let searchQuery = '';
  let searchFocused = false;
  let searchActiveIndex = -1;
  let selectedYear = 1200;
  let activeEra: Era = eraForYear(selectedYear);
  let selected: Selection | null = null;
  let selectedEntity: HistoricalEntity | null = null;
  let linkedEntities: HistoricalEntity[] = [];
  let selectedDossiers: HistoricalDossier[] = [];
  let selectedLink: FeatureContentLink | null = null;
  let selectedCausalClaims: CausalClaim[] = [];
  let selectedCausalPaths: CausalPath[] = [];
  let selectedPeriods: HistoricalPeriodDefinition[] = [];
  let selectedWikiContext: SelectedWikiContext | null = null;
  let selectedRegionalContext: SelectedRegionalContext | null = null;
  let selectedThematicAssertions: ThematicAssertion[] = [];
  let selectedEvidenceAssertions: EvidenceAssertion[] = [];
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
  let yearEditorOpen = false;
  let yearDraft = '1200';
  let yearDraftEra: 'BCE' | 'CE' = 'CE';
  let yearInputError = '';
  let reducedMotion = false;
  let detailLimitReached = false;
  let mapAnnouncement = '';
  let linkedRecordToRestore: SearchRecord | null = null;
  let layerMode: HistoricalLayerMode = 'combined';
  let activeLens: HistoricalLens = 'all';
  let evidenceOverlay: 'none' | 'confidence' | 'provenance' = 'none';

  $: activeHistoricalMap = historicalMaps.find(
    (historicalMap) => historicalMap.map_id === selectedHistoricalMapId
  ) ?? null;
  $: normalizedQuery = searchQuery.trim().toLocaleLowerCase();
  $: activeLensDefinition = lensDefinition(activeLens);
  $: timelinePosition = scaleForYear(selectedYear);
  $: activeDatedRecords = searchIndex.filter(
    (record) => record.valid_from <= selectedYear && record.valid_to >= selectedYear
  );
  $: activeLensRecordCount = activeDatedRecords.filter(
    (record) => recordMatchesLens(record, activeLens)
  ).length;
  $: selectedSource = selected?.sourceRole === 'reviewed' ? sourceForFeature(selected.featureId, selected.sourceId) : null;
  $: selectedSearchRecord = selected?.sourceRole === 'reviewed'
    ? searchIndex.find((record) => record.entity_id === selected?.entityId || record.feature_ids.includes(selected?.featureId ?? ''))
    : undefined;
  $: alternateNames = selected?.sourceRole === 'reviewed'
    ? Array.from(new Set([
        ...(selectedSearchRecord?.name_attestations ?? [])
          .filter((name) => name.valid_from <= selectedYear && name.valid_to >= selectedYear)
          .map((name) => name.text),
        ...Object.values(selectedEntity?.names ?? {}),
        ...Object.values(selectedEntity?.aliases ?? {}).flat()
      ])).filter((name) => name !== selected?.name)
    : [];
  $: selectedRelationships = selectedEntity?.relationships ?? [];
  $: elsewhere = selected?.sourceRole === 'reviewed' ? elsewhereAtThisTime(selected) : [];
  $: visibleThematicAssertions = selectedThematicAssertions.filter(
    (assertion) => activeLens === 'all' || assertion.theme === activeLens
  );

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
    searchActiveIndex = -1;
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

  function humanize(value: string): string {
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
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
      temporalConfidence: 'not assessed by History Joice',
      spatialConfidence: 'not assessed by History Joice',
      interpretiveConfidence: 'not assessed by History Joice',
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

  function yearFilter(year: number): unknown[] {
    return [
      'all',
      ['<=', ['get', 'valid_from'], year],
      ['>=', ['get', 'valid_to'], year],
      ['<=', ['coalesce', ['get', 'min_display_zoom'], 0], ['zoom']]
    ];
  }

  function combinedFilter(year: number, extra: unknown[]): unknown[] {
    return ['all', ...yearFilter(year).slice(1), extra];
  }

  function themedFilter(year: number, extra: unknown[]): unknown {
    if (activeLens === 'all') return false;
    return ['all', ...yearFilter(year).slice(1), reviewedLensFilter(activeLens), extra];
  }

  type LensVisual = {
    accent: string;
    fillOpacity: number;
    lineWidth: number;
    lineDash: number[];
    pointRadius: number;
  };

  function lensVisual(lens: HistoricalLens): LensVisual {
    const shape = {
      all: { fillOpacity: 0.16, lineWidth: 1.2, lineDash: [1, 0.1], pointRadius: 3.6 },
      power: { fillOpacity: 0.24, lineWidth: 1.8, lineDash: [1, 0.1], pointRadius: 4.5 },
      belief: { fillOpacity: 0.2, lineWidth: 1.55, lineDash: [1.2, 1.2], pointRadius: 4.1 },
      knowledge: { fillOpacity: 0.18, lineWidth: 1.45, lineDash: [0.45, 1.15], pointRadius: 3.7 },
      culture: { fillOpacity: 0.21, lineWidth: 1.65, lineDash: [2.8, 1.1], pointRadius: 4.3 },
      trade: { fillOpacity: 0.19, lineWidth: 2, lineDash: [4, 1.2], pointRadius: 3.9 }
    }[lens];
    return { ...shape, accent: lensDefinition(lens).accent };
  }

  function lensAccent(lens: HistoricalLens): string {
    return lensVisual(lens).accent;
  }

  function reviewedFillColor(): unknown {
    if (evidenceOverlay === 'confidence') {
      return ['match', ['get', 'interpretive_confidence'],
        'A', '#236b55',
        'B', '#55815c',
        'C', '#b08a42',
        'D', '#a95d4f',
        '#77736d'
      ];
    }
    if (evidenceOverlay === 'provenance') {
      return ['match', ['get', 'source_id'],
        'loc_copernicus', '#2f6683',
        'cliopatria', '#76584f',
        'pleiades', '#5f716b',
        'open_context', '#84654f',
        '#726278'
      ];
    }
    return [
      'match', ['get', 'spatial_meaning'],
      'legal_boundary', '#625e68',
      'territorial_control', '#76584f',
      'claim', '#88745f',
      'territorial_claim', '#88745f',
      'occupation', '#7d5a4e',
      'tributary_relationship', '#77705c',
      'cultural_region', '#5f716b',
      'influence_zone', '#5f716b',
      'mobility_range', '#5f716b',
      'seasonal_use', '#5f716b',
      'network', '#657078',
      '#716d68'
    ];
  }

  function reviewedLineColor(): unknown {
    if (evidenceOverlay !== 'none') return reviewedFillColor();
    return ['case', ['boolean', ['feature-state', 'hover'], false], '#453b37', '#625d59'];
  }

  function reviewedFillOpacity(lens: HistoricalLens): unknown {
    const dimmed = lens !== 'all';
    return [
      'interpolate', ['linear'], ['zoom'],
      1, ['case',
        ['boolean', ['feature-state', 'selected'], false], dimmed ? 0.13 : 0.24,
        ['boolean', ['feature-state', 'hover'], false], dimmed ? 0.08 : 0.16,
        ['==', ['get', 'review_status'], 'contested'], dimmed ? 0.012 : 0.055,
        ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]], dimmed ? 0.016 : 0.075,
        dimmed ? 0.022 : 0.11
      ],
      4, ['case',
        ['boolean', ['feature-state', 'selected'], false], dimmed ? 0.11 : 0.21,
        ['boolean', ['feature-state', 'hover'], false], dimmed ? 0.07 : 0.14,
        ['==', ['get', 'review_status'], 'contested'], dimmed ? 0.009 : 0.04,
        ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]], dimmed ? 0.012 : 0.055,
        dimmed ? 0.018 : 0.08
      ],
      8, ['case',
        ['boolean', ['feature-state', 'selected'], false], dimmed ? 0.09 : 0.17,
        ['boolean', ['feature-state', 'hover'], false], dimmed ? 0.055 : 0.11,
        ['==', ['get', 'review_status'], 'contested'], dimmed ? 0.006 : 0.025,
        ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]], dimmed ? 0.006 : 0.025,
        dimmed ? 0.01 : 0.035
      ]
    ];
  }

  function reviewedLineOpacity(lens: HistoricalLens): unknown {
    const dimmed = lens !== 'all';
    return [
      'case',
      ['boolean', ['feature-state', 'hover'], false], dimmed ? 0.38 : 0.82,
      ['==', ['get', 'spatial_confidence'], 'D'], dimmed ? 0.045 : 0.25,
      dimmed ? 0.085 : 0.46
    ];
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
    updateOhmYear(map, selectedYear, activeLens);
    const visual = lensVisual(activeLens);
    const backgroundOpacity = activeLens === 'all' ? 1 : 0.16;
    for (const layer of [FILL_LAYER, LINE_LAYER, SELECTED_HALO_LAYER, SELECTED_LAYER]) {
      if (map.getLayer(layer)) {
        map.setFilter(layer, combinedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never);
      }
    }
    if (map.getLayer(FILL_LAYER)) {
      map.setPaintProperty(FILL_LAYER, 'fill-opacity', reviewedFillOpacity(activeLens) as never);
      map.setPaintProperty(FILL_LAYER, 'fill-color', reviewedFillColor() as never);
    }
    if (map.getLayer(LINE_LAYER)) {
      map.setPaintProperty(LINE_LAYER, 'line-opacity', reviewedLineOpacity(activeLens) as never);
      map.setPaintProperty(LINE_LAYER, 'line-color', reviewedLineColor() as never);
    }
    if (map.getLayer(REVIEWED_LABEL_LAYER)) {
      map.setFilter(REVIEWED_LABEL_LAYER, combinedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['!', ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]]) as never);
      map.setPaintProperty(REVIEWED_LABEL_LAYER, 'text-opacity', backgroundOpacity);
    }
    for (const layer of [REVIEWED_PLACE_POINT_LAYER, REVIEWED_PLACE_LABEL_LAYER]) {
      if (map.getLayer(layer)) {
        map.setFilter(layer, combinedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never);
      }
    }
    if (map.getLayer(REVIEWED_PLACE_POINT_LAYER)) {
      map.setPaintProperty(REVIEWED_PLACE_POINT_LAYER, 'circle-opacity', activeLens === 'all' ? 0.76 : 0.13);
    }
    if (map.getLayer(REVIEWED_PLACE_LABEL_LAYER)) {
      map.setPaintProperty(REVIEWED_PLACE_LABEL_LAYER, 'text-opacity', backgroundOpacity);
    }
    if (map.getLayer(SOFT_LINE_LAYER)) {
      map.setFilter(SOFT_LINE_LAYER, combinedFilter(selectedYear, ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]]) as never);
      map.setPaintProperty(SOFT_LINE_LAYER, 'line-opacity', activeLens === 'all' ? 0.48 : 0.09);
    }
    if (map.getLayer(CONTESTED_LAYER)) {
      map.setFilter(CONTESTED_LAYER, combinedFilter(selectedYear, ['any', ['==', ['get', 'review_status'], 'contested'], ['has', 'dispute_group']]) as never);
      map.setPaintProperty(CONTESTED_LAYER, 'line-opacity', activeLens === 'all' ? 0.76 : 0.14);
    }
    const thematicArea = ['!=', ['get', 'spatial_meaning'], 'location'];
    if (map.getLayer(THEME_FILL_LAYER)) {
      map.setFilter(THEME_FILL_LAYER, themedFilter(selectedYear, thematicArea) as never);
      map.setPaintProperty(THEME_FILL_LAYER, 'fill-color', visual.accent);
      map.setPaintProperty(THEME_FILL_LAYER, 'fill-opacity', ['interpolate', ['linear'], ['zoom'], 1, visual.fillOpacity, 5, visual.fillOpacity * 0.7, 9, visual.fillOpacity * 0.46] as never);
    }
    if (map.getLayer(THEME_LINE_LAYER)) {
      map.setFilter(THEME_LINE_LAYER, themedFilter(selectedYear, thematicArea) as never);
      map.setPaintProperty(THEME_LINE_LAYER, 'line-color', visual.accent);
      map.setPaintProperty(THEME_LINE_LAYER, 'line-width', ['interpolate', ['linear'], ['zoom'], 1, visual.lineWidth, 6, visual.lineWidth * 1.45, 10, visual.lineWidth * 1.8] as never);
      map.setPaintProperty(THEME_LINE_LAYER, 'line-dasharray', visual.lineDash);
    }
    updateThemeDiscoveryLayer();
    if (map.getLayer(THEME_DISCOVERY_LAYER)) {
      map.setPaintProperty(THEME_DISCOVERY_LAYER, 'circle-color', visual.accent);
    }
    if (map.getLayer(THEME_POINT_LAYER)) {
      map.setFilter(THEME_POINT_LAYER, themedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never);
      map.setPaintProperty(THEME_POINT_LAYER, 'circle-color', visual.accent);
      map.setPaintProperty(THEME_POINT_LAYER, 'circle-radius', ['interpolate', ['linear'], ['zoom'], 1, visual.pointRadius * 0.5, 5, visual.pointRadius, 12, visual.pointRadius * 1.45] as never);
    }
    if (map.getLayer(THEME_LABEL_LAYER)) {
      map.setFilter(THEME_LABEL_LAYER, themedFilter(selectedYear, ['==', ['get', 'primary'], true]) as never);
      map.setPaintProperty(THEME_LABEL_LAYER, 'text-color', visual.accent);
      map.setLayoutProperty(THEME_LABEL_LAYER, 'text-field', ['concat', activeLensDefinition.marker, '  ', ['get', 'name']] as never);
    }
    updateCoverageLayer();
  }

  function applyLayerMode(): void {
    if (!map) return;
    setOhmLayerVisibility(map, layerMode, activeLens);
    const reviewedVisibility = layerMode === 'historical-detail' ? 'none' : 'visible';
    for (const layer of HISTORY_LAYERS) {
      if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', reviewedVisibility);
    }
    const coverageVisibility = reviewedVisibility === 'visible' && activeLens === 'all' ? 'visible' : 'none';
    for (const layer of [COVERAGE_FILL_LAYER, COVERAGE_EDGE_LAYER]) {
      if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', coverageVisibility);
    }
    detailLimitReached = layerMode !== 'historical-detail' && map.getZoom() > 7.05;
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

  function selectHistoricalMap(event: Event): void {
    selectedHistoricalMapId = (event.currentTarget as HTMLSelectElement).value;
    if (historicalMapVisible) void updateHistoricalMapOverlay();
  }

  function setYear(candidate: number): void {
    const next = normalizeYear(candidate, selectedYear);
    const nextEra = eraForYear(next);
    selectedYear = next;
    void updateSearchTimeBand(next);
    yearDraft = String(Math.abs(next));
    yearDraftEra = next < 0 ? 'BCE' : 'CE';
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

  function handleTimeline(event: Event): void {
    setYear(yearForScale(Number((event.currentTarget as HTMLInputElement).value)));
  }

  function handleTimelineKey(event: KeyboardEvent): void {
    let amount = 0;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') amount = event.shiftKey ? -10 : -1;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') amount = event.shiftKey ? 10 : 1;
    if (event.key === 'PageDown') amount = -100;
    if (event.key === 'PageUp') amount = 100;
    if (event.key === 'Home') {
      event.preventDefault();
      setYear(MINIMUM_YEAR);
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      setYear(MAXIMUM_YEAR);
      return;
    }
    if (amount) {
      event.preventDefault();
      setYear(stepYear(selectedYear, amount));
    }
  }

  function openYearEditor(): void {
    yearDraft = String(Math.abs(selectedYear));
    yearDraftEra = selectedYear < 0 ? 'BCE' : 'CE';
    yearInputError = '';
    yearEditorOpen = true;
    requestAnimationFrame(() => exactYearInput?.select());
  }

  function submitYear(event: SubmitEvent): void {
    event.preventDefault();
    const parsed = parseYearInput(yearDraft, yearDraftEra, selectedYear);
    if (parsed === null) {
      yearInputError = `Enter a year from 1 to ${Math.abs(yearDraftEra === 'BCE' ? MINIMUM_YEAR : MAXIMUM_YEAR)}.`;
      return;
    }
    setYear(parsed);
    yearEditorOpen = false;
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

  function handleSearchKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' && searchResults.length) {
      event.preventDefault();
      searchActiveIndex = (searchActiveIndex + 1) % searchResults.length;
    } else if (event.key === 'ArrowUp' && searchResults.length) {
      event.preventDefault();
      searchActiveIndex = (searchActiveIndex - 1 + searchResults.length) % searchResults.length;
    } else if (event.key === 'Enter' && searchResults.length) {
      event.preventDefault();
      chooseSearchResult(searchResults[Math.max(0, searchActiveIndex)]);
    } else if (event.key === 'Escape') {
      searchFocused = false;
      searchActiveIndex = -1;
      searchInput.blur();
    }
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
    searchFocused = false;
    searchActiveIndex = -1;
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

  function updateMapPadding(reading: boolean): void {
    if (!map || window.innerWidth < 840) return;
    const readerPadding = window.innerWidth < 1050 ? 390 : 458;
    map.easeTo({ padding: { top: 0, left: 0, bottom: 0, right: reading ? readerPadding : 0 }, duration: reducedMotion ? 0 : 320 });
  }

  async function resolveSelectionContent(selection: Selection): Promise<void> {
    selectedEntity = null;
    linkedEntities = [];
    selectedDossiers = [];
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
        const entityIds = content?.link.entity_ids ?? [
          selection.entityId,
          selection.wikidataId ? `wikidata:${selection.wikidataId}` : undefined
        ].filter(Boolean) as string[];
        // Core reading material is ready. Optional historical context continues
        // below without keeping the sidebar behind a loading state.
        contentLoading = false;
        const [causal, periods, wikiContext, regionalContext, thematicAssertions, evidenceAssertions] = await Promise.all([
          loadCausalContext(release, entityIds),
          loadChronologyContext(release, entityIds, selectedYear),
          loadWikiContext(release, selection.featureId, selectedYear),
          loadRegionalContextForSelection(release, selection),
          loadThemeAssertions(release, selection.featureId),
          loadEvidenceAssertions(release, selection.featureId)
        ]);
        if (selected?.featureId !== selection.featureId) return;
        selectedCausalClaims = causal.claims;
        selectedCausalPaths = causal.paths;
        selectedPeriods = periods;
        selectedWikiContext = wikiContext;
        selectedRegionalContext = regionalContext;
        selectedThematicAssertions = thematicAssertions;
        selectedEvidenceAssertions = evidenceAssertions;
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
      const [causal, periods, wikiContext, regionalContext, thematicAssertions, evidenceAssertions] = await Promise.all([
        loadCausalContext(release, entityCandidates),
        loadChronologyContext(release, entityCandidates, selectedYear),
        loadWikiContext(release, selection.featureId, selectedYear),
        loadRegionalContextForSelection(release, selection),
        loadThemeAssertions(release, selection.featureId),
        loadEvidenceAssertions(release, selection.featureId)
      ]);
      if (selected?.featureId !== selection.featureId) return;
      selectedCausalClaims = causal.claims;
      selectedCausalPaths = causal.paths;
      selectedPeriods = periods;
      selectedWikiContext = wikiContext;
      selectedRegionalContext = regionalContext;
      selectedThematicAssertions = thematicAssertions;
      selectedEvidenceAssertions = evidenceAssertions;
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

  function periodLabel(period: HistoricalPeriodDefinition): string {
    return period.labels.en?.[0] ?? Object.values(period.labels)[0]?.[0] ?? period.period_id;
  }

  function sourceForFeature(featureId: string, declaredSourceId?: string): SourceReference | null {
    const sourceId = declaredSourceId ?? featureId.split(':')[0];
    return release?.manifest.sources.find((source) => source.source_id === sourceId) ?? null;
  }

  function causalSummary(claim: CausalClaim): string {
    return claim.mechanism_summary.en ?? Object.values(claim.mechanism_summary)[0] ?? claim.mechanism_type;
  }

  function contextName(entity: HistoricalEntity): string {
    return entity.names.en ?? Object.values(entity.names)[0] ?? entity.entity_id;
  }

  function contextDescription(entity: HistoricalEntity): string {
    return entity.descriptions.en ?? Object.values(entity.descriptions)[0] ?? 'No short description is published in this release.';
  }

  function assertionObjectLabel(assertion: EvidenceAssertion): string {
    if (assertion.object.entity_id) {
      const entity = linkedEntities.find(
        (candidate) => candidate.entity_id === assertion.object.entity_id
      );
      return entity?.names.en ?? Object.values(entity?.names ?? {})[0] ?? assertion.object.entity_id;
    }
    if (assertion.object.year) return formatYear(assertion.object.year);
    return assertion.object.value ?? 'Unspecified value';
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

  function regionalRecord(entry: RegionTimeEntry): SearchRecord | undefined {
    return searchIndex.find((record) =>
      record.entity_id === entry.entity_id ||
      Boolean(entry.feature_id && record.feature_ids.includes(entry.feature_id))
    );
  }

  function regionalName(entry: RegionTimeEntry): string {
    const record = regionalRecord(entry);
    if (record) return displayNameForYear(record, selectedYear);
    const entity = selectedRegionalContext?.entities.get(entry.entity_id);
    return entity ? contextName(entity) : entry.entity_id;
  }

  function geometryStatement(meaning: string): string {
    const statements: Record<string, string> = {
      territorial_control: 'A source reconstruction of territorial control. Authority may have varied within this area.',
      legal_boundary: 'A boundary documented as a legal or surveyed line for its stated date.',
      claim: 'A claimed extent, which may not represent effective control.',
      territorial_claim: 'A claimed extent from a stated perspective, which may not represent effective control.',
      occupation: 'An area represented as under occupation for this interval.',
      tributary_relationship: 'A tributary relationship, not uniform territorial administration.',
      cultural_region: 'A cultural region with a deliberately soft edge, not a state border.',
      influence_zone: 'An approximate zone of influence rather than exclusive control.',
      location: 'A location or representative point, not an asserted territorial extent.',
      route: 'A route reconstructed from the cited source.',
      mobility_range: 'A mobile range with variable use and deliberately soft edges.',
      seasonal_use: 'A seasonal-use area, not permanent or exclusive control.',
      network: 'A network of relationships and movement, not a bounded territory.',
      ohm_contributor_detail: 'Contributor-built historical detail from OpenHistoricalMap. Its dates and geometry are shown separately from the reviewed reconstruction.',
      unknown_extent: 'An approximate extent whose precise spatial meaning is not known.',
      unknown: 'The release does not yet describe what this geometry represents.'
    };
    return statements[meaning] ?? statements.unknown;
  }

  function confidenceText(grade: string): string {
    return {
      A: 'high documentary precision',
      B: 'specialist reconstruction',
      C: 'approximate atlas reconstruction',
      D: 'location or influence only',
      unknown: 'not yet assessed'
    }[grade] ?? 'not yet assessed';
  }

  function dossierLabel(dossier: HistoricalDossier): string {
    if (dossier.content_role === 'primary_source') return 'Primary source transcription';
    if (dossier.content_role === 'project_interpretation') return 'History Joice interpretation';
    if (dossier.source_ref.source_id === 'wikipedia') return `From ${dossier.language.toUpperCase()} Wikipedia`;
    return `Tertiary summary · ${dossier.source_ref.publisher}`;
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
      if (!artifact(release, tilePath)) throw new Error(`This release has no ${eraLabel(era).toLowerCase()} map archive.`);
      const absoluteTileUrl = new URL(artifactUrl(release, tilePath), window.location.href).href;
      const beforeLabels = map.getLayer(FIRST_OHM_LABEL_LAYER) ? FIRST_OHM_LABEL_LAYER : undefined;
      map.addSource(MAP_SOURCE, {
        type: 'vector',
        url: `pmtiles://${absoluteTileUrl}`,
        promoteId: 'feature_id',
        attribution: 'Historical geography: Seshat Global History Databank / Cliopatria (CC BY 4.0)'
      });
      if (!map.getSource(THEME_DISCOVERY_SOURCE)) {
        map.addSource(THEME_DISCOVERY_SOURCE, {
          type: 'geojson',
          data: themeDiscoveryPoints()
        });
      }
      map.addLayer({
        id: FILL_LAYER,
        type: 'fill',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'fill-color': reviewedFillColor() as never,
          'fill-opacity': reviewedFillOpacity(activeLens) as never,
          'fill-antialias': true
        }
      }, beforeLabels);
      map.addLayer({
        id: LINE_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'line-color': reviewedLineColor() as never,
          'line-width': ['interpolate', ['linear'], ['zoom'],
            1, ['case', ['boolean', ['feature-state', 'hover'], false], 0.9, 0.4],
            4, ['case', ['boolean', ['feature-state', 'hover'], false], 1.2, 0.68],
            8, ['case', ['boolean', ['feature-state', 'hover'], false], 1.65, 0.9]
          ],
          'line-opacity': reviewedLineOpacity(activeLens) as never
        }
      }, beforeLabels);
      map.addLayer({
        id: SOFT_LINE_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]]) as never,
        paint: {
          'line-color': '#68766f',
          'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.5, 6, 0.95],
          'line-opacity': activeLens === 'all' ? 0.48 : 0.09,
          'line-dasharray': [1.1, 2.5]
        }
      }, beforeLabels);
      map.addLayer({
        id: CONTESTED_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['any', ['==', ['get', 'review_status'], 'contested'], ['has', 'dispute_group']]) as never,
        paint: {
          'line-color': '#8e5a50',
          'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.7, 6, 1.35],
          'line-opacity': activeLens === 'all' ? 0.76 : 0.14,
          'line-dasharray': [2.6, 2.2]
        }
      }, beforeLabels);
      map.addLayer({
        id: THEME_FILL_LAYER,
        type: 'fill',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: themedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'fill-color': lensAccent(activeLens),
          'fill-opacity': ['interpolate', ['linear'], ['zoom'], 1, lensVisual(activeLens).fillOpacity, 5, lensVisual(activeLens).fillOpacity * 0.7, 9, lensVisual(activeLens).fillOpacity * 0.46]
        }
      }, beforeLabels);
      map.addLayer({
        id: THEME_LINE_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: themedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'line-color': lensAccent(activeLens),
          'line-width': ['interpolate', ['linear'], ['zoom'], 1, lensVisual(activeLens).lineWidth, 6, lensVisual(activeLens).lineWidth * 1.45, 10, lensVisual(activeLens).lineWidth * 1.8],
          'line-opacity': 0.9,
          'line-dasharray': lensVisual(activeLens).lineDash
        }
      }, beforeLabels);
      map.addLayer({
        id: THEME_DISCOVERY_LAYER,
        type: 'circle',
        source: THEME_DISCOVERY_SOURCE,
        minzoom: 0,
        maxzoom: 5.5,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 3.2, 3, 4.2, 5, 5],
          'circle-color': lensAccent(activeLens),
          'circle-stroke-color': '#fffdf7',
          'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 0, 0.8, 5, 1.2],
          'circle-opacity': ['interpolate', ['linear'], ['zoom'], 0, 0.88, 4, 0.92, 5.5, 0]
        }
      }, beforeLabels);
      map.addLayer({
        id: SELECTED_HALO_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'line-color': '#fffdf7',
          'line-width': ['interpolate', ['linear'], ['zoom'],
            1, ['case', ['boolean', ['feature-state', 'selected'], false], 3.8, 0],
            7, ['case', ['boolean', ['feature-state', 'selected'], false], 5.2, 0]
          ],
          'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.78, 0]
        }
      }, beforeLabels);
      map.addLayer({
        id: SELECTED_LAYER,
        type: 'line',
        source: MAP_SOURCE,
        'source-layer': 'history',
        filter: combinedFilter(selectedYear, ['!=', ['get', 'spatial_meaning'], 'location']) as never,
        paint: {
          'line-color': '#302d2a',
          'line-width': ['interpolate', ['linear'], ['zoom'],
            1, ['case', ['boolean', ['feature-state', 'selected'], false], 1.45, 0],
            7, ['case', ['boolean', ['feature-state', 'selected'], false], 2.2, 0]
          ],
          'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0]
        }
      }, beforeLabels);
      map.addLayer({
        id: REVIEWED_LABEL_LAYER,
        type: 'symbol',
        source: MAP_SOURCE,
        'source-layer': 'history_labels',
        maxzoom: 9,
        filter: combinedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['!', ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]]) as never,
        layout: {
          'text-field': ['get', 'name'],
          'text-font': ['Noto Sans Bold'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 1, 10, 4, 12.5, 8, 14],
          'text-letter-spacing': 0.055,
          'text-max-width': 10,
          'text-padding': 7,
          'symbol-sort-key': ['-', ['to-number', ['get', 'label_area'], 0]]
        },
        paint: {
          'text-color': '#2f2926',
          'text-halo-color': 'rgba(247, 244, 236, 0.94)',
          'text-halo-width': 1.55,
          'text-halo-blur': 0.25,
          'text-opacity': activeLens === 'all' ? 1 : 0.16
        }
      });
      map.addLayer({
        id: REVIEWED_PLACE_POINT_LAYER,
        type: 'circle',
        source: MAP_SOURCE,
        'source-layer': 'history_labels',
        minzoom: 6,
        filter: combinedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 1.4, 12, 2.5],
          'circle-color': ['match', ['get', 'kind'], 'archaeological_site', '#76584f', '#465550'],
          'circle-stroke-color': '#f7f4ec',
          'circle-stroke-width': 0.9,
          'circle-opacity': activeLens === 'all' ? 0.76 : 0.13
        }
      });
      map.addLayer({
        id: THEME_POINT_LAYER,
        type: 'circle',
        source: MAP_SOURCE,
        'source-layer': 'history_labels',
        minzoom: 1,
        filter: themedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, lensVisual(activeLens).pointRadius * 0.5, 5, lensVisual(activeLens).pointRadius, 12, lensVisual(activeLens).pointRadius * 1.45],
          'circle-color': lensAccent(activeLens),
          'circle-stroke-color': '#fffdf7',
          'circle-stroke-width': 1.2,
          'circle-opacity': 0.94
        }
      });
      map.addLayer({
        id: THEME_LABEL_LAYER,
        type: 'symbol',
        source: MAP_SOURCE,
        'source-layer': 'history_labels',
        maxzoom: 15,
        filter: themedFilter(selectedYear, ['==', ['get', 'primary'], true]) as never,
        layout: {
          'text-field': ['concat', activeLensDefinition.marker, '  ', ['get', 'name']],
          'text-font': ['Noto Sans Bold'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 1, 10.5, 6, 12, 12, 13],
          'text-letter-spacing': 0.035,
          'text-max-width': 11,
          'text-padding': 8,
          'symbol-sort-key': ['-', ['to-number', ['get', 'label_area'], 0]]
        },
        paint: {
          'text-color': lensAccent(activeLens),
          'text-halo-color': 'rgba(255, 253, 247, 0.97)',
          'text-halo-width': 1.8,
          'text-halo-blur': 0.25,
          'text-opacity': 1
        }
      });
      map.addLayer({
        id: REVIEWED_PLACE_LABEL_LAYER,
        type: 'symbol',
        source: MAP_SOURCE,
        'source-layer': 'history_labels',
        minzoom: 6,
        maxzoom: 15,
        filter: combinedFilter(selectedYear, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never,
        layout: {
          'text-field': ['get', 'name'],
          'text-font': ['Noto Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 9, 12, 11.5],
          'text-offset': [0, 0.72],
          'text-anchor': 'top',
          'text-max-width': 9,
          'text-padding': 5,
          'symbol-sort-key': ['-', ['to-number', ['get', 'label_area'], 0]]
        },
        paint: {
          'text-color': '#3b4541',
          'text-halo-color': 'rgba(247, 244, 236, 0.94)',
          'text-halo-width': 1.2,
          'text-halo-blur': 0.2,
          'text-opacity': activeLens === 'all' ? 1 : 0.16
        }
      });
      if (selectedFeatureStateId) {
        map.setFeatureState({ source: MAP_SOURCE, sourceLayer: 'history', id: selectedFeatureStateId }, { selected: true });
      }
      applyLayerMode();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Could not load this historical layer.';
    } finally {
      loadingEra = false;
    }
  }

  async function openAbout(): Promise<void> {
    aboutDialog?.showModal();
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
        yearDraft = String(Math.abs(year));
        yearDraftEra = year < 0 ? 'BCE' : 'CE';
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
      yearDraft = String(Math.abs(selectedYear));
      yearDraftEra = selectedYear < 0 ? 'BCE' : 'CE';
      activeEra = eraForYear(selectedYear);
      release = await loadRelease(DATA_BASE);

      staticSearchIndex = await loadStaticSearchIndex(release);
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
      map.on('mousemove', (event) => {
        if (!map) return;
        const reviewedLayers = [THEME_DISCOVERY_LAYER, THEME_POINT_LAYER, REVIEWED_PLACE_LABEL_LAYER, REVIEWED_LABEL_LAYER, REVIEWED_PLACE_POINT_LAYER, FILL_LAYER].filter((layer) => map?.getLayer(layer));
        const reviewed = reviewedLayers.length ? map.queryRenderedFeatures(event.point, { layers: reviewedLayers }) : [];
        const ohmLayers = OHM_INTERACTIVE_LAYER_IDS.filter((layer) => map?.getLayer(layer));
        const ohm = ohmLayers.length ? map.queryRenderedFeatures(event.point, { layers: [...ohmLayers] }) : [];
        map.getCanvas().style.cursor = reviewed.length || ohm.length ? 'pointer' : '';
        setHoveredFeature(reviewed[0]?.id === undefined ? null : String(reviewed[0].id));
      });
      map.on('mouseout', () => {
        if (!map) return;
        map.getCanvas().style.cursor = '';
        setHoveredFeature(null);
      });
      map.on('click', (event) => {
        if (!map) return;
        const reviewedLayers = [THEME_DISCOVERY_LAYER, THEME_POINT_LAYER, REVIEWED_PLACE_LABEL_LAYER, REVIEWED_LABEL_LAYER, REVIEWED_PLACE_POINT_LAYER, FILL_LAYER].filter((layer) => map?.getLayer(layer));
        const reviewed = reviewedLayers.length ? map.queryRenderedFeatures(event.point, { layers: reviewedLayers })[0] : undefined;
        if (reviewed) {
          setSelection(selectionFromFeature(reviewed, event.lngLat.lng, event.lngLat.lat));
          return;
        }
        const ohmLayers = OHM_INTERACTIVE_LAYER_IDS.filter((layer) => map?.getLayer(layer));
        const ohmFeature = ohmLayers.length
          ? map.queryRenderedFeatures(event.point, { layers: [...ohmLayers] })[0]
          : undefined;
        if (ohmFeature) {
          setSelection(
            selectionFromOhmFeature(ohmFeature, event.lngLat.lng, event.lngLat.lat)
          );
        }
      });
      map.on('zoom', () => {
        detailLimitReached = Boolean(map && layerMode !== 'historical-detail' && map.getZoom() > 7.05);
      });
      map.on('sourcedata', (event) => {
        if (event.sourceId === MAP_SOURCE && event.isSourceLoaded) refreshSelectionFromMap();
      });
      window.addEventListener('resize', () => updateMapPadding(Boolean(selected)));
      await Promise.allSettled([
        searchPromise,
        coveragePromise,
        layerCatalogPromise,
        historicalMapsPromise
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
      historicalMapRequest += 1;
      removeHistoricalMapLayer();
      map?.remove();
      pmtilesProtocol = null;
    };
  });
</script>

<svelte:head>
  <title>History Joice — A world history map</title>
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

  <header class="masthead">
    <a class="brand" href="/" aria-label="History Joice home"><span>History Joice</span><small>World history map</small></a>

    <div class="search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.7" cy="10.7" r="6.7"></circle><path d="m16 16 5 5"></path></svg>
      <input
        bind:this={searchInput}
        type="search"
        role="combobox"
        bind:value={searchQuery}
        oninput={() => void updateSearchResults()}
        onfocus={() => (searchFocused = true)}
        onblur={() => setTimeout(() => (searchFocused = false), 120)}
        onkeydown={handleSearchKey}
        placeholder="Find a historical place or polity"
        aria-label="Search historical places and alternate names"
        aria-autocomplete="list"
        aria-controls="place-results"
        aria-activedescendant={searchActiveIndex >= 0 ? `place-result-${searchActiveIndex}` : undefined}
        aria-expanded={searchFocused && normalizedQuery.length >= 2}
      />
      <kbd aria-hidden="true">/</kbd>
      {#if searchQuery}<button class="clear-search" onclick={() => { searchQuery = ''; void updateSearchResults(); searchInput.focus(); }} aria-label="Clear search">×</button>{/if}
      {#if searchFocused && normalizedQuery.length >= 2}
        <div class="search-results" id="place-results" role="listbox" aria-label="Historical place results">
          {#if searchResults.length}
            {#each searchResults as result, index (result.entity_id)}
              <button
                id={`place-result-${index}`}
                role="option"
                aria-selected={index === searchActiveIndex}
                class:active={index === searchActiveIndex}
                onmousedown={(event) => event.preventDefault()}
                onmouseenter={() => (searchActiveIndex = index)}
                onclick={() => chooseSearchResult(result)}
              >
                <span><strong>{displayName(result)}</strong><small>{humanize(result.kind)}</small></span>
                <time>{formatRange(result.valid_from, result.valid_to)}</time>
              </button>
            {/each}
          {:else}<p>No matching record in this release.</p>{/if}
        </div>
      {/if}
    </div>

    <nav class="utility-nav" aria-label="Project links">
      <a href={`/browse?year=${selectedYear}${activeLens !== 'all' ? `&lens=${activeLens}` : ''}`}>Browse records</a>
      <button onclick={openAbout}>About this map</button>
    </nav>
  </header>

  <section class="date-readout" aria-live="polite" aria-atomic="true">
    <span>World at</span>
    <strong>{formatYear(selectedYear)}</strong>
    <small>{eraLabel(activeEra)}{loadingEra ? ' · changing archive' : ''}</small>
  </section>

  <fieldset class="lens-control" aria-label="Explore historical themes">
    <legend>Explore</legend>
    <div>
      {#each HISTORICAL_LENSES as lens (lens.id)}
        <button
          class:active={activeLens === lens.id}
          aria-pressed={activeLens === lens.id}
          title={`${lens.label}: ${lens.description}`}
          style={`--lens-accent: ${lensAccent(lens.id)}`}
          onclick={() => setLens(lens.id)}
        ><span aria-hidden="true">{lens.marker}</span>{lens.shortLabel}</button>
      {/each}
    </div>
  </fieldset>

  <fieldset class="layer-control" aria-label="Historical map layers">
    <legend>Map layers</legend>
    <button class:active={layerMode === 'combined'} aria-pressed={layerMode === 'combined'} onclick={() => setLayerMode('combined')}>Combined</button>
    <button class:active={layerMode === 'historical-detail'} aria-pressed={layerMode === 'historical-detail'} onclick={() => setLayerMode('historical-detail')}>Historical detail</button>
    <button class:active={layerMode === 'reviewed'} aria-pressed={layerMode === 'reviewed'} onclick={() => setLayerMode('reviewed')}>Reviewed reconstructions</button>
  </fieldset>

  <fieldset class="overlay-control" aria-label="Evidence overlays">
    <legend>Evidence overlay</legend>
    <button class:active={evidenceOverlay === 'none'} aria-pressed={evidenceOverlay === 'none'} onclick={() => setEvidenceOverlay('none')}>Off</button>
    <button class:active={evidenceOverlay === 'confidence'} aria-pressed={evidenceOverlay === 'confidence'} disabled={!layerCatalog} onclick={() => setEvidenceOverlay('confidence')}>Confidence</button>
    <button class:active={evidenceOverlay === 'provenance'} aria-pressed={evidenceOverlay === 'provenance'} disabled={!layerCatalog} onclick={() => setEvidenceOverlay('provenance')}>Provenance</button>
  </fieldset>

  <fieldset class="historical-map-control" aria-label="Optional historical map image">
    <legend>Historical map image · optional</legend>
    <select
      aria-label="Approved historical map image"
      disabled={!historicalMaps.length || historicalMapLoading}
      value={selectedHistoricalMapId}
      onchange={selectHistoricalMap}
    >
      {#if historicalMaps.length}
        {#each historicalMaps as historicalMap (historicalMap.map_id)}
          <option value={historicalMap.map_id}>{historicalMap.label}</option>
        {/each}
      {:else}
        <option>No rights-approved map in this release</option>
      {/if}
    </select>
    <button
      class:active={historicalMapVisible}
      aria-pressed={historicalMapVisible}
      disabled={!historicalMaps.length || historicalMapLoading}
      onclick={toggleHistoricalMap}
    >{historicalMapLoading ? 'Loading…' : historicalMapVisible ? 'Hide image' : 'Show image'}</button>
  </fieldset>

  {#if historicalMapError}
    <p class="historical-map-error" role="alert">{historicalMapError}</p>
  {/if}

  {#if historicalMapVisible && activeHistoricalMap}
    <section class="historical-map-card" aria-label="Historical map image details">
      <p>Historical map image · source depiction</p>
      <strong>{activeHistoricalMap.label}</strong>
      <dl>
        <div><dt>Depicted date</dt><dd>{activeHistoricalMap.depicted_date}</dd></div>
        <div><dt>Provider</dt><dd>{activeHistoricalMap.providers.join(', ')}</dd></div>
        <div><dt>Attribution</dt><dd>{activeHistoricalMap.required_statement}</dd></div>
        <div><dt>Image licence</dt><dd>{activeHistoricalMap.image_rights.license_id}</dd></div>
        <div><dt>Metadata licence</dt><dd>{activeHistoricalMap.metadata_rights.license_id}</dd></div>
        <div><dt>Georeference licence</dt><dd>{activeHistoricalMap.georeference_rights.license_id}</dd></div>
        <div><dt>Georeference confidence</dt><dd>{activeHistoricalMap.georeference_confidence.grade} · {activeHistoricalMap.georeference_confidence.rationale}</dd></div>
      </dl>
      <details>
        <summary>Known limitations</summary>
        <ul>
          {#each activeHistoricalMap.known_limitations as limitation}<li>{limitation}</li>{/each}
        </ul>
      </details>
      <p class="map-authority-warning">This scan records what the map depicts. History Joice does not treat it as geographically or politically authoritative, or as agreement with reviewed geometry or live OpenHistoricalMap context.</p>
      <a href={activeHistoricalMap.manifest_id} target="_blank" rel="noreferrer">Open the approved IIIF manifest <span aria-hidden="true">↗</span></a>
    </section>
  {/if}

  {#if !selected && !loading}
    <section class="orientation" aria-labelledby="orientation-title">
      <p id="orientation-title">{activeLensDefinition.label}</p>
      <span>{activeLensDefinition.description} Move the timeline or select a record to inspect its evidence.</span>
      {#if activeLens !== 'all'}
        <strong class:empty={activeLensRecordCount === 0}>
          {activeLensRecordCount === 0
            ? `No release records are classified in this lens at ${formatYear(selectedYear)}.`
            : `${activeLensRecordCount.toLocaleString()} release ${activeLensRecordCount === 1 ? 'record' : 'records'} classified at ${formatYear(selectedYear)}.`}
        </strong>
      {/if}
    </section>
  {/if}

  <div class="map-legend" aria-label="Map key">
    {#if evidenceOverlay !== 'none'}
      <span class="overlay-key"><i class="overlay-swatch"></i>{evidenceOverlay === 'confidence' ? 'Interpretive confidence' : 'Source provenance'}</span>
    {/if}
    {#if activeLens !== 'all'}
      <span class="theme-key"><i class="theme-swatch" style={`--lens-accent: ${lensAccent(activeLens)}`}></i>{activeLensDefinition.marker} Highlighted</span>
      <span class="background-key"><i class="background-swatch"></i>Other published history</span>
    {:else}
      <span class="control-key"><i class="control-swatch"></i>Control</span>
    {/if}
    <span class="soft-key"><i class="soft-swatch"></i>Approximate region or claim</span>
    <span class="gap-key"><i class="gap-swatch"></i>No coverage in this release</span>
  </div>

  {#if detailLimitReached}<p class="detail-limit" role="status">Reviewed geometry stops at zoom 7 · OHM detail continues</p>{/if}

  {#if selected}
    <aside class="reading-surface" id="reading-surface" aria-labelledby="record-title" tabindex="-1">
      <header class="record-header">
        <div>
          <p class="eyebrow">{selected.sourceRole === 'ohm' ? 'OpenHistoricalMap detail' : humanize(selected.kind)}</p>
          <h1 id="record-title">{selected.name}</h1>
          {#if alternateNames.length}<p class="alternate-names">Also {alternateNames.slice(0, 3).join(' · ')}</p>{/if}
        </div>
        <button class="close" onclick={clearSelection} aria-label="Close {selected.name}"><span aria-hidden="true">×</span></button>
      </header>

      <div class="record-scroll">
        <div class="record-dates"><time>{selected.dateLabel ?? formatRange(selected.validFrom, selected.validTo)}</time><span>{humanize(selected.reviewStatus)}</span></div>

        {#if activeLens !== 'all'}
          <section class="lens-reading" aria-label="Active historical lens">
            <p class="section-label">Viewed through {activeLensDefinition.label}</p>
            <p>{activeLensDefinition.description}</p>
            <small>Lenses are non-exclusive. The release must carry a structured, sourced assertion before a published record is highlighted.</small>
          </section>
        {/if}

        {#if selected.sourceRole === 'reviewed' && visibleThematicAssertions.length}
          <section class="lens-reading" aria-labelledby="classification-title">
            <p class="section-label" id="classification-title">Why this record is in {activeLens === 'all' ? 'these lenses' : `the ${activeLensDefinition.label} lens`}</p>
            {#each visibleThematicAssertions as assertion (assertion.assertion_id)}
              <article class="classification-assertion">
                <strong>{activeLens === 'all' ? `${humanize(assertion.theme)} · ` : ''}{humanize(assertion.subtheme)}</strong>
                <p>{assertion.rationale}</p>
                <small>
                  {humanize(assertion.classification_basis)} · {humanize(assertion.role)} · confidence {assertion.confidence.grade}
                  {#if assertion.matched_values.length} · matched {assertion.matched_values.map(humanize).join(', ')}{/if}
                </small>
                <details>
                  <summary>Rule and evidence</summary>
                  <p>{assertion.confidence.rationale}</p>
                  <small>{assertion.rule_id} · {formatRange(assertion.valid_from, assertion.valid_to)} · {humanize(assertion.review_status)}</small>
                  <ul>{#each assertion.source_refs as source}<li><a href={source.url} target="_blank" rel="noreferrer">{source.citation}</a></li>{/each}</ul>
                </details>
              </article>
            {/each}
          </section>
        {:else if selected.sourceRole === 'reviewed' && activeLens !== 'all' && !contentLoading}
          <section class="lens-reading" aria-label="No thematic assertion">
            <p class="section-label">Not classified in this lens</p>
            <p>This record remains visible as baseline geography, but this release has no sourced {activeLensDefinition.label.toLocaleLowerCase()} assertion for it.</p>
          </section>
        {/if}

        <section class="geometry-reading" aria-labelledby="geometry-title">
          <p class="section-label" id="geometry-title">{selected.sourceRole === 'ohm' ? 'What this map record means' : 'What the shape means'}</p>
          <p>{geometryStatement(selected.spatialMeaning)}</p>
        </section>

        {#if selected.sourceRole === 'reviewed' && selectedEvidenceAssertions.length}
          <section class="assertion-reading" aria-labelledby="assertion-title">
            <p class="section-label" id="assertion-title">Structured sourced facts</p>
            <p class="causal-caveat">These records are subject–predicate–object assertions, not generated narrative prose.</p>
            {#each selectedEvidenceAssertions as assertion (assertion.assertion_id)}
              <article class="evidence-assertion">
                <strong>{humanize(assertion.predicate)} · {assertionObjectLabel(assertion)}</strong>
                <small>{formatRange(assertion.valid_from, assertion.valid_to)} · {humanize(assertion.evidence_basis)} · confidence {assertion.confidence.grade}</small>
                <details>
                  <summary>Evidence and uncertainty</summary>
                  <p>{assertion.confidence.rationale}</p>
                  {#if assertion.temporal_uncertainty}<p>{assertion.temporal_uncertainty.rationale}</p>{/if}
                  <ul>{#each assertion.source_refs as source}<li><a href={source.url} target="_blank" rel="noreferrer">{source.citation}</a> · {source.license_id}</li>{/each}</ul>
                </details>
              </article>
            {/each}
          </section>
        {/if}

        {#if selected.sourceRole === 'reviewed' && selected.nameAttestation}
          <section class="name-reading" aria-label="Historical name attestation">
            <p class="section-label">Name at this date</p>
            <p><strong>{selected.nameAttestation.text}</strong> is the sourced label active in {formatYear(selectedYear)}.</p>
            <small>
              Language {selected.nameAttestation.language}
              · {humanize(selected.nameAttestation.name_kind)}
              · confidence {selected.nameAttestation.temporal_confidence}
              · {selected.nameAttestation.temporal_basis === 'attested' ? 'independently dated name' : 'date inherited from this feature interval'}
            </small>
          </section>
        {/if}

        {#if selected.sourceRole === 'ohm'}
          <section class="ohm-reading" aria-label="OpenHistoricalMap record provenance">
            <p class="section-label">Live historical detail</p>
            <p>This contributor record is shown as historical context. It has not been merged with, or reviewed as, the History Joice reconstruction.</p>
            <dl>
              <div><dt>Vector layer</dt><dd>{selected.ohm?.sourceLayer}</dd></div>
              {#if selected.ohm?.elementId}<div><dt>OHM/OSM ID</dt><dd>{selected.ohm.elementId}</dd></div>{/if}
              <div><dt>Date metadata</dt><dd>{selected.ohm?.datesComplete ? 'Start and end supplied' : 'Incomplete or undated'}</dd></div>
              {#if selected.ohm?.source}<div><dt>Source tag</dt><dd>{selected.ohm.source}</dd></div>{/if}
              {#if selected.ohm?.sourceRef}<div><dt>Source reference</dt><dd>{selected.ohm.sourceRef}</dd></div>{/if}
              {#if selected.ohm?.license}<div><dt>Licence override</dt><dd>{selected.ohm.license}</dd></div>{/if}
              {#if selected.ohm?.changeset}<div><dt>Changeset</dt><dd>{selected.ohm.changeset}</dd></div>{/if}
            </dl>
            <p class="join-note">The live tile does not always expose complete element provenance or per-feature licence tags. A future curated OHM snapshot must retain and validate those fields before publication.</p>
            <a href={OHM_COPYRIGHT_URL} target="_blank" rel="noreferrer">OpenHistoricalMap copyright and attribution <span aria-hidden="true">↗</span></a>
          </section>
        {:else if contentLoading}
          <div class="content-loading" aria-live="polite"><span></span>Checking this release for linked reading material…</div>
        {:else if contentError}
          <p class="content-error" role="alert">{contentError}</p>
        {:else}
          {#if selectedEntity && Object.values(selectedEntity.descriptions).length}
            <section class="source-extract compact-extract" aria-labelledby="wikidata-heading">
              <p class="section-label" id="wikidata-heading">Wikidata description</p>
              <p>{selectedEntity.descriptions.en ?? Object.values(selectedEntity.descriptions)[0]}</p>
              {#if selectedEntity.links.wikidata}<a href={selectedEntity.links.wikidata} target="_blank" rel="noreferrer">Open the Wikidata item <span aria-hidden="true">↗</span></a>{/if}
            </section>
          {/if}

          {#each selectedDossiers as dossier (dossier.dossier_id)}
            <section class="source-extract" aria-labelledby={`dossier-${dossier.page_id}`}>
              <p class="section-label" id={`dossier-${dossier.page_id}`}>{dossierLabel(dossier)}</p>
              <h2>{dossier.title}</h2>
              {#each dossier.extract.trim().split('\n').filter(Boolean) as paragraph}<p>{paragraph}</p>{/each}
              <footer>
                <span>{dossier.source_ref.citation} · {dossier.source_ref.license_id}</span>
                <a href={dossier.url} target="_blank" rel="noreferrer">Read at source <span aria-hidden="true">↗</span></a>
                {#if dossier.revision_id}<small>Revision {dossier.revision_id}{dossier.revision_timestamp ? ` · ${new Date(dossier.revision_timestamp).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}</small>{/if}
              </footer>
            </section>
          {/each}

          {#if !selectedDossiers.length}
            <section class="empty-reading" aria-label="Reading material unavailable">
              <p class="section-label">Reading dossier</p>
              <p>This release maps the record but does not publish a dossier linked to this exact feature. Nothing has been inferred or filled in.</p>
              {#if selectedLink?.missing_entity_ids.length}<p class="join-note">The feature-to-entity join is published, but metadata for {selectedLink.missing_entity_ids.join(', ')} was not enriched in this build.</p>{/if}
              {#if selected.wikidataId}<a href={`https://www.wikidata.org/wiki/${selected.wikidataId}`} target="_blank" rel="noreferrer">Open {selected.wikidataId} on Wikidata <span aria-hidden="true">↗</span></a>{/if}
            </section>
          {/if}
        {/if}

        {#if selectedWikiContext?.items.length}
          <section class="wiki-context" aria-labelledby="wiki-context-title">
            <p class="section-label" id="wiki-context-title">Historical context near this record</p>
            <p class="causal-caveat">These people, events, places, institutions and themes are a bounded, date-aware selection of explicit Wikidata relationships. A connection is not a claim of causation.</p>
            {#each selectedWikiContext.items as item (item.context_entity_id)}
              <article class="context-card">
                <span>{humanize(item.role)} · {item.relationship_types.map(humanize).join(' · ')}</span>
                <strong>{contextName(item.entity)}</strong>
                <p>{contextDescription(item.entity)}</p>
                {#if item.valid_from !== null || item.valid_to !== null}<small>{formatRange(item.valid_from ?? item.valid_to ?? selectedYear, item.valid_to ?? item.valid_from ?? selectedYear)}</small>{/if}
                <small>{item.source_strength === 'referenced_statement' ? 'Wikidata statement with retained reference' : 'Wikidata statement; no reference returned'}</small>
                {#if item.dossiers[0]}
                  <details>
                    <summary>Read the saved Wikipedia introduction</summary>
                    <p>{item.dossiers[0].extract}</p>
                    <a href={item.dossiers[0].url} target="_blank" rel="noreferrer">{item.dossiers[0].title} · revision {item.dossiers[0].revision_id ?? 'recorded in release'} <span aria-hidden="true">↗</span></a>
                  </details>
                {:else if item.entity.sitelinks?.en}
                  <a href={item.entity.sitelinks.en.url} target="_blank" rel="noreferrer">Open the linked Wikipedia page <span aria-hidden="true">↗</span></a>
                {/if}
              </article>
            {/each}
            {#if selectedWikiContext.total_items > selectedWikiContext.items.length}<p class="join-note">{selectedWikiContext.total_items - selectedWikiContext.items.length} lower-ranked connections are retained in the release shard but collapsed in this first reading view.</p>{/if}
          </section>
        {/if}

        {#if selectedPeriods.length}
          <section class="chronology-reading" aria-labelledby="chronology-title">
            <p class="section-label" id="chronology-title">Named periods in use here</p>
            <p class="causal-caveat">These PeriodO entries are attributed scholarly definitions that overlap at {formatYear(selectedYear)}. They are not one universal timeline.</p>
            {#each selectedPeriods.slice(0, 12) as period (period.period_id)}
              <article class="period-definition">
                <span>{period.start_label} – {period.stop_label}</span>
                <strong>{periodLabel(period)}</strong>
                <small>{period.spatial_coverage_description ?? period.spatial_coverage.map((place) => place.label).join(', ')}</small>
                <a href={period.source_ref.url} target="_blank" rel="noreferrer">{period.authority_citation} <span aria-hidden="true">↗</span></a>
              </article>
            {/each}
            {#if selectedPeriods.length > 12}<p class="join-note">{selectedPeriods.length - 12} additional overlapping definitions are present in this release; the reading UI intentionally starts with the most specific twelve.</p>{/if}
          </section>
        {/if}

        {#if selectedCausalClaims.length || selectedCausalPaths.length}
          <section class="causal-reading" aria-labelledby="causal-title">
            <p class="section-label" id="causal-title">Interpretive pathways</p>
            <p class="causal-caveat">These are attributed historical arguments, not automatic facts or a single authoritative chain.</p>
            {#each selectedCausalPaths as path (path.path_id)}
              <div class="causal-path">
                <span>Curated pathway · {humanize(path.review_status)}</span>
                <strong>{path.titles.en ?? Object.values(path.titles)[0]}</strong>
                <p>{path.summaries.en ?? Object.values(path.summaries)[0]}</p>
                <small>{path.perspective} · {path.claim_ids.length} linked claims</small>
              </div>
            {/each}
            {#each selectedCausalClaims as claim (claim.claim_id)}
              <article class="causal-claim">
                <span>{humanize(claim.relationship)} · {humanize(claim.mechanism_type)}</span>
                <p>{causalSummary(claim)}</p>
                <small>{formatRange(claim.cause_period.valid_from, claim.cause_period.valid_to)} → {formatRange(claim.effect_period.valid_from, claim.effect_period.valid_to)}</small>
                <small>{claim.perspective} · confidence {claim.confidence.grade} · {claim.source_refs.length} source{claim.source_refs.length === 1 ? '' : 's'}</small>
                <details>
                  <summary>Evidence and authorship</summary>
                  <p>{claim.confidence.rationale}</p>
                  <p>Authored by {claim.authored_by}{claim.reviewed_by.length ? ` · reviewed by ${claim.reviewed_by.join(', ')}` : ''}</p>
                  <ul>{#each claim.source_refs as source}<li><a href={source.url} target="_blank" rel="noreferrer">{source.citation}</a></li>{/each}</ul>
                </details>
              </article>
            {/each}
          </section>
        {/if}

        {#if selected.sourceRole === 'reviewed'}
        <details class="evidence">
          <summary><span>Evidence and uncertainty</span><small>3 confidence readings</small></summary>
          <div class="confidence-grid">
            <div><span>When</span><strong>{selected.temporalConfidence}</strong><small>{confidenceText(selected.temporalConfidence)}</small></div>
            <div><span>Where</span><strong>{selected.spatialConfidence}</strong><small>{confidenceText(selected.spatialConfidence)}</small></div>
            <div><span>Interpretation</span><strong>{selected.interpretiveConfidence}</strong><small>{confidenceText(selected.interpretiveConfidence)}</small></div>
          </div>
          {#if selected.disputeGroup}<p class="dispute-note"><strong>Alternatives exist.</strong> This feature belongs to dispute group {selected.disputeGroup}; the map does not average competing reconstructions.</p>{/if}
          {#if selectedSource}
            <div class="record-source">
              <p class="section-label">Geometry source</p>
              <a href={selectedSource.url} target="_blank" rel="noreferrer"><strong>{selectedSource.title}</strong><span>{selectedSource.publisher} · {selectedSource.license_id} · {selectedSource.version ?? 'release snapshot'}</span></a>
            </div>
          {/if}
          <p class="precision-note">This global archive stops at zoom 7. Enlarging a shape does not make its source more precise.</p>
        </details>
        {/if}

        {#if selectedRelationships.length}
          <section class="connections" aria-labelledby="connections-title">
            <p class="section-label" id="connections-title">Connected records</p>
            {#each selectedRelationships as relationship}
              {@const relatedEntity = linkedEntities.find((entity) => entity.entity_id === relationship.target_entity_id)}
              {@const relatedRecord = searchIndex.find((record) => record.entity_id === relationship.target_entity_id || record.entity_id === relationship.target_entity_id.replace('wikidata:', ''))}
              <div>
                <span>{humanize(relationship.relation_type)}</span>
                <strong>{relatedEntity?.names.en ?? Object.values(relatedEntity?.names ?? {})[0] ?? relationship.target_entity_id}</strong>
                <small>Relationship published with this entity’s Wikidata metadata.</small>
                {#if relatedRecord}<button onclick={() => chooseSearchResult(relatedRecord)}>Show connected record →</button>{/if}
              </div>
            {/each}
          </section>
        {/if}

        {#if selectedRegionalContext?.entries.length}
          <section class="regional-context" aria-labelledby="regional-context-title">
            <p class="section-label" id="regional-context-title">In this area at {formatYear(selectedYear)}</p>
            <p class="causal-caveat">This is a discovery result from a 10° grid cell, not a historical region or a claim that every record was locally influential.</p>
            {#each selectedRegionalContext.entries.slice(0, 20) as entry (entry.entry_id)}
              {@const record = regionalRecord(entry)}
              {@const dossier = entry.dossier_ids.map((id) => selectedRegionalContext?.dossiers.get(id)).find(Boolean)}
              <article class="regional-card">
                <span>{humanize(entry.kind)} · {entry.spatial_basis === 'feature_geometry_intersection' ? 'reviewed geometry intersects cell' : 'dated Wikidata coordinate'}</span>
                <strong>{regionalName(entry)}</strong>
                <small>{formatRange(entry.valid_from, entry.valid_to)} · {entry.source_ids.join(', ')}</small>
                {#if record}
                  <button onclick={() => chooseSearchResult(record)}>Open mapped record →</button>
                {:else if dossier}
                  <a href={dossier.url} target="_blank" rel="noreferrer">Read saved {dossier.language.toUpperCase()} Wikipedia introduction <span aria-hidden="true">↗</span></a>
                {/if}
              </article>
            {/each}
            {#if selectedRegionalContext.entries.length > 20}<p class="join-note">{selectedRegionalContext.entries.length - 20} additional results remain in this bounded release response.</p>{/if}
          </section>
        {/if}

        {#if elsewhere.length}
          <section class="elsewhere" aria-labelledby="elsewhere-title">
            <p class="section-label" id="elsewhere-title">Elsewhere in {formatYear(selectedYear)}</p>
            <p>Other mapped records active in the same year, chosen from different longitudes.</p>
            <div>
              {#each elsewhere as record}<button onclick={() => chooseSearchResult(record)}><span>{displayName(record)}</span><small>{formatRange(record.valid_from, record.valid_to)}</small></button>{/each}
            </div>
          </section>
        {/if}

        {#if selected.sourceRole === 'reviewed'}
          <a class="text-record-link" href={`/browse?year=${selectedYear}&entity=${encodeURIComponent(selected.entityId ?? '')}&q=${encodeURIComponent(selected.name)}${activeLens !== 'all' ? `&lens=${activeLens}` : ''}`}>Open this record in the text view <span aria-hidden="true">→</span></a>
        {/if}
      </div>
    </aside>
  {/if}

  {#if loading}<div class="loading-state"><span></span><p>Opening release data</p></div>{/if}
  {#if errorMessage}<div class="error-toast" role="alert"><div><strong>Map unavailable</strong><p>{errorMessage}</p></div><button onclick={() => (errorMessage = '')} aria-label="Dismiss error">×</button></div>{/if}

  <section class="timeline" id="timeline" tabindex="-1" aria-label="Historical timeline">
    <div class="timeline-primary">
      <button class="play" onclick={togglePlayback} aria-label={playing ? 'Pause changing years' : 'Play changing years'} aria-pressed={playing}>
        {#if playing}<span class="pause-icon" aria-hidden="true"></span>{:else}<span class="play-icon" aria-hidden="true"></span>{/if}
      </button>
      <button class="year-button" onclick={openYearEditor} aria-expanded={yearEditorOpen} aria-controls="year-editor"><span>Selected year</span><strong>{formatYear(selectedYear)}</strong><small>Enter exact year</small></button>
      {#if yearEditorOpen}
        <form class="year-editor" id="year-editor" onsubmit={submitYear}>
          <label><span>Year</span><input bind:this={exactYearInput} bind:value={yearDraft} inputmode="numeric" aria-describedby={yearInputError ? 'year-error' : undefined} /></label>
          <label><span>Era</span><select bind:value={yearDraftEra}><option>BCE</option><option>CE</option></select></label>
          <button type="submit">Go</button>
          <button type="button" class="editor-close" onclick={() => (yearEditorOpen = false)} aria-label="Close exact year entry">×</button>
          {#if yearInputError}<p id="year-error" role="alert">{yearInputError}</p>{/if}
        </form>
      {/if}
    </div>

    <div class="timeline-scale">
      <input
        type="range"
        min="0"
        max={TIMELINE_MAX}
        value={timelinePosition}
        oninput={handleTimeline}
        onkeydown={handleTimelineKey}
        aria-label="Selected historical year"
        aria-valuemin={MINIMUM_YEAR}
        aria-valuemax={MAXIMUM_YEAR}
        aria-valuenow={selectedYear}
        aria-valuetext={formatYear(selectedYear)}
      />
      <div class="archive-bands" aria-hidden="true">{#each TIMELINE_BANDS as band}<span>{band.label}</span>{/each}</div>
      <div class="timeline-ticks" aria-hidden="true"><span>3400 BCE</span><span>1 CE</span><span>500</span><span>1500</span><span>1800</span><span>Now</span></div>
    </div>

    <div class="year-steps" aria-label="Change the year in large steps">
      <button onclick={() => setYear(stepYear(selectedYear, -100))} aria-label="Go back 100 years">−100</button>
      <button onclick={() => setYear(stepYear(selectedYear, 100))} aria-label="Go forward 100 years">+100</button>
    </div>

    <p class="map-credit"><a href="https://www.openhistoricalmap.org/copyright" target="_blank" rel="noreferrer">© OpenHistoricalMap contributors</a><span> · modern reference geography </span><a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">Natural Earth</a><span> · reviewed geometry </span><a href="https://seshatdatabank.info/" target="_blank" rel="noreferrer">Seshat</a><span> / </span><a href="https://github.com/JustusBuitelaar/cliopatria" target="_blank" rel="noreferrer">Cliopatria</a></p>
  </section>

  <p class="sr-only" aria-live="polite">{mapAnnouncement}</p>

  <dialog class="about-dialog" bind:this={aboutDialog} onclick={(event) => event.currentTarget === event.target && aboutDialog.close()}>
    <div class="dialog-inner">
      <header><div><p class="eyebrow">Read the map critically</p><h2>This map shows source claims, not settled borders.</h2></div><button class="close" onclick={() => aboutDialog.close()} aria-label="Close about this map">×</button></header>
      <div class="dialog-grid">
        <div class="method-copy">
          <p>Each shape preserves a source’s interpretation and date interval. Control could overlap, change seasonally, or be understood differently by another source. The interface never interpolates a new boundary between dated geometries.</p>
          <p>Hatched cells mean this release has no mapped coverage for that place and year. They do not mean nobody lived there or nothing happened there.</p>
          <p>OpenHistoricalMap supplies live, contributor-built historical detail and labels. The quiet History Joice layer remains a separate reviewed reconstruction; overlapping geometries are not merged or presented as agreement.</p>
          <p>Natural Earth land and physical water are modern reference geography for orientation. An optional historical map image remains a separately attributed source depiction, never a substitute for reviewed reconstruction geometry.</p>
          <p>The thematic lenses are non-exclusive discovery views. They use reviewed theme tags or explicit source feature types; a record may appear in several lenses, and an empty lens means this release has no classified record rather than no history.</p>
          <h3>Visual key</h3>
          <ul class="visual-key">
            <li><i class="control-swatch"></i><span><strong>Territorial control</strong> — reconstructed area with a firmer edge</span></li>
            <li><i class="soft-swatch"></i><span><strong>Region, influence or claim</strong> — softer fill and broken edge</span></li>
            <li><i class="contested-swatch"></i><span><strong>Contested interpretation</strong> — a distinct broken red edge</span></li>
            <li><i class="gap-swatch"></i><span><strong>Coverage gap</strong> — absent from this release</span></li>
          </ul>
          <p class="archive-note">The four equal-width timeline bands are data archives, not a claim that one region’s historical periodisation applies worldwide.</p>
        </div>
        <aside class="release-notes">
          <div class="release-stats">
            <div><span>Release</span><strong>{release?.manifest.build_id ?? '—'}</strong></div>
            <div><span>Published</span><strong>{release ? new Date(release.manifest.generated_at).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}</strong></div>
            <div><span>Map records</span><strong>{quality?.accepted_feature_count?.toLocaleString() ?? '—'}</strong></div>
            <div><span>Rejected</span><strong>{quality?.rejected_record_count?.toLocaleString() ?? release?.manifest.rejected_record_count ?? '—'}</strong></div>
          </div>
          <h3>Sources in this release</h3>
          <div class="source-list">
            <a href="https://www.openhistoricalmap.org/copyright" target="_blank" rel="noreferrer"><span>OpenHistoricalMap live detail</span><small>OpenHistoricalMap contributors<br />CC0 by default; element overrides may apply</small></a>
            {#each attributions ?? release?.manifest.sources ?? [] as source (source.source_id)}
              <a href={source.url} target="_blank" rel="noreferrer"><span>{source.title}</span><small>{source.publisher}<br />{source.license_id}</small></a>
            {/each}
          </div>
          <p class="release-id">Schema {release?.manifest.schema_version ?? '—'} · immutable build {release?.manifest.build_id ?? '—'}</p>
        </aside>
      </div>
    </div>
  </dialog>
</main>

<svelte:window onkeydown={(event) => {
  if (event.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'SELECT') {
    event.preventDefault();
    searchInput?.focus();
  }
  if (event.key === 'Escape' && yearEditorOpen) yearEditorOpen = false;
}} />

<style>
  :global(*) { box-sizing: border-box; }
  :global(:root) {
    --reader-width: 448px;
    --timeline-height: 128px;
    font-family: 'Manrope', 'Inter', system-ui, sans-serif;
    color: #172321;
    background: #d8ddd4;
    font-synthesis: none;
  }
  :global(html), :global(body) { margin: 0; width: 100%; height: 100%; overflow: hidden; }
  :global(button), :global(input), :global(select) { font: inherit; }
  :global(button), :global(a) { -webkit-tap-highlight-color: transparent; }
  :global(button:focus-visible), :global(a:focus-visible), :global(input:focus-visible), :global(select:focus-visible), :global(summary:focus-visible) { outline: 2px solid #a93f5a; outline-offset: 3px; }
  :global(.maplibregl-ctrl-bottom-right) { right: 13px; bottom: calc(var(--timeline-height) + 10px); }
  :global(.maplibregl-ctrl-group) { overflow: hidden; border: 1px solid #5d716d; border-radius: 1px; box-shadow: none; }
  :global(.maplibregl-ctrl-group button) { background-color: #fffdf7; }
  :global(.maplibregl-ctrl-attrib) { font-size: 10px; opacity: .82; }
  :global(.maplibregl-ctrl-attrib.maplibregl-compact) { border-radius: 1px; background: #fffdf7; }

  .skip-link { position: fixed; z-index: 100; top: 8px; left: 8px; transform: translateY(-150%); padding: 10px 14px; background: #f8f7f2; color: #17211f; border: 2px solid #173f3d; }
  .skip-link:focus { transform: none; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .app-shell { position: relative; width: 100vw; height: 100dvh; overflow: hidden; background: #d8ddd4; }
  .map { position: absolute; inset: 0; }

  .masthead { position: absolute; z-index: 7; inset: 0 0 auto; height: 58px; display: grid; grid-template-columns: 210px minmax(300px, 520px) 1fr; align-items: center; gap: 30px; padding: 0 22px; border-bottom: 1px solid #b8b2a6; background: #fffdf7; transition: right .3s ease; }
  .reading .masthead { right: var(--reader-width); }
  .brand { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; width: fit-content; color: #16201e; text-decoration: none; }
  .brand > span { font: 19px/1 'Instrument Serif', Georgia, serif; letter-spacing: -.015em; }
  .brand > small { color: #64716d; font-size: 9px; font-weight: 600; letter-spacing: .04em; }
  .search { position: relative; display: flex; align-items: center; height: 40px; border-bottom: 1px solid #405b58; }
  .search > svg { flex: none; width: 17px; height: 17px; fill: none; stroke: #45514f; stroke-width: 1.5; }
  .search input { min-width: 0; flex: 1; height: 100%; padding: 0 10px; border: 0; outline: 0; background: transparent; color: #17201f; font-size: 12px; }
  .search input::placeholder { color: #6e7774; }
  .search kbd { border: 1px solid #b8bcb8; padding: 2px 6px; color: #707875; font: 10px 'DM Mono', monospace; }
  .clear-search { width: 30px; height: 30px; border: 0; background: none; color: #5d6764; cursor: pointer; font-size: 18px; }
  .search-results { position: absolute; top: 47px; left: -12px; right: -12px; padding: 8px 12px 10px; border: 1px solid #a9aeaa; border-top: 2px solid #a93f5a; background: #fffdf7; box-shadow: 0 14px 36px rgba(22, 31, 29, .14); }
  .search-results button { width: 100%; min-height: 53px; display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 8px 7px; border: 0; border-top: 1px solid #d6d7d2; background: transparent; color: inherit; cursor: pointer; text-align: left; }
  .search-results button:first-child { border-top: 0; }
  .search-results button:hover, .search-results button.active { background: #e9ebe6; }
  .search-results button > span { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .search-results strong { overflow: hidden; text-overflow: ellipsis; font-size: 14px; font-weight: 600; white-space: nowrap; }
  .search-results small, .search-results time { color: #69716e; font: 10px/1.35 'DM Mono', monospace; letter-spacing: .01em; }
  .search-results time { flex: none; text-align: right; }
  .search-results p { margin: 13px 7px; color: #606966; font-size: 12px; }
  .utility-nav { justify-self: end; display: flex; align-items: center; gap: 22px; }
  .utility-nav a, .utility-nav button { padding: 4px 0; border: 0; border-bottom: 1px solid transparent; background: none; color: #34413e; cursor: pointer; font-size: 11px; font-weight: 550; letter-spacing: .01em; text-decoration: none; white-space: nowrap; }
  .utility-nav a:hover, .utility-nav button:hover { border-color: #34413e; }

  .date-readout { position: absolute; z-index: 4; top: 78px; left: 24px; display: flex; flex-direction: column; pointer-events: none; color: #17201f; text-shadow: 0 1px 9px #e7e9e5; }
  .date-readout > span, .date-readout small { font: 10px/1.3 'DM Mono', monospace; letter-spacing: .045em; }
  .date-readout strong { margin: 3px 0 5px; font: 36px/.95 'Instrument Serif', Georgia, serif; font-weight: 400; letter-spacing: -.02em; }
  .date-readout small { color: #485350; letter-spacing: .03em; }

  .lens-control { position: absolute; z-index: 5; top: 157px; left: 24px; display: flex; align-items: stretch; margin: 0; padding: 0; border: 1px solid rgba(61, 71, 68, .48); background: rgba(255, 253, 247, .95); }
  .lens-control legend { display: flex; align-items: center; padding: 0 10px; border-right: 1px solid rgba(61, 71, 68, .25); color: #754259; font: 8px 'DM Mono', monospace; letter-spacing: .06em; text-transform: uppercase; }
  .lens-control > div { display: flex; }
  .lens-control button { min-height: 36px; display: inline-flex; align-items: center; gap: 5px; padding: 0 11px; border: 0; border-left: 1px solid rgba(61, 71, 68, .18); background: transparent; color: #4d5855; cursor: pointer; font: 9px/1.2 'DM Mono', monospace; }
  .lens-control button span { color: var(--lens-accent); font-size: 10px; }
  .lens-control button:first-child { border-left: 0; }
  .lens-control button:hover { background: #ebece6; }
  .lens-control button.active { background: var(--lens-accent); color: #fffdf7; }
  .lens-control button.active span { color: #fffdf7; }

  .layer-control { position: absolute; z-index: 5; top: 205px; left: 24px; display: flex; margin: 0; padding: 0; border: 1px solid rgba(61, 71, 68, .48); background: rgba(255, 253, 247, .94); }
  .layer-control legend { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .layer-control button { min-height: 36px; padding: 0 12px; border: 0; border-left: 1px solid rgba(61, 71, 68, .25); background: transparent; color: #4d5855; cursor: pointer; font: 10px/1.2 'DM Mono', monospace; letter-spacing: .01em; }
  .layer-control button:first-of-type { border-left: 0; }
  .layer-control button:hover { background: #ebece6; }
  .layer-control button.active { background: #314743; color: #fffdf7; }
  .overlay-control { position: absolute; z-index: 5; top: 249px; left: 24px; display: flex; margin: 0; padding: 0; border: 1px solid rgba(61, 71, 68, .4); background: rgba(255, 253, 247, .94); }
  .overlay-control legend { display: flex; align-items: center; padding: 0 9px; color: #5f6764; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .overlay-control button { min-height: 32px; padding: 0 10px; border: 0; border-left: 1px solid rgba(61, 71, 68, .2); background: transparent; color: #4d5855; cursor: pointer; font: 9px 'DM Mono', monospace; }
  .overlay-control button.active { background: #596b67; color: #fffdf7; }
  .overlay-control button:disabled { opacity: .45; cursor: wait; }
  .historical-map-control { position: absolute; z-index: 6; top: 289px; left: 24px; display: flex; align-items: stretch; max-width: min(560px, calc(100vw - 48px)); margin: 0; padding: 0; border: 1px solid rgba(102, 72, 49, .48); background: rgba(255, 250, 239, .96); }
  .historical-map-control legend { display: flex; align-items: center; padding: 0 9px; color: #75533b; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .historical-map-control select { min-width: 190px; max-width: 290px; min-height: 32px; padding: 0 28px 0 8px; border: 0; border-left: 1px solid rgba(102, 72, 49, .22); border-radius: 0; background: transparent; color: #493d35; font: 9px 'DM Mono', monospace; text-overflow: ellipsis; }
  .historical-map-control button { min-height: 32px; padding: 0 10px; border: 0; border-left: 1px solid rgba(102, 72, 49, .22); background: transparent; color: #493d35; cursor: pointer; font: 9px 'DM Mono', monospace; }
  .historical-map-control button.active { background: #75533b; color: #fffdf7; }
  .historical-map-control button:disabled, .historical-map-control select:disabled { opacity: .5; cursor: not-allowed; }
  .historical-map-card { position: absolute; z-index: 6; top: 331px; left: 24px; width: min(360px, calc(100vw - 48px)); max-height: calc(100dvh - var(--timeline-height) - 348px); overflow-y: auto; padding: 14px 15px; border: 1px solid rgba(102, 72, 49, .5); border-top: 2px solid #8c6245; background: rgba(255, 251, 241, .97); box-shadow: 0 12px 30px rgba(37, 28, 22, .1); }
  .historical-map-card > p:first-child { margin: 0 0 5px; color: #79583f; font: 8px 'DM Mono', monospace; letter-spacing: .05em; text-transform: uppercase; }
  .historical-map-card > strong { display: block; font: 20px/1.15 'Instrument Serif', Georgia, serif; font-weight: 500; }
  .historical-map-card dl { margin: 11px 0; border-top: 1px solid #d7cbbd; }
  .historical-map-card dl div { display: grid; grid-template-columns: 112px 1fr; gap: 9px; padding: 6px 0; border-bottom: 1px solid #e0d7cd; }
  .historical-map-card dt { color: #766a61; font: 7px/1.35 'DM Mono', monospace; text-transform: uppercase; }
  .historical-map-card dd { margin: 0; color: #403832; font-size: 9px; line-height: 1.45; }
  .historical-map-card details { color: #4f443c; font-size: 9px; line-height: 1.5; }
  .historical-map-card summary { cursor: pointer; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .historical-map-card ul { margin: 8px 0; padding-left: 18px; }
  .historical-map-card .map-authority-warning { margin: 11px 0; padding: 9px; border-left: 2px solid #8c6245; background: #eee5d9; color: #4d4139; font-size: 9px; line-height: 1.5; }
  .historical-map-card a { color: #594534; font-size: 9px; font-weight: 600; text-underline-offset: 2px; }
  .historical-map-error { position: absolute; z-index: 7; top: 331px; left: 24px; max-width: 360px; margin: 0; padding: 9px 12px; border: 1px solid #9d5041; background: #f4e8e2; color: #692e27; font-size: 9px; }

  .orientation { position: absolute; z-index: 4; left: 24px; bottom: calc(var(--timeline-height) + 12px); width: 254px; padding: 12px 14px 13px; border: 1px solid rgba(61, 71, 68, .22); border-top: 1px solid #9b4960; background: rgba(255, 253, 247, .94); box-shadow: 0 10px 28px rgba(28, 37, 34, .05); }
  .orientation > p, .eyebrow, .section-label { margin: 0 0 8px; color: #754259; font: 10px/1.25 'DM Mono', monospace; letter-spacing: .045em; }
  .orientation > span { display: block; color: #4d5855; font-size: 12px; line-height: 1.55; }
  .orientation > strong { display: block; margin-top: 10px; padding-top: 9px; border-top: 1px solid rgba(61, 71, 68, .18); color: #31534a; font: 9px/1.45 'DM Mono', monospace; }
  .orientation > strong.empty { color: #88485b; }

  .map-legend { position: absolute; z-index: 4; right: 22px; bottom: var(--timeline-height); display: flex; gap: 17px; padding: 9px 11px; background: rgba(255, 253, 247, .93); border: 1px solid rgba(61, 71, 68, .18); color: #3e4946; font: 9px 'DM Mono', monospace; box-shadow: 0 7px 24px rgba(28, 37, 34, .04); }
  .reading .map-legend { right: calc(var(--reader-width) + 22px); }
  .map-legend span { display: inline-flex; align-items: center; gap: 6px; }
  .overlay-swatch { width: 14px; height: 8px; background: linear-gradient(90deg, #236b55, #b08a42, #a95d4f); }
  .control-swatch, .theme-swatch, .background-swatch, .soft-swatch, .contested-swatch, .gap-swatch { display: inline-block; flex: none; width: 21px; height: 10px; }
  .control-swatch { border: 1px solid #625d59; background: rgba(118, 88, 79, .11); }
  .theme-swatch { border: 2px solid var(--lens-accent); background: color-mix(in srgb, var(--lens-accent) 24%, transparent); }
  .background-swatch { border: 1px solid rgba(98, 93, 89, .25); background: rgba(118, 88, 79, .025); }
  .soft-swatch { border: 1px dashed #68766f; background: rgba(95, 113, 107, .075); }
  .contested-swatch { border: 1px dashed #8e5a50; background: rgba(142, 90, 80, .055); }
  .gap-swatch { opacity: .72; background-image: radial-gradient(circle, #3d4840 .8px, transparent 1px); background-size: 6px 6px; }
  .detail-limit { position: absolute; z-index: 5; top: 72px; right: 15px; margin: 0; padding: 7px 9px; border: 1px solid #9fa5a1; background: #f5f4ef; color: #4b5653; font: 8px 'DM Mono', monospace; text-transform: uppercase; }

  .reading-surface { position: absolute; z-index: 9; inset: 0 0 auto auto; width: var(--reader-width); max-height: calc(100dvh - var(--timeline-height)); display: flex; flex-direction: column; overflow: hidden; border-left: 1px solid rgba(70, 82, 78, .34); background: #fffdf8; box-shadow: -18px 0 48px rgba(22, 31, 29, .09); }
  .record-header { position: relative; flex: none; display: flex; justify-content: space-between; gap: 24px; padding: 34px 30px 27px; border-bottom: 1px solid rgba(79, 91, 87, .2); }
  .record-header::before { content: ''; position: absolute; inset: 0 auto auto 30px; width: 42px; height: 2px; background: #9f4059; }
  .record-header .eyebrow { margin-bottom: 10px; color: #8a4055; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; }
  .record-header h1 { margin: 0; font-family: 'Instrument Serif', Georgia, serif; font-size: 39px; line-height: 1.01; font-weight: 400; letter-spacing: -.028em; }
  .alternate-names { margin: 12px 0 0; color: #68716e; font: 10px/1.55 'DM Mono', monospace; }
  .close { flex: none; width: 34px; height: 34px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 50%; background: #f0efe9; color: #40504c; cursor: pointer; font: 19px/1 'Manrope', sans-serif; transition: background .18s ease, color .18s ease, transform .18s ease; }
  .close:hover { transform: rotate(4deg); background: #263f3c; color: #fff; }
  .record-scroll { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; scrollbar-color: #afb5b0 transparent; }
  .record-dates { display: flex; justify-content: space-between; align-items: center; padding: 15px 30px; border-bottom: 1px solid rgba(79, 91, 87, .16); background: #f7f5ef; color: #53615d; font: 10px 'DM Mono', monospace; letter-spacing: .025em; text-transform: uppercase; }
  .record-dates span { display: inline-flex; align-items: center; gap: 7px; color: #9b493e; }
  .record-dates span::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; opacity: .75; }
  .geometry-reading, .lens-reading, .assertion-reading, .name-reading, .ohm-reading, .source-extract, .empty-reading, .elsewhere, .connections, .causal-reading, .chronology-reading, .wiki-context, .regional-context { padding: 26px 30px 27px; border-bottom: 1px solid rgba(79, 91, 87, .18); }
  .evidence-assertion { display: grid; gap: 5px; padding: 12px 0; border-top: 1px solid rgba(79, 91, 87, .16); }
  .evidence-assertion strong { color: #263b37; font-size: 13px; }
  .evidence-assertion small { color: #68726f; font: 9px/1.55 'DM Mono', monospace; }
  .evidence-assertion details p, .evidence-assertion details li { color: #47534f; font-size: 11px; line-height: 1.55; }
  .evidence-assertion a { color: #245b66; }
  .lens-reading { background: #f1ecea; }
  .lens-reading > p:not(.section-label) { margin: 0 0 8px; color: #394542; font-size: 13px; line-height: 1.55; }
  .lens-reading small { color: #67716e; font: 9px/1.55 'DM Mono', monospace; }
  .classification-assertion { margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(79, 91, 87, .18); }
  .classification-assertion strong { display: block; margin-bottom: 5px; color: #263d39; font: 15px/1.25 'Instrument Serif', Georgia, serif; }
  .classification-assertion p { margin: 0 0 7px; color: #394542; font-size: 12px; line-height: 1.55; }
  .classification-assertion details { margin-top: 9px; }
  .classification-assertion summary { cursor: pointer; color: #234c49; font-size: 10px; font-weight: 600; }
  .classification-assertion ul { margin: 8px 0 0; padding-left: 17px; }
  .classification-assertion a { color: #234c49; text-underline-offset: 2px; }
  .geometry-reading > p:last-child, .empty-reading > p:last-of-type { margin: 0; color: #33413d; font-family: 'Instrument Serif', Georgia, serif; font-size: 22px; line-height: 1.36; letter-spacing: -.008em; }
  .source-extract { background: #fbfaf6; }
  .source-extract h2 { margin: 0 0 13px; font-size: 21px; line-height: 1.15; font-weight: 550; letter-spacing: -.015em; }
  .source-extract > p:not(.section-label) { margin: 0 0 13px; color: #303b38; font-family: Georgia, serif; font-size: 14px; line-height: 1.65; }
  .compact-extract > p:not(.section-label) { font-family: 'Instrument Serif', Georgia, serif; font-size: 20px; line-height: 1.35; }
  .source-extract > a, .empty-reading a { color: #234c49; font-size: 12px; font-weight: 600; text-underline-offset: 3px; }
  .source-extract footer { display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; margin-top: 17px; padding-top: 13px; border-top: 1px solid #d7d8d3; color: #66706d; font: 10px/1.45 'DM Mono', monospace; }
  .source-extract footer a { color: #234c49; text-align: right; text-decoration: none; }
  .source-extract footer small { grid-column: 1 / -1; }
  .empty-reading p:not(.section-label) { color: #3c4945; font-family: inherit; font-size: 13px; line-height: 1.7; }
  .name-reading p:not(.section-label), .ohm-reading > p:not(.section-label) { margin: 0 0 10px; color: #394542; font-size: 13px; line-height: 1.65; }
  .name-reading small { color: #67716e; font: 10px/1.6 'DM Mono', monospace; }
  .ohm-reading { background: #f7f6f1; }
  .ohm-reading dl { margin: 14px 0; border-top: 1px solid #d5d7d2; }
  .ohm-reading dl div { display: grid; grid-template-columns: 105px 1fr; gap: 12px; padding: 8px 0; border-bottom: 1px solid #d5d7d2; }
  .ohm-reading dt { color: #69726f; font: 9px 'DM Mono', monospace; text-transform: uppercase; }
  .ohm-reading dd { margin: 0; overflow-wrap: anywhere; color: #303b38; font-size: 12px; }
  .ohm-reading a { color: #234c49; font-size: 12px; font-weight: 600; text-underline-offset: 3px; }
  .content-loading, .content-error { margin: 0; padding: 20px 30px; border-bottom: 1px solid #cdd0cb; color: #56615e; font-size: 12px; line-height: 1.55; }
  .content-loading { display: flex; align-items: center; gap: 10px; }
  .content-loading span { width: 11px; height: 11px; border: 1px solid #63706c; border-top-color: transparent; border-radius: 50%; animation: spin .8s linear infinite; }
  .content-error { color: #7c342b; }
  .evidence { border-bottom: 1px solid rgba(79, 91, 87, .18); }
  .evidence summary { display: flex; align-items: center; justify-content: space-between; padding: 20px 30px; cursor: pointer; color: #374440; font: 11px 'DM Mono', monospace; letter-spacing: .055em; text-transform: uppercase; }
  .evidence summary::marker { color: #9b4056; }
  .evidence summary small { color: #737c78; font-size: 9px; letter-spacing: .025em; }
  .evidence[open] summary { border-bottom: 1px solid #d3d5d0; }
  .confidence-grid { display: grid; grid-template-columns: repeat(3, 1fr); padding: 18px 24px; }
  .confidence-grid div { min-width: 0; padding: 0 10px; border-left: 1px solid #d0d3ce; }
  .confidence-grid div:first-child { padding-left: 0; border-left: 0; }
  .confidence-grid span, .confidence-grid small { display: block; color: #66706d; font: 9px/1.4 'DM Mono', monospace; text-transform: uppercase; }
  .confidence-grid strong { display: block; margin: 5px 0; font: 26px/1 'Instrument Serif', Georgia, serif; font-weight: 400; }
  .dispute-note, .precision-note { margin: 0 24px 18px; padding: 12px; background: #ebe9e2; color: #4f5a57; font-size: 10px; line-height: 1.55; }
  .record-source { padding: 2px 24px 18px; }
  .record-source a { display: flex; flex-direction: column; gap: 4px; color: inherit; text-decoration: none; }
  .record-source strong { font-family: 'Instrument Serif', Georgia, serif; font-size: 18px; font-weight: 400; }
  .record-source span { color: #65706d; font: 8px/1.45 'DM Mono', monospace; }
  .connections > div { display: flex; flex-direction: column; gap: 3px; padding: 10px 0; border-top: 1px solid #d4d6d1; }
  .connections > div > span, .connections small { color: #68716f; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .connections strong { font-size: 15px; font-weight: 600; }
  .connections button { align-self: flex-start; margin-top: 5px; padding: 0; border: 0; border-bottom: 1px solid #53615d; background: transparent; color: #294b47; cursor: pointer; font-size: 9px; }
  .causal-caveat { margin: 0 0 14px; color: #59635f; font-size: 10px; line-height: 1.5; }
  .causal-path, .causal-claim { padding: 13px 0; border-top: 1px solid #d0d3ce; }
  .causal-path > span, .causal-claim > span, .causal-path small, .causal-claim small { display: block; color: #68716f; font: 8px/1.45 'DM Mono', monospace; text-transform: uppercase; }
  .causal-path strong { display: block; margin: 5px 0; font: 19px/1.2 'Instrument Serif', Georgia, serif; font-weight: 500; }
  .causal-path p, .causal-claim > p { margin: 7px 0; color: #303b38; font-size: 11px; line-height: 1.55; }
  .causal-claim details { margin-top: 9px; color: #56615e; font-size: 9px; line-height: 1.5; }
  .causal-claim summary { cursor: pointer; text-transform: uppercase; }
  .causal-claim ul { margin: 6px 0 0; padding-left: 17px; }
  .causal-claim a { color: #234c49; }
  .wiki-context { background: #f5f5ef; }
  .context-card { display: grid; gap: 5px; padding: 13px 0; border-top: 1px solid #d0d3ce; }
  .context-card > span, .context-card > small { color: #68716f; font: 8px/1.45 'DM Mono', monospace; text-transform: uppercase; }
  .context-card > strong { font: 19px/1.2 'Instrument Serif', Georgia, serif; font-weight: 500; }
  .context-card > p { margin: 1px 0; color: #303b38; font-size: 11px; line-height: 1.55; }
  .context-card > a, .context-card details a { color: #234c49; font-size: 9px; line-height: 1.45; }
  .context-card details { margin-top: 4px; color: #4f5b57; font-size: 10px; line-height: 1.55; }
  .context-card details summary { cursor: pointer; font: 9px 'DM Mono', monospace; text-transform: uppercase; }
  .context-card details p { white-space: pre-line; }
  .regional-context { background: #f8f4ec; }
  .regional-card { display: grid; gap: 5px; padding: 12px 0; border-top: 1px solid #d0d3ce; }
  .regional-card > span, .regional-card > small { color: #68716f; font: 8px/1.45 'DM Mono', monospace; text-transform: uppercase; }
  .regional-card > strong { font: 18px/1.2 'Instrument Serif', Georgia, serif; font-weight: 500; }
  .regional-card button { justify-self: start; padding: 0; border: 0; border-bottom: 1px solid #53615d; background: transparent; color: #294b47; cursor: pointer; font-size: 9px; }
  .regional-card a { color: #234c49; font-size: 9px; }
  .period-definition { display: grid; gap: 4px; padding: 12px 0; border-top: 1px solid #d0d3ce; }
  .period-definition > span, .period-definition small { color: #68716f; font: 8px/1.45 'DM Mono', monospace; text-transform: uppercase; }
  .period-definition strong { font: 18px/1.2 'Instrument Serif', Georgia, serif; font-weight: 500; }
  .period-definition a { color: #234c49; font-size: 9px; line-height: 1.45; }
  .elsewhere > p:not(.section-label) { margin: -1px 0 17px; color: #69736f; font-size: 12px; line-height: 1.55; }
  .elsewhere > div { border-top: 1px solid rgba(79, 91, 87, .2); }
  .elsewhere button { position: relative; width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: baseline; gap: 17px; padding: 14px 18px 14px 0; border: 0; border-bottom: 1px solid rgba(79, 91, 87, .2); background: transparent; color: inherit; cursor: pointer; text-align: left; }
  .elsewhere button::after { content: '→'; position: absolute; right: 0; opacity: 0; color: #914157; transition: opacity .16s ease, transform .16s ease; }
  .elsewhere button:hover::after { opacity: 1; transform: translateX(3px); }
  .elsewhere button:hover span { color: #294d48; }
  .elsewhere button span { overflow: hidden; text-overflow: ellipsis; font-family: 'Instrument Serif', Georgia, serif; font-size: 19px; line-height: 1.15; font-weight: 400; white-space: nowrap; }
  .elsewhere button small { color: #707975; font: 9px 'DM Mono', monospace; text-align: right; }
  .text-record-link { display: flex; justify-content: space-between; align-items: center; margin: 0; padding: 21px 30px; border-bottom: 1px solid rgba(79, 91, 87, .2); background: #f0f1eb; color: #29423e; font: 10px 'DM Mono', monospace; letter-spacing: .065em; text-decoration: none; text-transform: uppercase; transition: background .18s ease, color .18s ease; }
  .text-record-link span { font-size: 16px; transition: transform .18s ease; }
  .text-record-link:hover { background: #29423e; color: #fffdf7; }
  .text-record-link:hover span { transform: translateX(4px); }

  .timeline { position: absolute; z-index: 8; right: 0; bottom: 0; left: 0; height: var(--timeline-height); display: grid; grid-template-columns: 200px minmax(320px, 1fr) 110px 220px; align-items: center; gap: 24px; padding: 14px 22px 12px; border-top: 1px solid rgba(62, 79, 74, .52); background: rgba(255, 253, 248, .98); box-shadow: 0 -10px 34px rgba(22, 31, 29, .045); }
  .timeline-primary { position: relative; display: flex; align-items: center; gap: 15px; }
  .play { flex: none; width: 44px; height: 44px; display: grid; place-items: center; border: 1px solid rgba(169, 63, 90, .72); border-radius: 50%; background: transparent; color: #94344d; cursor: pointer; transition: background .18s ease, color .18s ease, transform .18s ease; }
  .play:hover { transform: scale(1.04); }
  .play:hover { background: #a93f5a; color: white; }
  .play-icon { width: 0; height: 0; margin-left: 2px; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 8px solid currentColor; }
  .pause-icon { width: 8px; height: 10px; border-right: 3px solid currentColor; border-left: 3px solid currentColor; }
  .year-button { display: flex; flex-direction: column; align-items: flex-start; min-width: 0; padding: 0; border: 0; background: none; color: inherit; cursor: pointer; text-align: left; }
  .year-button > span, .year-button small { color: #69736f; font: 10px 'DM Mono', monospace; letter-spacing: .035em; }
  .year-button strong { margin: 5px 0 4px; font: 36px/.94 'Instrument Serif', Georgia, serif; font-weight: 400; letter-spacing: -.025em; white-space: nowrap; }
  .year-editor { position: absolute; z-index: 5; bottom: 50px; left: -6px; width: 260px; display: grid; grid-template-columns: 1fr 66px 42px; gap: 8px; padding: 14px; border: 1px solid #808985; background: #f8f7f2; box-shadow: 0 12px 30px rgba(25, 34, 32, .16); }
  .year-editor label { display: flex; flex-direction: column; gap: 4px; }
  .year-editor label span { color: #626c69; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  .year-editor input, .year-editor select { min-width: 0; height: 32px; border: 1px solid #a4aaa6; border-radius: 0; background: #fff; color: #1d2826; padding: 0 7px; font-size: 12px; }
  .year-editor button[type='submit'] { align-self: end; height: 32px; border: 0; background: #263f3c; color: white; cursor: pointer; font-size: 10px; }
  .year-editor .editor-close { position: absolute; top: -27px; right: -1px; width: 27px; height: 27px; border: 1px solid #808985; background: #f8f7f2; cursor: pointer; }
  .year-editor p { grid-column: 1 / -1; margin: 0; color: #843b31; font-size: 9px; }
  .timeline-scale { position: relative; height: 92px; display: flex; align-items: center; padding-bottom: 22px; }
  .timeline-scale input { position: absolute; z-index: 3; top: 32px; left: 0; width: 100%; height: 32px; margin: 0; appearance: none; background: transparent; cursor: ew-resize; }
  .timeline-scale input::-webkit-slider-runnable-track { height: 1px; background: rgba(48, 67, 62, .72); }
  .timeline-scale input::-moz-range-track { height: 1px; background: rgba(48, 67, 62, .72); }
  .timeline-scale input::-webkit-slider-thumb { width: 14px; height: 14px; margin-top: -7px; appearance: none; border: 3px solid #fffdf7; border-radius: 50%; background: #a3445c; box-shadow: 0 0 0 1px #743047, 0 2px 6px rgba(75, 38, 47, .22); }
  .timeline-scale input::-moz-range-thumb { width: 8px; height: 8px; border: 3px solid #fffdf7; border-radius: 50%; background: #a3445c; box-shadow: 0 0 0 1px #743047; }
  .archive-bands { position: absolute; z-index: 1; top: 16px; right: 0; left: 0; height: 33px; display: grid; grid-template-columns: repeat(4, 1fr); overflow: hidden; border-bottom: 1px solid rgba(76, 91, 86, .34); background: linear-gradient(90deg, rgba(205, 178, 92, .12) 0 25%, rgba(105, 150, 96, .11) 25% 50%, rgba(172, 93, 72, .1) 50% 75%, rgba(83, 130, 162, .1) 75% 100%); }
  .archive-bands span { overflow: hidden; padding: 10px 11px; border-left: 1px solid rgba(76, 91, 86, .16); color: #40504c; font: 10px/1 'DM Mono', monospace; letter-spacing: .015em; white-space: nowrap; }
  .archive-bands span:first-child { border-left: 0; }
  .timeline-ticks { position: absolute; right: 0; bottom: 0; left: 0; display: flex; justify-content: space-between; color: #5e6b67; font: 10px 'DM Mono', monospace; }
  .year-steps { display: grid; grid-template-columns: 1fr 1fr; }
  .year-steps button { position: relative; height: 46px; border: 0; background: transparent; color: #344541; cursor: pointer; font: 11px 'DM Mono', monospace; }
  .year-steps button + button::before { content: ''; position: absolute; top: 10px; bottom: 10px; left: 0; width: 1px; background: rgba(70, 84, 80, .3); }
  .year-steps button:hover { background: #eff0eb; color: #8f3f55; }
  .map-credit { margin: 0; color: #68736f; font: 9px/1.6 'DM Mono', monospace; }
  .map-credit a { color: #315d5d; text-underline-offset: 2px; }

  .loading-state { position: absolute; z-index: 20; inset: 0; display: grid; place-content: center; justify-items: center; background: #dfe2de; }
  .loading-state > span { width: 28px; height: 28px; border: 1px solid #7f8985; border-top-color: #365c5f; border-radius: 50%; animation: spin .8s linear infinite; }
  .loading-state p { margin-top: 12px; font: 8px 'DM Mono', monospace; letter-spacing: .12em; text-transform: uppercase; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error-toast { position: absolute; z-index: 18; top: 76px; right: 16px; width: min(390px, calc(100vw - 32px)); display: flex; justify-content: space-between; gap: 18px; padding: 14px 16px; border: 1px solid #9d5041; background: #f4e8e2; color: #4f2923; box-shadow: 0 8px 24px rgba(35, 25, 22, .14); }
  .error-toast strong { font: 9px 'DM Mono', monospace; text-transform: uppercase; }
  .error-toast p { margin: 4px 0 0; font-size: 10px; line-height: 1.45; }
  .error-toast button { border: 0; background: none; cursor: pointer; font-size: 18px; }

  .about-dialog { width: min(920px, calc(100vw - 36px)); max-height: calc(100dvh - 36px); padding: 0; border: 1px solid #4b5653; border-radius: 0; background: #f5f4ef; color: #1c2725; box-shadow: 0 28px 80px rgba(14, 22, 20, .32); }
  .about-dialog::backdrop { background: rgba(23, 31, 29, .62); }
  .dialog-inner { padding: 32px 34px 27px; }
  .dialog-inner > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 30px; padding-bottom: 25px; border-bottom: 1px solid #bdc2bd; }
  .dialog-inner h2 { max-width: 650px; margin: 0; font-size: 34px; line-height: 1.08; font-weight: 520; letter-spacing: -.025em; }
  .dialog-grid { display: grid; grid-template-columns: 1.15fr .85fr; gap: 36px; padding-top: 25px; }
  .method-copy > p { margin: 0 0 15px; color: #43504d; font-size: 12px; line-height: 1.7; }
  .dialog-grid h3 { margin: 24px 0 10px; font: 8px 'DM Mono', monospace; letter-spacing: .12em; text-transform: uppercase; }
  .visual-key { margin: 0; padding: 0; list-style: none; border-top: 1px solid #c8cbc7; }
  .visual-key li { display: flex; align-items: center; gap: 13px; padding: 10px 0; border-bottom: 1px solid #d5d7d2; color: #515d5a; font-size: 10px; line-height: 1.45; }
  .visual-key strong { color: #27322f; font-weight: 600; }
  .archive-note { margin-top: 20px !important; padding: 12px; border-left: 2px solid #506b69; background: #e9e8e1; font-size: 10px !important; }
  .release-notes { border-left: 1px solid #c9ccc7; padding-left: 28px; }
  .release-stats { display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid #afb5b0; border-left: 1px solid #afb5b0; }
  .release-stats div { min-width: 0; padding: 11px; border-right: 1px solid #afb5b0; border-bottom: 1px solid #afb5b0; }
  .release-stats span, .release-stats strong { display: block; }
  .release-stats span { margin-bottom: 5px; color: #69716f; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  .release-stats strong { overflow: hidden; text-overflow: ellipsis; font: 16px 'Instrument Serif', Georgia, serif; font-weight: 400; white-space: nowrap; }
  .source-list { border-top: 1px solid #c7cac6; }
  .source-list a { display: flex; justify-content: space-between; gap: 18px; padding: 10px 0; border-bottom: 1px solid #d4d6d1; color: inherit; text-decoration: none; }
  .source-list span { font-family: 'Instrument Serif', Georgia, serif; font-size: 16px; }
  .source-list small { color: #69716e; font: 7px/1.45 'DM Mono', monospace; text-align: right; }
  .release-id { margin: 18px 0 0; color: #747c79; font: 7px 'DM Mono', monospace; }

  @media (max-width: 1050px) {
    :global(:root) { --reader-width: 380px; }
    .masthead { grid-template-columns: 180px minmax(260px, 440px) 1fr; gap: 18px; }
    .utility-nav a { display: none; }
    .reading .masthead { right: 380px; }
    .reading-surface { width: 380px; }
    .reading .map-legend { right: 402px; }
    .timeline { grid-template-columns: 170px 1fr 86px 138px; gap: 12px; }
    .map-credit span { display: none; }
    .map-credit a { display: block; }
  }

  @media (max-width: 839px) {
    :global(:root) { --timeline-height: 125px; }
    :global(.maplibregl-ctrl-bottom-right) { right: 4px; bottom: 170px; }
    .masthead, .reading .masthead { right: 0; height: 104px; grid-template-columns: 1fr auto; grid-template-rows: 48px 50px; gap: 0 16px; padding: 3px 14px; }
    .brand { grid-column: 1; grid-row: 1; }
    .utility-nav { grid-column: 2; grid-row: 1; }
    .utility-nav button { font-size: 8px; }
    .search { grid-column: 1 / -1; grid-row: 2; height: 40px; }
    .search-results { top: 45px; left: -4px; right: -4px; max-height: min(54dvh, 430px); overflow-y: auto; }
    .date-readout { top: 121px; left: 15px; }
    .date-readout strong { font-size: 33px; }
    .lens-control { top: 184px; left: 15px; max-width: calc(100vw - 30px); overflow-x: auto; }
    .lens-control legend { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    .lens-control > div { min-width: max-content; }
    .lens-control button { min-height: 30px; padding-inline: 8px; font-size: 7px; }
    .layer-control { top: 224px; left: 15px; max-width: calc(100vw - 30px); }
    .layer-control button { min-height: 30px; padding-inline: 8px; font-size: 7px; }
    .overlay-control { top: 264px; left: 15px; max-width: calc(100vw - 30px); }
    .overlay-control legend { padding-inline: 7px; font-size: 7px; }
    .overlay-control button { min-height: 28px; padding-inline: 7px; font-size: 7px; }
    .historical-map-control { top: 302px; left: 15px; max-width: calc(100vw - 30px); }
    .historical-map-control legend { padding-inline: 7px; font-size: 7px; }
    .historical-map-control select { min-width: 130px; max-width: 210px; min-height: 28px; font-size: 7px; }
    .historical-map-control button { min-height: 28px; padding-inline: 7px; font-size: 7px; }
    .historical-map-card, .historical-map-error { top: 338px; left: 15px; width: min(340px, calc(100vw - 30px)); max-height: calc(100dvh - 480px); }
    .orientation { display: none; }
    .orientation > span { font-size: 10px; }
    .map-legend, .reading .map-legend { right: auto; bottom: 130px; left: 7px; max-width: calc(100vw - 58px); gap: 9px; }
    .map-legend span { font-size: 0; }
    .map-legend span::after { font-size: 7px; }
    .map-legend .control-key::after { content: 'Control'; }
    .map-legend .theme-key::after { content: 'Highlighted'; }
    .map-legend .background-key::after { content: 'Other history'; }
    .map-legend .soft-key::after { content: 'Soft edge'; }
    .map-legend .gap-key::after { content: 'No coverage'; }
    .reading-surface { inset: auto 0 125px; width: 100%; height: min(48dvh, 470px); max-height: none; border-top: 1px solid #66716d; border-left: 0; box-shadow: 0 -16px 38px rgba(22, 31, 29, .12); }
    .record-header { padding: 18px 18px 14px; }
    .record-header h1 { font-size: 31px; }
    .record-dates { padding: 10px 18px; }
    .geometry-reading, .lens-reading, .assertion-reading, .name-reading, .ohm-reading, .source-extract, .empty-reading, .elsewhere, .connections, .causal-reading, .chronology-reading, .wiki-context, .regional-context { padding: 18px; }
    .timeline { right: 0; bottom: 0; left: 0; height: 125px; grid-template-columns: 146px 1fr; grid-template-rows: 53px 48px; gap: 0 10px; padding: 8px 12px; border-right: 0; border-bottom: 0; border-left: 0; }
    .timeline-primary { grid-column: 1; grid-row: 1; }
    .timeline-scale { grid-column: 1 / -1; grid-row: 2; height: 48px; }
    .year-steps { grid-column: 2; grid-row: 1; justify-self: end; width: 96px; }
    .archive-bands { top: 6px; height: 24px; }
    .archive-bands span { padding-inline: 2px; color: #263936; font-size: 6px; text-align: center; }
    .timeline-scale input { top: 17px; }
    .timeline-ticks span:nth-child(2), .timeline-ticks span:nth-child(4) { display: none; }
    .timeline-ticks { bottom: 10px; font-size: 7px; }
    .map-credit { position: absolute; right: 12px; bottom: 3px; font-size: 6px; line-height: 1; }
    .map-credit a { display: inline; }
    .map-credit a:not(:first-child), .map-credit span { display: none; }
    .year-editor { bottom: 47px; width: min(260px, calc(100vw - 26px)); }
    .detail-limit { top: 111px; right: 7px; }
    .dialog-inner { padding: 24px 20px; }
    .dialog-inner h2 { font-size: 34px; }
    .dialog-grid { grid-template-columns: 1fr; gap: 22px; }
    .release-notes { border-top: 1px solid #c9ccc7; border-left: 0; padding-top: 22px; padding-left: 0; }
  }

  @media (max-width: 480px) {
    .brand > span { font-size: 12px; }
    .date-readout { top: 112px; left: 8px; padding: 7px 10px 8px; background: rgba(247, 244, 236, .96); text-shadow: none; }
    .date-readout strong { font-size: 31px; }
    .date-readout small { max-width: 180px; }
    .lens-control { top: 181px; left: 8px; max-width: calc(100vw - 16px); }
    .layer-control { top: 221px; left: 8px; }
    .layer-control button { padding-inline: 7px; }
    .overlay-control { top: 261px; left: 8px; }
    .historical-map-control { top: 299px; left: 8px; max-width: calc(100vw - 16px); }
    .historical-map-control legend { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    .historical-map-control select { min-width: 0; max-width: calc(100vw - 100px); }
    .historical-map-card, .historical-map-error { top: 335px; left: 8px; width: calc(100vw - 16px); }
    .orientation { bottom: 132px; }
    .orientation > span { display: block; }
    .map-legend { bottom: 130px; }
    .reading-surface { bottom: 125px; height: 48dvh; }
    .record-header h1 { font-size: 28px; }
    .confidence-grid { padding-inline: 18px; }
    .year-button small { display: none; }
    .year-steps { width: 86px; }
    .year-steps button { font-size: 7px; }
    .about-dialog { width: calc(100vw - 14px); max-height: calc(100dvh - 14px); }
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
  }
</style>
