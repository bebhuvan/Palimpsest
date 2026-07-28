<script lang="ts">
  import { densityProfile, gradeColour, gradeMeaning, type DensityProfile } from '$lib/density';
  import type { CoverageCell } from '$lib/data';
  import {
    formatYear,
    MAXIMUM_YEAR,
    MINIMUM_YEAR,
    parseYearInput,
    scaleForYear,
    stepYear,
    TIMELINE_BANDS,
    TIMELINE_MAX,
    yearForScale
  } from '$lib/history';

  export let selectedYear: number;
  export let playing: boolean;
  export let coverage: CoverageCell[] = [];
  export let dossierYear: number | null = null;
  export let onYearSelect: (year: number) => void;
  export let onPlaybackToggle: () => void;

  let exactYearInput: HTMLInputElement;
  let yearEditorOpen = false;
  let yearDraft = '';
  let yearDraftEra: 'BCE' | 'CE' = 'CE';
  let yearInputError = '';

  $: timelinePosition = scaleForYear(selectedYear);
  $: profile = buildProfile(coverage);
  $: activeBucket = profile.buckets.find(
    (bucket, index) =>
      timelinePosition >= (index * TIMELINE_MAX) / profile.buckets.length &&
      timelinePosition < ((index + 1) * TIMELINE_MAX) / profile.buckets.length
  );

  let cachedCoverage: CoverageCell[] = [];
  let cachedProfile: DensityProfile = { buckets: [], peak: 0 };
  function buildProfile(cells: CoverageCell[]): DensityProfile {
    if (cells !== cachedCoverage) {
      cachedCoverage = cells;
      cachedProfile = densityProfile(cells);
    }
    return cachedProfile;
  }

  const RIBBON_W = 1000;
  const RIBBON_H = 100;

  /**
   * The profile as one drawn shape rather than a row of blocks.
   *
   * Consecutive buckets sharing a dominant confidence grade become a single stepped area,
   * so the ribbon reads as a landscape washed with colour where the evidence changes,
   * under one continuous crisp edge. The steps are never smoothed: coverage genuinely is
   * binned, and interpolating between bins would draw precision the archive does not have.
   */
  function steppedRuns(buckets: { height: number; grade: string }[]): Array<{ grade: string; path: string }> {
    if (!buckets.length) return [];
    const width = RIBBON_W / buckets.length;
    const y = (index: number): number => RIBBON_H - Math.max(1, buckets[index].height * RIBBON_H);
    const runs: Array<{ grade: string; path: string }> = [];
    let start = 0;
    for (let index = 1; index <= buckets.length; index += 1) {
      if (index < buckets.length && buckets[index].grade === buckets[start].grade) continue;
      const end = index - 1;
      let path = `M${(start * width).toFixed(2)},${RIBBON_H}`;
      for (let step = start; step <= end; step += 1) {
        path += ` L${(step * width).toFixed(2)},${y(step).toFixed(2)}`;
        path += ` L${((step + 1) * width).toFixed(2)},${y(step).toFixed(2)}`;
      }
      path += ` L${((end + 1) * width).toFixed(2)},${RIBBON_H} Z`;
      runs.push({ grade: buckets[start].grade, path });
      start = index;
    }
    return runs;
  }

  function silhouette(buckets: { height: number }[]): string {
    if (!buckets.length) return '';
    const width = RIBBON_W / buckets.length;
    let path = '';
    buckets.forEach((bucket, index) => {
      const y = RIBBON_H - Math.max(1, bucket.height * RIBBON_H);
      path += `${index === 0 ? 'M' : ' L'}${(index * width).toFixed(2)},${y.toFixed(2)}`;
      path += ` L${((index + 1) * width).toFixed(2)},${y.toFixed(2)}`;
    });
    return path;
  }

  $: runs = steppedRuns(profile.buckets);
  $: edge = silhouette(profile.buckets);

  // The timeline scale gives each archive band equal width, so a year's horizontal
  // position is not proportional to elapsed time. Marking the real boundary years
  // makes that warp legible instead of leaving it for a footnote.
  $: boundaries = TIMELINE_BANDS.slice(1).map((band, index) => ({
    label: formatYear(band.from),
    percent: (((index + 1) * TIMELINE_MAX) / TIMELINE_BANDS.length / TIMELINE_MAX) * 100
  }));

  function handleTimeline(event: Event): void {
    onYearSelect(yearForScale(Number((event.currentTarget as HTMLInputElement).value)));
  }

  function handleTimelineKey(event: KeyboardEvent): void {
    let amount = 0;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') amount = event.shiftKey ? -10 : -1;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') amount = event.shiftKey ? 10 : 1;
    if (event.key === 'PageDown') amount = -100;
    if (event.key === 'PageUp') amount = 100;
    if (event.key === 'Home') {
      event.preventDefault();
      onYearSelect(MINIMUM_YEAR);
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      onYearSelect(MAXIMUM_YEAR);
      return;
    }
    if (amount) {
      event.preventDefault();
      onYearSelect(stepYear(selectedYear, amount));
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
    onYearSelect(parsed);
    yearEditorOpen = false;
  }
