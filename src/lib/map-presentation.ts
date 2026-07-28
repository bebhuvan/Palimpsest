import type { Map as MapLibreMap } from 'maplibre-gl';
import type { GeoJSON } from 'geojson';
import { lensDefinition, reviewedLensFilter, type HistoricalLens } from '$lib/lenses';
import {
  setOhmLayerVisibility,
  updateOhmYear,
  type HistoricalLayerMode
} from '$lib/ohm';

export type EvidenceOverlay = 'none' | 'confidence' | 'provenance';

export const MAP_SOURCE = 'historical-world';
export const THEME_DISCOVERY_SOURCE = 'theme-discovery-points';
export const COVERAGE_SOURCE = 'coverage-gaps';
export const HISTORICAL_MAP_IMAGE_SOURCE = 'historical-map-image';
export const HISTORICAL_MAP_IMAGE_LAYER = 'historical-map-image-raster';
export const FILL_LAYER = 'history-fill';
export const LINE_LAYER = 'history-line';
export const SOFT_LINE_LAYER = 'history-soft-line';
export const CONTESTED_LAYER = 'history-contested-line';
export const SELECTED_HALO_LAYER = 'history-selected-halo';
export const SELECTED_LAYER = 'history-selected-line';
export const REVIEWED_LABEL_LAYER = 'history-reviewed-label';
export const REVIEWED_PLACE_POINT_LAYER = 'history-reviewed-place-point';
export const REVIEWED_PLACE_LABEL_LAYER = 'history-reviewed-place-label';
export const THEME_FILL_LAYER = 'history-theme-fill';
export const THEME_LINE_LAYER = 'history-theme-line';
export const THEME_DISCOVERY_LAYER = 'history-theme-discovery';
export const THEME_POINT_LAYER = 'history-theme-point';
export const THEME_LABEL_LAYER = 'history-theme-label';
export const COVERAGE_FILL_LAYER = 'coverage-gap-fill';
export const COVERAGE_EDGE_LAYER = 'coverage-gap-edge';

export const HISTORY_LAYERS = [
  THEME_LABEL_LAYER,
  REVIEWED_PLACE_LABEL_LAYER,
  REVIEWED_LABEL_LAYER,
  THEME_POINT_LAYER,
  THEME_DISCOVERY_LAYER,
  REVIEWED_PLACE_POINT_LAYER,
  SELECTED_LAYER,
  SELECTED_HALO_LAYER,
  THEME_LINE_LAYER,
  THEME_FILL_LAYER,
  CONTESTED_LAYER,
  SOFT_LINE_LAYER,
  LINE_LAYER,
  FILL_LAYER
];

export const SOFT_MEANINGS = [
  'claim',
  'territorial_claim',
  'cultural_region',
  'influence_zone',
  'mobility_range',
  'seasonal_use',
  'network',
  'unknown_extent',
  'unknown',
  'tributary_relationship'
];

export const POINT_KINDS = ['settlement', 'archaeological_site', 'event'];

export function yearFilter(year: number): unknown[] {
  return [
    'all',
    ['<=', ['get', 'valid_from'], year],
    ['>=', ['get', 'valid_to'], year],
    ['<=', ['coalesce', ['get', 'min_display_zoom'], 0], ['zoom']]
  ];
}

export function combinedFilter(year: number, extra: unknown[]): unknown[] {
  return ['all', ...yearFilter(year).slice(1), extra];
}

export function themedFilter(
  year: number,
  lens: HistoricalLens,
  extra: unknown[]
): unknown {
  if (lens === 'all') return false;
  return ['all', ...yearFilter(year).slice(1), reviewedLensFilter(lens), extra];
}

export type LensVisual = {
  accent: string;
  fillOpacity: number;
  lineWidth: number;
  lineDash: number[];
  pointRadius: number;
};

