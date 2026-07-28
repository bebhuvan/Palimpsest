import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import { lensDefinition, type HistoricalLens } from '$lib/lenses';

export type HistoricalLayerMode = 'combined' | 'historical-detail' | 'reviewed';

export const OHM_TILEJSON = 'https://vtiles.openhistoricalmap.org/maps/ohm.json';
export const OHM_LAND_TILEJSON = 'https://vtiles.openhistoricalmap.org/maps/osm_land.json';
export const NATURAL_EARTH_TILEJSON = 'https://vtiles.openhistoricalmap.org/maps/ne.json';
// These are the templates advertised by the official TileJSON. Embedding them avoids making
// browser startup depend on cross-origin access to the TileJSON documents themselves.
const OHM_TILES = 'https://vtiles.openhistoricalmap.org/maps/ohm/{z}/{x}/{y}';
const NATURAL_EARTH_TILES = 'https://vtiles.openhistoricalmap.org/maps/ne/{z}/{x}/{y}';
export const OHM_COPYRIGHT_URL = 'https://www.openhistoricalmap.org/copyright';
// OHM's website no longer serves the old /map-styles/fonts path. OpenFreeMap
// publishes Noto's MapLibre glyph ranges under a stable, CORS-enabled URL.
export const OHM_GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';

export const FIRST_OHM_LABEL_LAYER = 'ohm-label-major-admin';

const OHM_DETAIL_LAYER_IDS = [
  'ohm-water-areas',
  'ohm-landuse-areas',
  'ohm-other-areas',
  'ohm-admin-boundaries',
  'ohm-maritime-boundaries',
  'ohm-water-lines',
  'ohm-routes',
  'ohm-transport-lines',
  'ohm-buildings',
  'ohm-settlement-points',
  'ohm-archaeology-points',
  'ohm-local-points'
] as const;

export const OHM_LABEL_LAYER_IDS = [
  FIRST_OHM_LABEL_LAYER,
  'ohm-label-major-place',
  'ohm-label-regional-admin',
  'ohm-label-capitals',
  'ohm-label-cities',
  'ohm-label-towns',
  'ohm-label-local-admin',
  'ohm-label-water',
  'ohm-label-routes',
  'ohm-label-local-places',
  'ohm-label-archaeology',
  'ohm-label-buildings',
  'ohm-label-addresses'
] as const;

export const OHM_TEMPORAL_LAYER_IDS = [...OHM_DETAIL_LAYER_IDS, ...OHM_LABEL_LAYER_IDS] as const;
export const OHM_INTERACTIVE_LAYER_IDS = [
  ...OHM_LABEL_LAYER_IDS,
  ...OHM_DETAIL_LAYER_IDS
] as const;

const LAYER_EXTRA_FILTERS: Record<string, unknown[]> = {
  'ohm-landuse-areas': ['in', 'type', 'forest', 'wood', 'grassland', 'park', 'orchard', 'vineyard', 'farmland', 'cemetery'],
  'ohm-other-areas': ['in', 'type', 'archaeological_site', 'fort', 'battlefield', 'ruins'],
  'ohm-settlement-points': ['in', 'type', 'city', 'town', 'village', 'hamlet'],
  'ohm-archaeology-points': ['in', 'type', 'archaeological_site', 'fort', 'battlefield', 'ruins', 'monument'],
  'ohm-local-points': ['all', ['has', 'name'], ['!in', 'type', 'city', 'town', 'village', 'hamlet', 'archaeological_site']],
  'ohm-label-major-admin': ['all', ['has', 'name'], ['in', 'admin_level', 2, '2']],
  'ohm-label-major-place': ['all', ['has', 'name'], ['in', 'type', 'country', 'region', 'continent']],
  'ohm-label-regional-admin': ['all', ['has', 'name'], ['in', 'admin_level', 3, '3', 4, '4']],
  'ohm-label-capitals': ['all', ['has', 'name'], ['==', 'type', 'city'], ['has', 'capital']],
  'ohm-label-cities': ['all', ['has', 'name'], ['==', 'type', 'city'], ['!has', 'capital']],
  'ohm-label-towns': ['all', ['has', 'name'], ['in', 'type', 'town', 'village']],
  'ohm-label-local-admin': ['all', ['has', 'name'], ['in', 'admin_level', 5, '5', 6, '6', 7, '7', 8, '8']],
  'ohm-label-water': ['has', 'name'],
  'ohm-label-routes': ['has', 'name'],
  'ohm-label-local-places': ['all', ['has', 'name'], ['in', 'type', 'hamlet', 'locality', 'neighbourhood', 'suburb', 'square']],
  'ohm-label-archaeology': ['all', ['has', 'name'], ['in', 'type', 'archaeological_site', 'fort', 'battlefield', 'ruins', 'monument']],
  'ohm-label-buildings': ['has', 'name'],
  'ohm-label-addresses': ['any', ['has', 'name'], ['has', 'addr_housename']]
};

