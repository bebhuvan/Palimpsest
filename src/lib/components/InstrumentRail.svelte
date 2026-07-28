<script lang="ts">
  import LensMark from '$lib/components/LensMark.svelte';
  import { HISTORICAL_LENSES, type HistoricalLens } from '$lib/lenses';
  import { formatYear } from '$lib/history';

  let {
    activeLens,
    selectedYear,
    lensCounts,
    viewOpen,
    searchOpen,
    onLensSelect,
    onSearchOpen,
    onViewToggle,
    onAbout
  }: {
    activeLens: HistoricalLens;
    selectedYear: number;
    lensCounts: Map<HistoricalLens, number>;
    viewOpen: boolean;
    searchOpen: boolean;
    onLensSelect: (lens: HistoricalLens) => void;
    onSearchOpen: () => void;
    onViewToggle: () => void;
    onAbout: () => void;
  } = $props();
</script>

<nav class="rail" aria-label="Palimpsest instrument">
  <a class="brand" href="/" aria-label="Palimpsest home">
    <span class="brand-mark" aria-hidden="true"></span>
    <span class="brand-name"><em>History</em><em>Joice</em></span>
  </a>

  <button class="tool" onclick={onSearchOpen} aria-expanded={searchOpen} aria-label="Search historical places">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.6" /><path d="m15.8 15.8 4.9 4.9" /></svg>
    <span>Search</span>
    <kbd aria-hidden="true">/</kbd>
  </button>

  <div class="group" role="group" aria-label="Historical lens">
    <p class="hj-label group-label">Lens</p>
    <p class="group-note">Records at {formatYear(selectedYear)}</p>
    {#each HISTORICAL_LENSES as lens (lens.id)}
      <!-- The visible label is dropped on narrow screens, so the accessible name is
           declared explicitly rather than inherited from text CSS may hide. -->
      <button
        class="lens"
        class:active={activeLens === lens.id}
        aria-pressed={activeLens === lens.id}
        aria-label={lens.label}
        title={lens.description}
        onclick={() => onLensSelect(lens.id)}
      >
        <LensMark lens={lens.id} />
        <span class="lens-name">{lens.shortLabel}</span>
        <span class="lens-count hj-numeral" class:none={(lensCounts.get(lens.id) ?? 0) === 0}>
          {(lensCounts.get(lens.id) ?? 0).toLocaleString('en')}
        </span>
      </button>
    {/each}

  </div>

  <div class="tools">
  <button class="tool" class:active={viewOpen} onclick={onViewToggle} aria-expanded={viewOpen} aria-label="Map layers and evidence overlays">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6 3.4 8 12 12.4 20.6 8Z" /><path d="m3.4 13 8.6 4.4 8.6-4.4" /></svg>
    <span>View</span>
  </button>

  <a class="tool" href={`/browse?year=${selectedYear}${activeLens !== 'all' ? `&lens=${activeLens}` : ''}`}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
    <span>Browse</span>
  </a>

  <button class="tool" onclick={onAbout} aria-label="About this map">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.4" /><path d="M12 11v5.4M12 7.9v.1" /></svg>
    <span>About</span>
  </button>
  </div>
</nav>

<style>
  .rail {
    position: absolute;
    z-index: 9;
    top: 0;
    bottom: var(--timeline-height);
    left: 0;
    width: var(--rail-width);
    display: flex;
    flex-direction: column;
    align-items: stretch;
    padding: var(--s-3) 0 var(--s-2);
    overflow-y: auto;
    scrollbar-width: none;
    border-right: 1px solid var(--line-strong);
    background: var(--surface);
  }
  .rail::-webkit-scrollbar { display: none; }

  .brand {
    display: grid;
    justify-items: start;
    gap: var(--s-3);
    padding: var(--s-3) var(--s-3) var(--s-5) calc(var(--s-3) - 1px);
    color: var(--text);
    text-decoration: none;
  }
  .brand-mark {
    width: 26px;
    height: 26px;
    border: 1px solid var(--accent);
    /* A meridian: the instrument's own mark, not a logo. */
    background: linear-gradient(to right, transparent calc(50% - 0.5px), var(--accent) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px));
  }
  /* Two words, two lines, optically aligned — not a wrapped string breaking wherever the
     column happens to end. */
  .brand-name { display: grid; }
  .brand-name em {
    font-family: var(--font-display);
    font-size: var(--t-md);
    font-style: normal;
    font-weight: 400;
    line-height: 1.08;
    letter-spacing: -0.022em;
  }

  .tool {
    position: relative;
    display: grid;
    grid-template-columns: 16px minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-3) var(--s-3) var(--s-3) calc(var(--s-3) - 1px);
    border: 0;
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    font-size: var(--t-xs);
    font-weight: 500;
    text-align: left;
    text-decoration: none;
    transition: color 0.18s var(--ease), background 0.18s var(--ease);
  }
  .tool:hover { background: var(--hover); color: var(--text); }
  .tool.active { background: var(--accent-soft); color: var(--accent); }
  .tool svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.4; stroke-linecap: round; stroke-linejoin: round; }
  .tool kbd {
    padding: 1px 5px;
    border: 1px solid var(--line-strong);
    color: var(--text-faint);
    font-family: var(--font-mono);
    font-size: 10px;
  }

  .group { display: flex; flex-direction: column; padding: var(--s-2) 0 var(--s-3); }
  .rail > .tool, .rail > .group { border-top: 1px solid var(--line); }
  .tools { display: flex; flex-direction: column; border-top: 1px solid var(--line); padding-block: var(--s-2); }
  .group-label { padding: var(--s-4) var(--s-3) 3px; color: var(--text-faint); }

  /* Lenses are non-ordinal categories, so they are told apart by mark, not by hue.
     Colour in this interface belongs to the confidence ramp alone. */
  .lens {
    position: relative;
    display: grid;
    grid-template-columns: 16px minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--s-2);
    padding: 9px var(--s-3) 9px calc(var(--s-3) - 1px);
    border: 0;
    background: transparent;
    color: var(--text-faint);
    cursor: pointer;
    text-align: left;
    transition: color 0.18s var(--ease), background 0.18s var(--ease);
  }
  .lens-name { font-size: var(--t-xs); font-weight: 500; letter-spacing: 0.01em; }
  .lens :global(svg) { color: var(--text-dim); transition: color 0.18s var(--ease); }
  .lens:hover :global(svg) { color: var(--text); }
  .lens.active :global(svg) { color: var(--accent); }
  .lens-count { color: var(--text-faint); font-size: 10px; font-variant-numeric: tabular-nums; }
  .lens-count.none { opacity: 0.4; }
  .lens.active .lens-count { color: var(--accent); }
  .lens:hover { background: var(--hover); color: var(--text); }
  .lens.active { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
  .lens.active::before { content: ''; position: absolute; top: 0; bottom: 0; left: 0; width: 2px; background: var(--accent); }

  .group-note {
    margin: 0 0 var(--s-2);
    padding: 0 var(--s-3);
    color: var(--text-faint);
    font-size: 10px;
    line-height: 1.35;
  }


  @media (max-width: 860px) {
    /* On a phone the rail becomes a tool strip. Lens labels drop to their marks so
       navigation stays reachable without scrolling the strip off its own controls. */
    .rail {
      inset: auto 0 var(--timeline-height) 0;
      top: auto;
      width: 100%;
      height: 56px;
      flex-direction: row;
      align-items: stretch;
      padding: 0;
      overflow-x: auto;
      overflow-y: hidden;
      border-right: 0;
      border-top: 1px solid var(--line);
      -webkit-overflow-scrolling: touch;
    }
    .brand { display: none; }
    .tool { flex: none; gap: 3px; padding-inline: var(--s-3); border-top: 0; border-left: 1px solid var(--line); font-size: 10px; }
    .tool:first-of-type { border-left: 0; }
    .tool svg { width: 17px; height: 17px; }
    .tool kbd { display: none; }
    .group { flex-direction: row; border-top: 0; border-left: 1px solid var(--line); padding-bottom: 0; }
    .group-label, .group-note { display: none; }
    .lens { min-width: 46px; grid-template-columns: 1fr; justify-items: center; gap: 2px; padding-inline: var(--s-2); }
    .lens-name { display: none; }
    .lens-count { font-size: 9px; }
    .lens.active::before { inset: auto 0 0 0; width: auto; height: 3px; }
  }
</style>
