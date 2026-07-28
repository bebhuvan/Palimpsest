<script lang="ts">
  import type { HistoricalMapMetadata } from '$lib/data';
  import { eraLabel, formatYear, type Era } from '$lib/history';
  import type { HistoricalLayerMode } from '$lib/ohm';

  let {
    open,
    selectedYear,
    activeEra,
    loadingEra,
    layerMode,
    evidenceOverlay,
    layerCatalogReady,
    historicalMaps,
    selectedHistoricalMapId,
    historicalMapVisible,
    historicalMapLoading,
    historicalMapError,
    activeHistoricalMap,
    onClose,
    onLayerModeSelect,
    onEvidenceOverlaySelect,
    onHistoricalMapSelect,
    onHistoricalMapToggle
  }: {
    open: boolean;
    selectedYear: number;
    activeEra: Era;
    loadingEra: boolean;
    layerMode: HistoricalLayerMode;
    evidenceOverlay: 'none' | 'confidence' | 'provenance';
    layerCatalogReady: boolean;
    historicalMaps: HistoricalMapMetadata[];
    selectedHistoricalMapId: string;
    historicalMapVisible: boolean;
    historicalMapLoading: boolean;
    historicalMapError: string;
    activeHistoricalMap: HistoricalMapMetadata | null;
    onClose: () => void;
    onLayerModeSelect: (mode: HistoricalLayerMode) => void;
    onEvidenceOverlaySelect: (overlay: 'none' | 'confidence' | 'provenance') => void;
    onHistoricalMapSelect: (mapId: string) => void;
    onHistoricalMapToggle: () => void;
  } = $props();

  const LAYER_MODES: Array<{ id: HistoricalLayerMode; label: string; note: string }> = [
    { id: 'combined', label: 'Combined', note: 'Contributor detail beneath reviewed reconstruction' },
    { id: 'historical-detail', label: 'Contributor detail', note: 'OpenHistoricalMap only' },
    { id: 'reviewed', label: 'Reviewed', note: 'Reconstruction over physical geography only' }
  ];

  const OVERLAYS: Array<{ id: 'none' | 'confidence' | 'provenance'; label: string; note: string }> = [
    { id: 'none', label: 'Off', note: 'Shapes carry no evidence shading' },
    { id: 'confidence', label: 'Confidence', note: 'Shade by interpretive confidence grade' },
    { id: 'provenance', label: 'Provenance', note: 'Shade by the source that supplied the shape' }
  ];
</script>