</script>

<section class="timeline" id="timeline" tabindex="-1" aria-label="Historical timeline">
  <div class="transport">
    <button
      class="play"
      onclick={onPlaybackToggle}
      aria-label={playing ? 'Pause changing years' : 'Play changing years'}
      aria-pressed={playing}
    >
      {#if playing}<span class="pause-icon" aria-hidden="true"></span>{:else}<span class="play-icon" aria-hidden="true"></span>{/if}
    </button>

    <button
      class="year"
      onclick={openYearEditor}
      aria-expanded={yearEditorOpen}
      aria-controls="year-editor"
      aria-label={`Selected year ${formatYear(selectedYear)}. Set an exact year`}
    >
      <span class="value"><strong class="hj-numeral">{Math.abs(selectedYear)}</strong><em>{selectedYear < 0 ? 'BCE' : 'CE'}</em></span>
      <small>Set exact year</small>
    </button>

    {#if yearEditorOpen}
      <form class="year-editor" id="year-editor" onsubmit={submitYear}>
        <label>
          <span class="hj-label">Year</span>
          <input
            bind:this={exactYearInput}
            bind:value={yearDraft}
            inputmode="numeric"
            aria-describedby={yearInputError ? 'year-error' : undefined}
          />
        </label>
        <label>
          <span class="hj-label">Era</span>
          <select bind:value={yearDraftEra}><option>BCE</option><option>CE</option></select>
        </label>
        <button type="submit">Go</button>
        <button type="button" class="editor-close" onclick={() => (yearEditorOpen = false)} aria-label="Close exact year entry">×</button>
        {#if yearInputError}<p id="year-error" role="alert">{yearInputError}</p>{/if}
      </form>
    {/if}

    {#if dossierYear !== null}
      <a class="read-year" href={`/year?year=${dossierYear}`}>Read the year <span aria-hidden="true">→</span></a>
    {/if}

    <div class="steps">
      <button onclick={() => onYearSelect(stepYear(selectedYear, -100))} aria-label="Go back 100 years">−100</button>
      <button onclick={() => onYearSelect(stepYear(selectedYear, 100))} aria-label="Go forward 100 years">+100</button>
    </div>
  </div>

  <div class="scale">
    <div class="ribbon" aria-hidden="true">
      {#if profile.peak}
        <svg class="profile" viewBox={`0 0 ${RIBBON_W} ${RIBBON_H}`} preserveAspectRatio="none">
          {#each runs as run, index (index)}
            <path d={run.path} fill={gradeColour(run.grade)} opacity="0.3" />
          {/each}
          <path d={edge} fill="none" class="edge" vector-effect="non-scaling-stroke" />
        </svg>
      {:else}
        <i class="ribbon-pending"></i>
      {/if}

      {#each boundaries as boundary}
        <span class="boundary" style={`left: ${boundary.percent}%`}><b class="hj-numeral">{boundary.label}</b></span>
      {/each}

      <span class="cursor" style={`left: ${(timelinePosition / TIMELINE_MAX) * 100}%`}></span>
    </div>

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

    <p class="ribbon-caption">
      {#if profile.peak}
        <span>Archive density · {activeBucket ? `${activeBucket.count.toLocaleString('en')} features recorded at ${formatYear(selectedYear)}` : 'features recorded per year'}</span>
        {#if activeBucket}
          <span class="grade" style={`--c: ${gradeColour(activeBucket.grade)}`}>
            <i></i>{gradeMeaning(activeBucket.grade)} dominates
          </span>
        {/if}
      {:else}
        <span>Reading archive coverage…</span>
      {/if}
    </p>
  </div>

  <p class="credit">
    <a href="https://www.openhistoricalmap.org/copyright" target="_blank" rel="noreferrer">OpenHistoricalMap</a>
    <a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">Natural Earth</a>
    <a href="https://seshatdatabank.info/" target="_blank" rel="noreferrer">Seshat</a>
    <a href="https://github.com/JustusBuitelaar/cliopatria" target="_blank" rel="noreferrer">Cliopatria</a>
  </p>
</section>

<svelte:window onkeydown={(event) => { if (event.key === 'Escape' && yearEditorOpen) yearEditorOpen = false; }} />

<style>
  .timeline {
    position: absolute;
    z-index: 8;
    right: 0;
    bottom: 0;
    left: 0;
    height: var(--timeline-height);
    display: grid;
    grid-template-columns: 268px minmax(280px, 1fr) auto;
    align-items: center;
    gap: var(--s-6);
    padding: 0 var(--s-5) 0 var(--s-5);
    border-top: 1px solid var(--line-strong);
    background: var(--surface);
  }

  .transport { position: relative; display: flex; align-items: center; gap: var(--s-4); }

  .play {
    flex: none;
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--accent-line);
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
    cursor: pointer;
    transition: background 0.2s var(--ease), border-color 0.2s var(--ease), color 0.2s var(--ease);
  }
  .play:hover { border-color: var(--accent); background: var(--accent); color: #fff; }
  .play-icon { width: 0; height: 0; margin-left: 2px; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 8px solid currentColor; }
  .pause-icon { width: 9px; height: 10px; border-right: 3px solid currentColor; border-left: 3px solid currentColor; }

  .year {
    display: grid;
    gap: 3px;
    padding: 0;
    border: 0;
    background: none;
    color: var(--text);
    cursor: pointer;
    text-align: left;
  }
  .value { display: flex; align-items: baseline; gap: 7px; }
  .year strong { font-family: var(--font-display); font-size: var(--t-2xl); font-weight: 400; line-height: 1; letter-spacing: -0.02em; }
  .year em { color: var(--text-dim); font-size: var(--t-sm); font-style: normal; font-weight: 500; letter-spacing: 0.06em; }
  .year small { color: var(--text-faint); font-size: var(--t-xs); letter-spacing: 0.03em; white-space: nowrap; }
  .year:hover small { color: var(--text-dim); }

  /* The dossiers are the reason this project exists, so when one covers the year in
     view it is offered next to the year itself rather than buried in a menu. */
  .read-year {
    padding: 6px var(--s-3);
    border: 1px solid var(--accent);
    background: var(--accent);
    color: #fff;
    font-size: var(--t-xs);
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
  }
  .read-year:hover { background: var(--accent-hover); border-color: var(--accent-hover); }

  .steps { margin-left: auto; display: flex; }
  .steps button {
    height: 30px;
    padding: 0 var(--s-2);
    border: 1px solid var(--line);
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    font-size: var(--t-xs);
    font-variant-numeric: tabular-nums;
  }
  .steps button:first-child { border-right: 0; }
  .steps button:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }

  .year-editor {
    position: absolute;
    z-index: 5;
    bottom: 52px;
    left: 0;
    width: 268px;
    display: grid;
    grid-template-columns: 1fr 74px 44px;
    gap: var(--s-2);
    padding: var(--s-4);
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: 0 18px 40px rgb(20 23 42 / 0.10);
  }
  .year-editor label { display: flex; flex-direction: column; gap: var(--s-1); color: var(--text-faint); }
  .year-editor input, .year-editor select {
    min-width: 0;
    height: 34px;
    padding: 0 var(--s-2);
    border: 1px solid var(--line-strong);
    border-radius: 0;
    background: var(--surface);
    color: var(--text);
    font-size: var(--t-sm);
  }
  .year-editor button[type='submit'] {
    align-self: end;
    height: 34px;
    border: 0;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    font-size: var(--t-xs);
    font-weight: 600;
  }
  .year-editor .editor-close {
    position: absolute;
    top: -1px;
    right: -30px;
    width: 29px;
    height: 29px;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--text-dim);
    cursor: pointer;
  }
  .year-editor p { grid-column: 1 / -1; margin: 0; color: var(--conf-d); font-size: var(--t-xs); }

  /* The signature: a stepped profile of what the release actually holds, coloured
     by the confidence grade that dominates each point in time. */
  .scale { position: relative; height: 100%; display: flex; flex-direction: column; justify-content: center; gap: var(--s-2); padding-top: var(--s-3); }

  /* A baseline runs the full width so a near-empty stretch reads as coverage that was
     measured and found thin, rather than as a control that failed to render. */
  .ribbon { position: relative; height: 38px; }
  .profile { display: block; width: 100%; height: 100%; }
  .edge { stroke: var(--text); stroke-width: 1; stroke-opacity: 0.58; stroke-linejoin: round; }
  .ribbon:hover .edge { stroke-opacity: 0.72; }
  .ribbon::after {
    content: '';
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    height: 1px;
    background: var(--line-strong);
  }
  .ribbon-pending { position: absolute; right: 0; bottom: 0; left: 0; height: 1px; background: var(--line); }

  .boundary { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--line-strong); opacity: 0.7; }
  .boundary b {
    position: absolute;
    top: -15px;
    left: 5px;
    color: var(--text-faint);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  .cursor { position: absolute; top: -7px; bottom: -3px; width: 1px; background: var(--accent); pointer-events: none; }
  .cursor::before {
    content: '';
    position: absolute;
    top: -2px;
    left: -3px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 3px var(--surface);
  }

  .scale input {
    position: absolute;
    z-index: 3;
    top: var(--s-3);
    left: 0;
    width: 100%;
    height: 40px;
    margin: 0;
    appearance: none;
    background: transparent;
    cursor: ew-resize;
  }
  .scale input::-webkit-slider-runnable-track { height: 40px; background: transparent; }
  .scale input::-moz-range-track { height: 40px; background: transparent; }
  .scale input::-webkit-slider-thumb { width: 18px; height: 40px; appearance: none; background: transparent; }
  .scale input::-moz-range-thumb { width: 18px; height: 40px; border: 0; background: transparent; }
  .scale input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .ribbon-caption {
    display: flex;
    gap: var(--s-4);
    margin: 0;
    color: var(--text-faint);
    font-size: var(--t-xs);
    letter-spacing: 0.01em;
  }
  .ribbon-caption .grade { display: inline-flex; align-items: center; gap: 6px; color: var(--text-dim); }
  .ribbon-caption .grade i { width: 8px; height: 8px; flex: none; background: var(--c); }

  .credit { display: flex; gap: var(--s-3); margin: 0; }
  .credit a {
    color: var(--text-faint);
    font-size: var(--t-xs);
    text-decoration: none;
    white-space: nowrap;
    border-bottom: 1px solid transparent;
  }
  .credit a:hover { color: var(--accent); border-bottom-color: var(--accent-line); }

  @media (max-width: 1180px) {
    .timeline { grid-template-columns: 210px minmax(240px, 1fr); gap: var(--s-5); }
    .credit { display: none; }
  }

  @media (max-width: 860px) {
    .timeline {
      height: var(--timeline-height);
      grid-template-columns: 1fr;
      grid-template-rows: auto auto;
      align-content: center;
      gap: 6px;
      padding-inline: var(--s-4);
    }
    .ribbon-caption { font-size: 10px; }
    .transport { gap: var(--s-2); }
    .read-year { padding-inline: var(--s-2); }
    .year strong { font-size: var(--t-xl); }
    .year small { display: none; }
    .scale { height: auto; padding-top: 0; }
    .ribbon { height: 26px; }
    .boundary b { display: none; }
    .ribbon-caption .grade { display: none; }
    .year-editor { bottom: 46px; width: min(268px, calc(100vw - 32px)); }
  }
</style>