const NEVER = false;
const NAMED: unknown[] = ['has', 'name'];
const POWER_TYPES = ['palace', 'castle', 'fort', 'fortification', 'battlefield', 'government', 'courthouse'];
const BELIEF_TYPES = ['place_of_worship', 'church', 'cathedral', 'chapel', 'mosque', 'synagogue', 'temple', 'monastery', 'convent', 'shrine', 'cemetery', 'grave_yard'];
const KNOWLEDGE_TYPES = ['school', 'university', 'college', 'library', 'archive', 'observatory', 'research_institute', 'laboratory'];
const CULTURE_TYPES = ['archaeological_site', 'ruins', 'monument', 'memorial', 'museum', 'theatre', 'arts_centre', 'community_centre'];
const TRADE_TYPES = ['market', 'marketplace', 'port', 'harbour', 'harbor', 'warehouse', 'customs'];

function typeFilter(types: string[], named = false): unknown[] {
  const filter: unknown[] = ['in', 'type', ...types];
  return named ? ['all', NAMED, filter] : filter;
}

/** Theme rules for live OHM context. These use explicit feature types, never name keywords. */
function ohmLensFilter(layerId: string, lens: HistoricalLens): unknown | undefined {
  if (lens === 'all') return undefined;
  const sharedPointLayers = ['ohm-local-points', 'ohm-buildings'];
  const sharedLabelLayers = ['ohm-label-buildings', 'ohm-label-addresses'];
  if (lens === 'power') {
    if (['ohm-admin-boundaries', 'ohm-maritime-boundaries', 'ohm-label-major-admin', 'ohm-label-regional-admin', 'ohm-label-local-admin', 'ohm-label-capitals'].includes(layerId)) return undefined;
    if (['ohm-other-areas', 'ohm-archaeology-points', 'ohm-label-archaeology', ...sharedPointLayers].includes(layerId)) return typeFilter(POWER_TYPES, layerId.startsWith('ohm-label'));
    return NEVER;
  }
  if (lens === 'belief') {
    if (layerId === 'ohm-landuse-areas') return typeFilter(['cemetery']);
    if ([...sharedPointLayers, ...sharedLabelLayers].includes(layerId)) return typeFilter(BELIEF_TYPES, layerId.startsWith('ohm-label'));
    return NEVER;
  }
  if (lens === 'knowledge') {
    if ([...sharedPointLayers, ...sharedLabelLayers].includes(layerId)) return typeFilter(KNOWLEDGE_TYPES, layerId.startsWith('ohm-label'));
    return NEVER;
  }
  if (lens === 'culture') {
    if (['ohm-other-areas', 'ohm-archaeology-points', 'ohm-label-archaeology'].includes(layerId)) return typeFilter(CULTURE_TYPES, layerId.startsWith('ohm-label'));
    if ([...sharedPointLayers, ...sharedLabelLayers].includes(layerId)) return typeFilter(CULTURE_TYPES, layerId.startsWith('ohm-label'));
    return NEVER;
  }
  if (['ohm-routes', 'ohm-transport-lines', 'ohm-label-routes'].includes(layerId)) {
    return typeFilter(
      ['trade_route', 'caravan_route', 'merchant_route', 'commercial_shipping'],
      layerId.startsWith('ohm-label')
    );
  }
  if ([...sharedPointLayers, ...sharedLabelLayers].includes(layerId)) return typeFilter(TRADE_TYPES, layerId.startsWith('ohm-label'));
  return NEVER;
}

