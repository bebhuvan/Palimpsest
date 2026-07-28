import type {
  Map as MapLibreMap,
  MapGeoJSONFeature,
  MapMouseEvent,
  MapSourceDataEvent
} from 'maplibre-gl';
import {
  FILL_LAYER,
  MAP_SOURCE,
  REVIEWED_LABEL_LAYER,
  REVIEWED_PLACE_LABEL_LAYER,
  REVIEWED_PLACE_POINT_LAYER,
  THEME_DISCOVERY_LAYER,
  THEME_POINT_LAYER
} from '$lib/map-presentation';
import { OHM_INTERACTIVE_LAYER_IDS } from '$lib/ohm';

export interface MapInteractionCallbacks {
  onReviewedFeature: (
    feature: MapGeoJSONFeature,
    longitude: number,
    latitude: number
  ) => void;
  onOhmFeature: (
    feature: MapGeoJSONFeature,
    longitude: number,
    latitude: number
  ) => void;
  onHoveredFeature: (featureId: string | null) => void;
  onDetailLimitChange: (reached: boolean) => void;
  onReviewedSourceLoaded: () => void;
  onResize: () => void;
  reviewedDetailVisible: () => boolean;
}

const REVIEWED_INTERACTIVE_LAYERS = [
  THEME_DISCOVERY_LAYER,
  THEME_POINT_LAYER,
  REVIEWED_PLACE_LABEL_LAYER,
  REVIEWED_LABEL_LAYER,
  REVIEWED_PLACE_POINT_LAYER,
  FILL_LAYER
];

export function bindMapInteractions(
  map: MapLibreMap,
  callbacks: MapInteractionCallbacks
): () => void {
  const availableLayers = (layerIds: readonly string[]): string[] =>
    layerIds.filter((layerId) => Boolean(map.getLayer(layerId)));

  const onMouseMove = (event: MapMouseEvent): void => {
    const reviewedLayers = availableLayers(REVIEWED_INTERACTIVE_LAYERS);
    const reviewed = reviewedLayers.length
      ? map.queryRenderedFeatures(event.point, { layers: reviewedLayers })
      : [];
    const ohmLayers = availableLayers(OHM_INTERACTIVE_LAYER_IDS);
    const ohm = ohmLayers.length
      ? map.queryRenderedFeatures(event.point, { layers: ohmLayers })
      : [];
    map.getCanvas().style.cursor = reviewed.length || ohm.length ? 'pointer' : '';
    callbacks.onHoveredFeature(
      reviewed[0]?.id === undefined ? null : String(reviewed[0].id)
    );
  };

  const onMouseOut = (): void => {
    map.getCanvas().style.cursor = '';
    callbacks.onHoveredFeature(null);
  };

  const onClick = (event: MapMouseEvent): void => {
    const reviewedLayers = availableLayers(REVIEWED_INTERACTIVE_LAYERS);
    const reviewed = reviewedLayers.length
      ? map.queryRenderedFeatures(event.point, { layers: reviewedLayers })[0]
      : undefined;
    if (reviewed) {
      callbacks.onReviewedFeature(reviewed, event.lngLat.lng, event.lngLat.lat);
      return;
    }

    const ohmLayers = availableLayers(OHM_INTERACTIVE_LAYER_IDS);
    const ohmFeature = ohmLayers.length
      ? map.queryRenderedFeatures(event.point, { layers: ohmLayers })[0]
      : undefined;
    if (ohmFeature) {
      callbacks.onOhmFeature(ohmFeature, event.lngLat.lng, event.lngLat.lat);
    }
  };

  const onZoom = (): void => {
    callbacks.onDetailLimitChange(
      callbacks.reviewedDetailVisible() && map.getZoom() > 7.05
    );
  };

  const onSourceData = (event: MapSourceDataEvent): void => {
    if (event.sourceId === MAP_SOURCE && event.isSourceLoaded) {
      callbacks.onReviewedSourceLoaded();
    }
  };

  map.on('mousemove', onMouseMove);
  map.on('mouseout', onMouseOut);
  map.on('click', onClick);
  map.on('zoom', onZoom);
  map.on('sourcedata', onSourceData);
  window.addEventListener('resize', callbacks.onResize);

  return () => {
    map.off('mousemove', onMouseMove);
    map.off('mouseout', onMouseOut);
    map.off('click', onClick);
    map.off('zoom', onZoom);
    map.off('sourcedata', onSourceData);
    window.removeEventListener('resize', callbacks.onResize);
  };
}