{#if open}
  <aside class="view-panel" aria-label="Map layers and evidence">
    <header>
      <p class="hj-label">View</p>
      <button onclick={onClose} aria-label="Close view controls">×</button>
    </header>

    <div class="body">
      <p class="archive-note">
        Reading the <strong>{eraLabel(activeEra).replace('Archive · ', '')}</strong> archive at {formatYear(selectedYear)}{loadingEra ? ' · changing archive' : ''}
      </p>

      <div class="group" role="group" aria-labelledby="group-sources">
        <p class="hj-label" id="group-sources">Map sources</p>
        {#each LAYER_MODES as mode (mode.id)}
          <button
            class:active={layerMode === mode.id}
            aria-pressed={layerMode === mode.id}
            onclick={() => onLayerModeSelect(mode.id)}
          >
            <span>{mode.label}</span>
            <small>{mode.note}</small>
          </button>
        {/each}
      </div>

      <div class="group" role="group" aria-labelledby="group-evidence">
        <p class="hj-label" id="group-evidence">Evidence shading</p>
        {#each OVERLAYS as overlay (overlay.id)}
          <button
            class:active={evidenceOverlay === overlay.id}
            aria-pressed={evidenceOverlay === overlay.id}
            disabled={overlay.id !== 'none' && !layerCatalogReady}
            onclick={() => onEvidenceOverlaySelect(overlay.id)}
          >
            <span>{overlay.label}</span>
            <small>{overlay.note}</small>
          </button>
        {/each}
      </div>

      {#if historicalMaps.length}
        <div class="group historical-map-control" role="group" aria-labelledby="group-image">
          <p class="hj-label" id="group-image">Historical map image</p>
          <div class="image-control">
            <select
              aria-label="Approved historical map image"
              disabled={historicalMapLoading}
              value={selectedHistoricalMapId}
              onchange={(event) => onHistoricalMapSelect(event.currentTarget.value)}
            >
              {#each historicalMaps as historicalMap (historicalMap.map_id)}
                <option value={historicalMap.map_id}>{historicalMap.label}</option>
              {/each}
            </select>
            <button
              class:active={historicalMapVisible}
              aria-pressed={historicalMapVisible}
              aria-label={`${historicalMapVisible ? 'Hide' : 'Show'} historical map image`}
              disabled={historicalMapLoading}
              onclick={onHistoricalMapToggle}
            >{historicalMapLoading ? 'Loading' : historicalMapVisible ? 'Hide' : 'Show'}</button>
          </div>

          {#if historicalMapVisible && activeHistoricalMap}
            <div class="image-detail" aria-label="Historical map image details">
              <p class="caption">A source depiction. Palimpsest does not treat a scan as authoritative geography, or as agreement with reviewed geometry.</p>
              <dl>
                <div><dt>Depicted</dt><dd>{activeHistoricalMap.depicted_date}</dd></div>
                <div><dt>Provider</dt><dd>{activeHistoricalMap.providers.join(', ')}</dd></div>
                <div><dt>Attribution</dt><dd>{activeHistoricalMap.required_statement}</dd></div>
                <div><dt>Image licence</dt><dd>{activeHistoricalMap.image_rights.license_id}</dd></div>
                <div><dt>Georeference</dt><dd>{activeHistoricalMap.georeference_confidence.grade} · {activeHistoricalMap.georeference_confidence.rationale}</dd></div>
              </dl>
              <details>
                <summary>Known limitations</summary>
                <ul>{#each activeHistoricalMap.known_limitations as limitation}<li>{limitation}</li>{/each}</ul>
              </details>
              <a href={activeHistoricalMap.manifest_id} target="_blank" rel="noreferrer">Open the approved IIIF manifest <span aria-hidden="true">↗</span></a>
            </div>
          {/if}
        </div>
      {/if}

      {#if historicalMapError}
        <p class="error" role="alert">{historicalMapError}</p>
      {/if}
    </div>
  </aside>
{/if}

<style>
  .view-panel {
    position: absolute;
    z-index: 10;
    top: 0;
    bottom: var(--timeline-height);
    left: var(--rail-width);
    width: 336px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--line-strong);
    background: var(--surface);
    color: var(--text);
    box-shadow: 24px 0 60px rgb(20 23 42 / 0.10);
  }

  header { flex: none; display: flex; align-items: center; justify-content: space-between; padding: var(--s-4) var(--s-4) var(--s-4) var(--s-5); border-bottom: 1px solid var(--line); color: var(--text-faint); }
  header button { width: 28px; height: 28px; border: 0; background: transparent; color: var(--text-dim); cursor: pointer; font-size: 20px; line-height: 1; }
  header button:hover { color: var(--text); }

  .body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding-bottom: var(--s-5); }

  .archive-note { margin: 0; padding: var(--s-4) var(--s-5); border-bottom: 1px solid var(--hover); color: var(--text-dim); font-size: var(--t-sm); line-height: var(--lh-snug); }
  .archive-note strong { color: var(--text); font-weight: 500; }

  .group { padding: var(--s-4) 0 var(--s-3); border-bottom: 1px solid var(--hover); }
  .group > .hj-label { padding: 0 var(--s-5) var(--s-3); color: var(--text-faint); }

  .group > button {
    width: 100%;
    display: grid;
    gap: 2px;
    padding: var(--s-3) var(--s-5);
    border: 0;
    border-left: 2px solid transparent;
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    text-align: left;
    transition: background 0.18s var(--ease), color 0.18s var(--ease);
  }
  .group > button span { font-size: var(--t-sm); font-weight: 500; }
  .group > button small { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.45; }
  .group > button:hover:not(:disabled) { background: var(--hover); color: var(--text); }
  .group > button.active { border-left-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
  .group > button:disabled { opacity: 0.4; cursor: not-allowed; }

  .image-control { display: flex; gap: var(--s-2); padding: 0 var(--s-5); }
  .image-control select {
    min-width: 0;
    flex: 1;
    height: 34px;
    padding: 0 var(--s-2);
    border: 1px solid var(--line-strong);
    border-radius: 0;
    background: var(--surface);
    color: var(--text);
    font-size: var(--t-sm);
  }
  .image-control button {
    flex: none;
    padding: 0 var(--s-3);
    border: 1px solid var(--line-strong);
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    font-size: var(--t-xs);
    font-weight: 600;
  }
  .image-control button.active { border-color: var(--accent); background: var(--accent); color: #fff; }
  .image-control button:disabled { opacity: 0.45; cursor: wait; }

  .image-detail { padding: var(--s-4) var(--s-5) 0; }
  .caption { margin: 0 0 var(--s-3); color: var(--text-faint); font-size: var(--t-xs); line-height: var(--lh-body); }
  .image-detail dl { margin: 0 0 var(--s-3); border-top: 1px solid var(--line); }
  .image-detail dl div { display: grid; grid-template-columns: 92px 1fr; gap: var(--s-2); padding: 6px 0; border-bottom: 1px solid var(--hover); }
  .image-detail dt { color: var(--text-faint); font-size: var(--t-xs); }
  .image-detail dd { margin: 0; color: var(--text-dim); font-size: var(--t-xs); line-height: 1.5; overflow-wrap: anywhere; }
  .image-detail details { color: var(--text-faint); font-size: var(--t-xs); line-height: var(--lh-body); }
  .image-detail summary { cursor: pointer; }
  .image-detail ul { margin: var(--s-2) 0; padding-left: var(--s-4); }
  .image-detail a { display: inline-block; margin-top: var(--s-3); color: var(--accent); font-size: var(--t-xs); font-weight: 500; text-underline-offset: 3px; }

  .error { margin: var(--s-4) var(--s-5) 0; padding: var(--s-3); border-left: 2px solid var(--conf-d); background: var(--hover); color: var(--conf-d); font-size: var(--t-xs); line-height: var(--lh-body); }

  @media (max-width: 860px) {
    .view-panel {
      inset: auto 0 calc(var(--timeline-height) + 58px) 0;
      top: auto;
      width: 100%;
      max-height: 58dvh;
      border-right: 0;
      border-top: 1px solid var(--line);
      box-shadow: 0 -20px 50px rgb(20 23 42 / 0.10);
    }
  }
</style>