const HISTORICAL_NAME: unknown[] = ['coalesce', ['get', 'name'], ['get', 'name_en']];

/** OHM uses astronomical numbering: its year 0 is the historical year 1 BCE. */
export function ohmTemporalFilter(year: number, extra?: unknown): unknown[] {
  const ohmYear = year < 0 ? year + 1 : year;
  const temporal: unknown[] = [
    'all',
    ['any', ['!has', 'start_decdate'], ['<=', 'start_decdate', ohmYear]],
    ['any', ['!has', 'end_decdate'], ['>=', 'end_decdate', ohmYear]]
  ];
  if (extra !== undefined) temporal.push(extra);
  return temporal;
}

export function ohmFilterForLayer(layerId: string, year: number, lens: HistoricalLens = 'all'): unknown[] {
  const base = LAYER_EXTRA_FILTERS[layerId];
  const thematic = ohmLensFilter(layerId, lens);
  const extra = thematic === false
    ? base
    : base !== undefined && thematic !== undefined
    ? ['all', base, thematic]
    : base ?? thematic;
  return ohmTemporalFilter(year, extra);
}

function labelLayout(size: unknown, options: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    'text-field': HISTORICAL_NAME,
    'text-font': ['Noto Sans Regular'],
    'text-size': size,
    'text-letter-spacing': 0.015,
    'text-max-width': 9,
    'text-padding': 4,
    ...options
  };
}

function labelPaint(color = '#303d39', haloWidth = 1.2): Record<string, unknown> {
  return {
    'text-color': color,
    'text-halo-color': 'rgba(247, 244, 236, 0.92)',
    'text-halo-width': haloWidth,
    'text-halo-blur': 0.3
  };
}