export function lensVisual(lens: HistoricalLens): LensVisual {
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

export function lensAccent(lens: HistoricalLens): string {
  return lensVisual(lens).accent;
}

export function reviewedFillColor(evidenceOverlay: EvidenceOverlay): unknown {
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

export function reviewedLineColor(evidenceOverlay: EvidenceOverlay): unknown {
  if (evidenceOverlay !== 'none') return reviewedFillColor(evidenceOverlay);
  return ['case', ['boolean', ['feature-state', 'hover'], false], '#453b37', '#625d59'];
}

export function reviewedFillOpacity(lens: HistoricalLens): unknown {
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

export function reviewedLineOpacity(lens: HistoricalLens): unknown {
  const dimmed = lens !== 'all';
  return [
    'case',
    ['boolean', ['feature-state', 'hover'], false], dimmed ? 0.38 : 0.82,
    ['==', ['get', 'spatial_confidence'], 'D'], dimmed ? 0.045 : 0.25,
    dimmed ? 0.085 : 0.46
  ];
}

export interface ReviewedHistoryLayerOptions {
  sourceUrl: string;
  themeDiscoveryData: GeoJSON;
  beforeLayerId?: string;
  year: number;
  lens: HistoricalLens;
  evidenceOverlay: EvidenceOverlay;
  selectedFeatureId?: string | null;
}

export function installReviewedHistoryLayers(
  map: MapLibreMap,
  options: ReviewedHistoryLayerOptions
): void {
  const {
    sourceUrl,
    themeDiscoveryData,
    beforeLayerId,
    year,
    lens,
    evidenceOverlay,
    selectedFeatureId
  } = options;
  const visual = lensVisual(lens);
  const areaFilter = ['!=', ['get', 'spatial_meaning'], 'location'];
  const pointFilter = ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]];

  map.addSource(MAP_SOURCE, {
    type: 'vector',
    url: sourceUrl,
    promoteId: 'feature_id',
    attribution: 'Historical geography: Seshat Global History Databank / Cliopatria (CC BY 4.0)'
  });
  if (!map.getSource(THEME_DISCOVERY_SOURCE)) {
    map.addSource(THEME_DISCOVERY_SOURCE, {
      type: 'geojson',
      data: themeDiscoveryData
    });
  }

  const addBeforeLabels = (layer: Parameters<MapLibreMap['addLayer']>[0]): void => {
    map.addLayer(layer, beforeLayerId);
  };

  addBeforeLabels({
    id: FILL_LAYER,
    type: 'fill',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, areaFilter) as never,
    paint: {
      'fill-color': reviewedFillColor(evidenceOverlay) as never,
      'fill-opacity': reviewedFillOpacity(lens) as never,
      'fill-antialias': true
    }
  });
  addBeforeLabels({
    id: LINE_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, areaFilter) as never,
    paint: {
      'line-color': reviewedLineColor(evidenceOverlay) as never,
      'line-width': ['interpolate', ['linear'], ['zoom'],
        1, ['case', ['boolean', ['feature-state', 'hover'], false], 0.9, 0.4],
        4, ['case', ['boolean', ['feature-state', 'hover'], false], 1.2, 0.68],
        8, ['case', ['boolean', ['feature-state', 'hover'], false], 1.65, 0.9]
      ],
      'line-opacity': reviewedLineOpacity(lens) as never
    }
  });
  addBeforeLabels({
    id: SOFT_LINE_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]]) as never,
    paint: {
      'line-color': '#68766f',
      'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.5, 6, 0.95],
      'line-opacity': lens === 'all' ? 0.48 : 0.09,
      'line-dasharray': [1.1, 2.5]
    }
  });
  addBeforeLabels({
    id: CONTESTED_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, ['any', ['==', ['get', 'review_status'], 'contested'], ['has', 'dispute_group']]) as never,
    paint: {
      'line-color': '#8e5a50',
      'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.7, 6, 1.35],
      'line-opacity': lens === 'all' ? 0.76 : 0.14,
      'line-dasharray': [2.6, 2.2]
    }
  });
  addBeforeLabels({
    id: THEME_FILL_LAYER,
    type: 'fill',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: themedFilter(year, lens, areaFilter) as never,
    paint: {
      'fill-color': visual.accent,
      'fill-opacity': ['interpolate', ['linear'], ['zoom'], 1, visual.fillOpacity, 5, visual.fillOpacity * 0.7, 9, visual.fillOpacity * 0.46]
    }
  });
  addBeforeLabels({
    id: THEME_LINE_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: themedFilter(year, lens, areaFilter) as never,
    paint: {
      'line-color': visual.accent,
      'line-width': ['interpolate', ['linear'], ['zoom'], 1, visual.lineWidth, 6, visual.lineWidth * 1.45, 10, visual.lineWidth * 1.8],
      'line-opacity': 0.9,
      'line-dasharray': visual.lineDash
    }
  });
  addBeforeLabels({
    id: THEME_DISCOVERY_LAYER,
    type: 'circle',
    source: THEME_DISCOVERY_SOURCE,
    minzoom: 0,
    maxzoom: 5.5,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 3.2, 3, 4.2, 5, 5],
      'circle-color': visual.accent,
      'circle-stroke-color': '#fffdf7',
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 0, 0.8, 5, 1.2],
      'circle-opacity': ['interpolate', ['linear'], ['zoom'], 0, 0.88, 4, 0.92, 5.5, 0]
    }
  });
  addBeforeLabels({
    id: SELECTED_HALO_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, areaFilter) as never,
    paint: {
      'line-color': '#fffdf7',
      'line-width': ['interpolate', ['linear'], ['zoom'],
        1, ['case', ['boolean', ['feature-state', 'selected'], false], 3.8, 0],
        7, ['case', ['boolean', ['feature-state', 'selected'], false], 5.2, 0]
      ],
      'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.78, 0]
    }
  });
  addBeforeLabels({
    id: SELECTED_LAYER,
    type: 'line',
    source: MAP_SOURCE,
    'source-layer': 'history',
    filter: combinedFilter(year, areaFilter) as never,
    paint: {
      'line-color': '#302d2a',
      'line-width': ['interpolate', ['linear'], ['zoom'],
        1, ['case', ['boolean', ['feature-state', 'selected'], false], 1.45, 0],
        7, ['case', ['boolean', ['feature-state', 'selected'], false], 2.2, 0]
      ],
      'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0]
    }
  });

  map.addLayer({
    id: REVIEWED_LABEL_LAYER,
    type: 'symbol',
    source: MAP_SOURCE,
    'source-layer': 'history_labels',
    maxzoom: 9,
    filter: combinedFilter(year, ['all', ['==', ['get', 'primary'], true], ['!', ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]]) as never,
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
      'text-opacity': lens === 'all' ? 1 : 0.16
    }
  });
  map.addLayer({
    id: REVIEWED_PLACE_POINT_LAYER,
    type: 'circle',
    source: MAP_SOURCE,
    'source-layer': 'history_labels',
    minzoom: 6,
    filter: combinedFilter(year, pointFilter) as never,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 1.4, 12, 2.5],
      'circle-color': ['match', ['get', 'kind'], 'archaeological_site', '#76584f', '#465550'],
      'circle-stroke-color': '#f7f4ec',
      'circle-stroke-width': 0.9,
      'circle-opacity': lens === 'all' ? 0.76 : 0.13
    }
  });
  map.addLayer({
    id: THEME_POINT_LAYER,
    type: 'circle',
    source: MAP_SOURCE,
    'source-layer': 'history_labels',
    minzoom: 1,
    filter: themedFilter(year, lens, pointFilter) as never,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, visual.pointRadius * 0.5, 5, visual.pointRadius, 12, visual.pointRadius * 1.45],
      'circle-color': visual.accent,
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
    filter: themedFilter(year, lens, ['==', ['get', 'primary'], true]) as never,
    layout: {
      'text-field': ['concat', lensDefinition(lens).marker, '  ', ['get', 'name']],
      'text-font': ['Noto Sans Bold'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 1, 10.5, 6, 12, 12, 13],
      'text-letter-spacing': 0.035,
      'text-max-width': 11,
      'text-padding': 8,
      'symbol-sort-key': ['-', ['to-number', ['get', 'label_area'], 0]]
    },
    paint: {
      'text-color': visual.accent,
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
    filter: combinedFilter(year, pointFilter) as never,
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
      'text-opacity': lens === 'all' ? 1 : 0.16
    }
  });

  if (selectedFeatureId) {
    map.setFeatureState(
      { source: MAP_SOURCE, sourceLayer: 'history', id: selectedFeatureId },
      { selected: true }
    );
  }
}