export function historyMapStyle(year: number, lens: HistoricalLens = 'all'): StyleSpecification {
  const filter = (id: string) => ohmFilterForLayer(id, year, lens) as never;
  return {
    version: 8,
    name: 'Palimpsest quiet historical map',
    glyphs: OHM_GLYPHS,
    sources: {
      'physical-land': {
        type: 'geojson',
        data: '/world-land.geojson',
        attribution: 'Modern reference geography — physical land: Natural Earth (public domain)'
      },
      'physical-water': {
        type: 'vector',
        tiles: [NATURAL_EARTH_TILES],
        minzoom: 0,
        maxzoom: 20,
        attribution: 'Modern reference geography — physical water: Natural Earth'
      },
      ohm: {
        type: 'vector',
        tiles: [OHM_TILES],
        minzoom: 0,
        maxzoom: 20,
        attribution: 'Historical detail: OpenHistoricalMap contributors'
      }
    },
    layers: [
      { id: 'ground', type: 'background', paint: { 'background-color': '#dce2dd' } },
      {
        id: 'physical-land',
        type: 'fill',
        source: 'physical-land',
        paint: { 'fill-color': '#f2efe6', 'fill-opacity': 1 }
      },
      {
        id: 'physical-water',
        type: 'fill',
        source: 'physical-water',
        'source-layer': 'water_areas',
        paint: { 'fill-color': '#d7dfdc', 'fill-opacity': 0.88 }
      },
      {
        id: 'ohm-water-areas', type: 'fill', source: 'ohm', 'source-layer': 'water_areas', filter: filter('ohm-water-areas'),
        paint: { 'fill-color': '#ccd9d7', 'fill-opacity': 0.78 }
      },
      {
        id: 'ohm-landuse-areas', type: 'fill', source: 'ohm', 'source-layer': 'landuse_areas', minzoom: 6, filter: filter('ohm-landuse-areas'),
        paint: {
          'fill-color': ['match', ['get', 'type'], ['forest', 'wood'], '#d8ddd1', ['orchard', 'vineyard', 'farmland'], '#e8e3d3', '#e2e5d9'],
          'fill-opacity': 0.56
        }
      },
      {
        id: 'ohm-other-areas', type: 'fill', source: 'ohm', 'source-layer': 'other_areas', minzoom: 8, filter: filter('ohm-other-areas'),
        paint: { 'fill-color': '#b7aea0', 'fill-opacity': 0.22, 'fill-outline-color': '#746c62' }
      },
      {
        id: 'ohm-admin-boundaries', type: 'line', source: 'ohm', 'source-layer': 'land_ohm_lines', filter: filter('ohm-admin-boundaries'),
        paint: {
          'line-color': ['case', ['==', ['get', 'disputed'], 'yes'], '#8e5a50', '#7b817d'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 0, 0.3, 5, 0.58, 10, 1.05],
          'line-opacity': 0.48
        }
      },
      {
        id: 'ohm-maritime-boundaries', type: 'line', source: 'ohm', 'source-layer': 'land_ohm_maritime', minzoom: 2, filter: filter('ohm-maritime-boundaries'),
        paint: { 'line-color': '#718481', 'line-width': 0.55, 'line-opacity': 0.42, 'line-dasharray': [2, 3] }
      },
      {
        id: 'ohm-water-lines', type: 'line', source: 'ohm', 'source-layer': 'water_lines', minzoom: 8, filter: filter('ohm-water-lines'),
        paint: { 'line-color': '#91aaa7', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.45, 15, 1.3], 'line-opacity': 0.74 }
      },
      {
        id: 'ohm-routes', type: 'line', source: 'ohm', 'source-layer': 'route_lines', minzoom: 5, filter: filter('ohm-routes'),
        paint: { 'line-color': '#92775e', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 12, 1.4], 'line-opacity': 0.52, 'line-dasharray': [4, 2] }
      },
      {
        id: 'ohm-transport-lines', type: 'line', source: 'ohm', 'source-layer': 'transport_lines', minzoom: 6, filter: filter('ohm-transport-lines'),
        paint: {
          'line-color': ['match', ['get', 'type'], ['rail', 'tram'], '#79736c', '#9a8e7c'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.35, 12, 1.1, 17, 2.2],
          'line-opacity': 0.54
        }
      },
      {
        id: 'ohm-buildings', type: 'fill', source: 'ohm', 'source-layer': 'buildings', minzoom: 14, filter: filter('ohm-buildings'),
        paint: { 'fill-color': '#b9b2a7', 'fill-opacity': 0.58, 'fill-outline-color': '#89837b' }
      },
      {
        id: 'ohm-settlement-points', type: 'circle', source: 'ohm', 'source-layer': 'place_points_centroids', minzoom: 3, filter: filter('ohm-settlement-points'),
        paint: {
          'circle-radius': ['match', ['get', 'type'], 'city', 2.5, 'town', 2, 1.3],
          'circle-color': '#4d5a55',
          'circle-stroke-color': '#f4f1e9',
          'circle-stroke-width': 0.8,
          'circle-opacity': 0.78
        }
      },
      {
        id: 'ohm-archaeology-points', type: 'circle', source: 'ohm', 'source-layer': 'other_points_centroids', minzoom: 8, filter: filter('ohm-archaeology-points'),
        paint: { 'circle-radius': 2.2, 'circle-color': '#8b604d', 'circle-stroke-color': '#f4f1e9', 'circle-stroke-width': 0.9 }
      },
      {
        id: 'ohm-local-points', type: 'circle', source: 'ohm', 'source-layer': 'amenity_points_centroids', minzoom: 14, filter: filter('ohm-local-points'),
        paint: { 'circle-radius': 1.6, 'circle-color': '#6c756f', 'circle-opacity': 0.72 }
      },

      {
        id: FIRST_OHM_LABEL_LAYER, type: 'symbol', source: 'ohm', 'source-layer': 'land_ohm_centroids', maxzoom: 6.5, filter: filter(FIRST_OHM_LABEL_LAYER),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 0, 10, 3, 12, 6, 15], { 'text-font': ['Noto Sans Bold'], 'text-transform': 'uppercase', 'text-letter-spacing': 0.1, 'text-padding': 8, 'symbol-sort-key': ['-', ['to-number', ['get', 'area_km2'], 0]] }) as never,
        paint: labelPaint('#364540', 1.5) as never
      },
      {
        id: 'ohm-label-major-place', type: 'symbol', source: 'ohm', 'source-layer': 'place_points_centroids', maxzoom: 6.5, filter: filter('ohm-label-major-place'),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 0, 10, 6, 13], { 'text-transform': 'uppercase', 'text-letter-spacing': 0.09, 'text-padding': 8 }) as never,
        paint: labelPaint('#52605c', 1.4) as never
      },
      {
        id: 'ohm-label-regional-admin', type: 'symbol', source: 'ohm', 'source-layer': 'land_ohm_centroids', minzoom: 3, maxzoom: 6.5, filter: filter('ohm-label-regional-admin'),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 3, 10, 6, 13], { 'text-font': ['Noto Sans Regular'], 'text-letter-spacing': 0.08, 'symbol-sort-key': ['-', ['to-number', ['get', 'area_km2'], 0]] }) as never,
        paint: labelPaint('#46534f', 1.35) as never
      },
      {
        id: 'ohm-label-capitals', type: 'symbol', source: 'ohm', 'source-layer': 'place_points_centroids', minzoom: 3, maxzoom: 9, filter: filter('ohm-label-capitals'),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 3, 11, 8, 14], { 'text-font': ['Noto Sans Bold'], 'text-offset': [0, 0.85], 'text-anchor': 'top' }) as never,
        paint: labelPaint('#263733', 1.4) as never
      },
      {
        id: 'ohm-label-cities', type: 'symbol', source: 'ohm', 'source-layer': 'place_points_centroids', minzoom: 3.8, maxzoom: 10, filter: filter('ohm-label-cities'),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 4, 10, 9, 13], { 'text-offset': [0, 0.75], 'text-anchor': 'top' }) as never,
        paint: labelPaint() as never
      },
      {
        id: 'ohm-label-towns', type: 'symbol', source: 'ohm', 'source-layer': 'place_points_centroids', minzoom: 6, maxzoom: 12, filter: filter('ohm-label-towns'),
        layout: labelLayout(['interpolate', ['linear'], ['zoom'], 6, 9, 11, 12], { 'text-offset': [0, 0.7], 'text-anchor': 'top' }) as never,
        paint: labelPaint('#40504b', 1.1) as never
      },
      {
        id: 'ohm-label-local-admin', type: 'symbol', source: 'ohm', 'source-layer': 'land_ohm_centroids', minzoom: 6, maxzoom: 11, filter: filter('ohm-label-local-admin'),
        layout: labelLayout(10, { 'text-letter-spacing': 0.06 }) as never,
        paint: labelPaint('#59635f', 1.1) as never
      },
      {
        id: 'ohm-label-water', type: 'symbol', source: 'ohm', 'source-layer': 'water_areas_centroids', minzoom: 8, filter: filter('ohm-label-water'),
        layout: labelLayout(10, { 'text-font': ['Noto Sans Italic'], 'text-letter-spacing': 0.04 }) as never,
        paint: labelPaint('#587774', 1) as never
      },
      {
        id: 'ohm-label-routes', type: 'symbol', source: 'ohm', 'source-layer': 'transport_lines', minzoom: 8, filter: filter('ohm-label-routes'),
        layout: labelLayout(9, { 'symbol-placement': 'line', 'text-font': ['Noto Sans Italic'], 'text-letter-spacing': 0.05 }) as never,
        paint: labelPaint('#756754', 1) as never
      },
      {
        id: 'ohm-label-local-places', type: 'symbol', source: 'ohm', 'source-layer': 'place_points_centroids', minzoom: 10, filter: filter('ohm-label-local-places'),
        layout: labelLayout(10, { 'text-offset': [0, 0.65], 'text-anchor': 'top' }) as never,
        paint: labelPaint('#4b5652', 1) as never
      },
      {
        id: 'ohm-label-archaeology', type: 'symbol', source: 'ohm', 'source-layer': 'other_points_centroids', minzoom: 11, filter: filter('ohm-label-archaeology'),
        layout: labelLayout(10, { 'text-font': ['Noto Sans Italic'], 'text-offset': [0, 0.65], 'text-anchor': 'top' }) as never,
        paint: labelPaint('#704e42', 1.1) as never
      },
      {
        id: 'ohm-label-buildings', type: 'symbol', source: 'ohm', 'source-layer': 'buildings_points_centroids', minzoom: 15, filter: filter('ohm-label-buildings'),
        layout: labelLayout(10) as never,
        paint: labelPaint('#4f4c47', 1) as never
      },
      {
        id: 'ohm-label-addresses', type: 'symbol', source: 'ohm', 'source-layer': 'address_points', minzoom: 17, filter: filter('ohm-label-addresses'),
        layout: {
          ...labelLayout(9),
          'text-field': ['coalesce', ['get', 'name'], ['get', 'addr_housename']]
        } as never,
        paint: labelPaint('#5c5954', 0.9) as never
      }
    ]
  };
}