export function applyMapYearPresentation(
  map: MapLibreMap,
  year: number,
  lens: HistoricalLens,
  evidenceOverlay: EvidenceOverlay
): void {
  updateOhmYear(map, year, lens);
  const visual = lensVisual(lens);
  const backgroundOpacity = lens === 'all' ? 1 : 0.16;
  const areaFilter = combinedFilter(year, ['!=', ['get', 'spatial_meaning'], 'location']);

  for (const layer of [FILL_LAYER, LINE_LAYER, SELECTED_HALO_LAYER, SELECTED_LAYER]) {
    if (map.getLayer(layer)) map.setFilter(layer, areaFilter as never);
  }
  if (map.getLayer(FILL_LAYER)) {
    map.setPaintProperty(FILL_LAYER, 'fill-opacity', reviewedFillOpacity(lens) as never);
    map.setPaintProperty(FILL_LAYER, 'fill-color', reviewedFillColor(evidenceOverlay) as never);
  }
  if (map.getLayer(LINE_LAYER)) {
    map.setPaintProperty(LINE_LAYER, 'line-opacity', reviewedLineOpacity(lens) as never);
    map.setPaintProperty(LINE_LAYER, 'line-color', reviewedLineColor(evidenceOverlay) as never);
  }

  const placeFilter = combinedFilter(year, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]);
  if (map.getLayer(REVIEWED_LABEL_LAYER)) {
    map.setFilter(REVIEWED_LABEL_LAYER, combinedFilter(year, ['all', ['==', ['get', 'primary'], true], ['!', ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]]) as never);
    map.setPaintProperty(REVIEWED_LABEL_LAYER, 'text-opacity', backgroundOpacity);
  }
  for (const layer of [REVIEWED_PLACE_POINT_LAYER, REVIEWED_PLACE_LABEL_LAYER]) {
    if (map.getLayer(layer)) map.setFilter(layer, placeFilter as never);
  }
  if (map.getLayer(REVIEWED_PLACE_POINT_LAYER)) {
    map.setPaintProperty(REVIEWED_PLACE_POINT_LAYER, 'circle-opacity', lens === 'all' ? 0.76 : 0.13);
  }
  if (map.getLayer(REVIEWED_PLACE_LABEL_LAYER)) {
    map.setPaintProperty(REVIEWED_PLACE_LABEL_LAYER, 'text-opacity', backgroundOpacity);
  }
  if (map.getLayer(SOFT_LINE_LAYER)) {
    map.setFilter(SOFT_LINE_LAYER, combinedFilter(year, ['in', ['get', 'spatial_meaning'], ['literal', SOFT_MEANINGS]]) as never);
    map.setPaintProperty(SOFT_LINE_LAYER, 'line-opacity', lens === 'all' ? 0.48 : 0.09);
  }
  if (map.getLayer(CONTESTED_LAYER)) {
    map.setFilter(CONTESTED_LAYER, combinedFilter(year, ['any', ['==', ['get', 'review_status'], 'contested'], ['has', 'dispute_group']]) as never);
    map.setPaintProperty(CONTESTED_LAYER, 'line-opacity', lens === 'all' ? 0.76 : 0.14);
  }

  const thematicArea = ['!=', ['get', 'spatial_meaning'], 'location'];
  if (map.getLayer(THEME_FILL_LAYER)) {
    map.setFilter(THEME_FILL_LAYER, themedFilter(year, lens, thematicArea) as never);
    map.setPaintProperty(THEME_FILL_LAYER, 'fill-color', visual.accent);
    map.setPaintProperty(THEME_FILL_LAYER, 'fill-opacity', ['interpolate', ['linear'], ['zoom'], 1, visual.fillOpacity, 5, visual.fillOpacity * 0.7, 9, visual.fillOpacity * 0.46] as never);
  }
  if (map.getLayer(THEME_LINE_LAYER)) {
    map.setFilter(THEME_LINE_LAYER, themedFilter(year, lens, thematicArea) as never);
    map.setPaintProperty(THEME_LINE_LAYER, 'line-color', visual.accent);
    map.setPaintProperty(THEME_LINE_LAYER, 'line-width', ['interpolate', ['linear'], ['zoom'], 1, visual.lineWidth, 6, visual.lineWidth * 1.45, 10, visual.lineWidth * 1.8] as never);
    map.setPaintProperty(THEME_LINE_LAYER, 'line-dasharray', visual.lineDash);
  }
  if (map.getLayer(THEME_DISCOVERY_LAYER)) {
    map.setPaintProperty(THEME_DISCOVERY_LAYER, 'circle-color', visual.accent);
  }
  if (map.getLayer(THEME_POINT_LAYER)) {
    map.setFilter(THEME_POINT_LAYER, themedFilter(year, lens, ['all', ['==', ['get', 'primary'], true], ['in', ['get', 'kind'], ['literal', POINT_KINDS]]]) as never);
    map.setPaintProperty(THEME_POINT_LAYER, 'circle-color', visual.accent);
    map.setPaintProperty(THEME_POINT_LAYER, 'circle-radius', ['interpolate', ['linear'], ['zoom'], 1, visual.pointRadius * 0.5, 5, visual.pointRadius, 12, visual.pointRadius * 1.45] as never);
  }
  if (map.getLayer(THEME_LABEL_LAYER)) {
    map.setFilter(THEME_LABEL_LAYER, themedFilter(year, lens, ['==', ['get', 'primary'], true]) as never);
    map.setPaintProperty(THEME_LABEL_LAYER, 'text-color', visual.accent);
    map.setLayoutProperty(THEME_LABEL_LAYER, 'text-field', ['concat', lensDefinition(lens).marker, '  ', ['get', 'name']] as never);
  }
}

export function applyLayerModePresentation(
  map: MapLibreMap,
  mode: HistoricalLayerMode,
  lens: HistoricalLens
): boolean {
  setOhmLayerVisibility(map, mode, lens);
  const reviewedVisibility = mode === 'historical-detail' ? 'none' : 'visible';
  for (const layer of HISTORY_LAYERS) {
    if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', reviewedVisibility);
  }
  const coverageVisibility = reviewedVisibility === 'visible' && lens === 'all' ? 'visible' : 'none';
  for (const layer of [COVERAGE_FILL_LAYER, COVERAGE_EDGE_LAYER]) {
    if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', coverageVisibility);
  }
  return mode !== 'historical-detail' && map.getZoom() > 7.05;
}