export function updateOhmYear(map: MapLibreMap, year: number, lens: HistoricalLens = 'all'): void {
  for (const layerId of OHM_TEMPORAL_LAYER_IDS) {
    if (map.getLayer(layerId)) map.setFilter(layerId, ohmFilterForLayer(layerId, year, lens) as never);
  }
}

const originalOhmPaint = new WeakMap<MapLibreMap, Map<string, Map<string, unknown>>>();

/** Recolour matching live detail while retaining its original point/line/polygon geometry. */
export function applyOhmLensAppearance(
  map: MapLibreMap,
  lens: HistoricalLens = 'all'
): void {
  let savedByLayer = originalOhmPaint.get(map);
  if (!savedByLayer) {
    savedByLayer = new Map();
    originalOhmPaint.set(map, savedByLayer);
  }
  for (const layerId of OHM_TEMPORAL_LAYER_IDS) {
    const layer = map.getLayer(layerId);
    if (!layer) continue;
    const properties =
      layer.type === 'fill'
        ? ['fill-color', 'fill-opacity']
        : layer.type === 'line'
          ? ['line-color', 'line-opacity']
          : layer.type === 'circle'
            ? ['circle-color', 'circle-opacity']
            : layer.type === 'symbol'
              ? ['text-color', 'text-opacity']
              : [];
    if (!properties.length) continue;
    let saved = savedByLayer.get(layerId);
    if (!saved) {
      saved = new Map();
      for (const property of properties) {
        saved.set(property, map.getPaintProperty(layerId, property as never));
      }
      savedByLayer.set(layerId, saved);
    }
    if (lens === 'all') {
      for (const [property, value] of saved) {
        map.setPaintProperty(layerId, property as never, value as never);
      }
      continue;
    }
    const accent = lensDefinition(lens).accent;
    const updates =
      layer.type === 'fill'
        ? { 'fill-color': accent, 'fill-opacity': 0.28 }
        : layer.type === 'line'
          ? { 'line-color': accent, 'line-opacity': 0.76 }
          : layer.type === 'circle'
            ? { 'circle-color': accent, 'circle-opacity': 0.9 }
            : { 'text-color': accent, 'text-opacity': 0.9 };
    for (const [property, value] of Object.entries(updates)) {
      map.setPaintProperty(layerId, property as never, value as never);
    }
  }
}

export function setOhmLayerVisibility(
  map: MapLibreMap,
  mode: HistoricalLayerMode,
  lens: HistoricalLens = 'all'
): void {
  applyOhmLensAppearance(map, lens);
  for (const layerId of [...OHM_DETAIL_LAYER_IDS, ...OHM_LABEL_LAYER_IDS]) {
    const supportsLens = lens === 'all' || ohmLensFilter(layerId, lens) !== false;
    const visible = mode !== 'reviewed' && supportsLens ? 'visible' : 'none';
    if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', visible);
  }
}
