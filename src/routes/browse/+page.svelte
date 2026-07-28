<script lang="ts">
  import { onMount } from 'svelte';
  import {
    artifact,
    displayNameForYear,
    loadRelease,
    loadSearchIndex,
    loadSearchPage,
    loadSearchRecord,
    loadSearchTimeBand,
    loadStaticSearchIndex,
    searchStaticRecords,
    searchableNames,
    type LoadedRelease,
    type SearchRecord,
    type StaticSearchIndex
  } from '$lib/data';
  import { eraForYear, eraLabel, formatRange, formatYear, normalizeYear } from '$lib/history';
  import { HISTORICAL_LENSES, isHistoricalLens, lensDefinition, recordMatchesLens, type HistoricalLens } from '$lib/lenses';
  import { availableYears, loadYearIndex } from '$lib/year-data';
  import LensMark from '$lib/components/LensMark.svelte';

  const DATA_BASE = (import.meta.env.VITE_DATA_BASE as string | undefined) || '/data';
  let release: LoadedRelease | null = null;
  let staticSearchIndex: StaticSearchIndex | null = null;
  let records: SearchRecord[] = [];
  let query = '';
  let year: number | null = null;
  let entity = '';
  let lens: HistoricalLens = 'all';
  let loading = true;
  let errorMessage = '';
  let visibleCount = 48;
  let loadedPageCount = 0;
  let filterRequest = 0;
  let yearsWithDossier: Set<number> = new Set();

  $: normalizedQuery = query.trim().toLocaleLowerCase();
  $: filtered = records.filter((record) => {
    const matchesQuery = !normalizedQuery || searchableNames(record).some((name) => name.toLocaleLowerCase().includes(normalizedQuery));
    const matchesEntity = !entity || record.entity_id === entity;
    const matchesLens = recordMatchesLens(record, lens);
    const matchesYear = year === null || recordActiveInYear(record, year);
    return matchesQuery && matchesEntity && matchesLens && matchesYear;
  }).sort(compareRecords);
  $: yearRecords = year === null ? records : records.filter((record) => recordActiveInYear(record, year!));
  $: featuredRecords = filtered.filter((record) => record.entity_id.startsWith('palimpsest:')).slice(0, 6);
  $: featuredIds = new Set(featuredRecords.map((record) => record.entity_id));
  $: showEditorialFrame = year !== null && !normalizedQuery && !entity;
  $: archiveRecords = showEditorialFrame ? filtered.filter((record) => !featuredIds.has(record.entity_id)) : filtered;
  $: exactYearRecords = year === null ? 0 : yearRecords.filter((record) => record.valid_from === year && record.valid_to === year).length;
  $: lensCounts = HISTORICAL_LENSES
    .filter((option) => option.id !== 'all')
    .map((option) => ({ ...option, count: yearRecords.filter((record) => recordMatchesLens(record, option.id)).length }));
  $: selectedLens = lensDefinition(lens);
  $: hasDossier = year !== null && yearsWithDossier.has(year);

  function displayName(record: SearchRecord): string {
    return displayNameForYear(record, year ?? record.valid_from);
  }

  function alternateNames(record: SearchRecord): string[] {
    const names = year === null
      ? searchableNames(record)
      : (record.name_attestations ?? [])
          .filter((name) => name.valid_from <= year! && name.valid_to >= year!)
          .map((name) => name.text);
    return Array.from(new Set(names)).filter((name) => name !== displayName(record));
  }

  function recordActiveInYear(record: SearchRecord, activeYear: number): boolean {
    return record.name_attestations?.length
      ? record.name_attestations.some((name) => name.valid_from <= activeYear && name.valid_to >= activeYear)
      : record.valid_from <= activeYear && record.valid_to >= activeYear;
  }

  function compareRecords(left: SearchRecord, right: SearchRecord): number {
    const leftCurated = left.entity_id.startsWith('palimpsest:') ? 0 : 1;
    const rightCurated = right.entity_id.startsWith('palimpsest:') ? 0 : 1;
    const leftSpan = left.valid_to - left.valid_from;
    const rightSpan = right.valid_to - right.valid_from;
    return leftCurated - rightCurated || leftSpan - rightSpan || displayName(left).localeCompare(displayName(right));
  }

  function sourceLabel(record: SearchRecord): string {
    const sources = record.source_ids ?? [];
    if (sources.some((source) => source.startsWith('loc_'))) return 'Library of Congress';
    if (sources.includes('mlit_tanegashima')) return 'Japan MLIT';
    if (sources.includes('pleiades')) return 'Pleiades';
    if (sources.includes('cliopatria')) return 'Cliopatria';
    return sources[0]?.replaceAll('_', ' ') ?? 'Published source';
  }

  function mapHref(record: SearchRecord): string {
    const activeYear = year && year >= record.valid_from && year <= record.valid_to ? year : record.valid_from;
    const activeFeatureId = record.name_attestations?.find(
      (name) =>
        name.valid_from <= activeYear &&
        name.valid_to >= activeYear &&
        record.feature_ids.includes(name.feature_id)
    )?.feature_id ?? record.feature_ids[0];
    const feature = activeFeatureId
      ? `&feature=${encodeURIComponent(activeFeatureId)}`
      : '';
    return `/?year=${activeYear}&entity=${encodeURIComponent(record.entity_id)}${feature}${lens !== 'all' ? `&lens=${lens}` : ''}`;
  }

  async function refreshRecords(): Promise<void> {
    if (!release) return;
    const request = ++filterRequest;
    let next: SearchRecord[];
    if (!staticSearchIndex) {
      next = records;
    } else if (entity) {
      const record = await loadSearchRecord(release, staticSearchIndex, { entityId: entity });
      next = record ? [record] : [];
    } else if (query.trim().length >= staticSearchIndex.minimum_query_length) {
      next = await searchStaticRecords(release, staticSearchIndex, query);
    } else if (year !== null) {
      next = await loadSearchTimeBand(release, staticSearchIndex, year);
    } else {
      next = await loadSearchPage(release, staticSearchIndex, 0);
      loadedPageCount = next.length ? 1 : 0;
    }
    if (request === filterRequest) records = next;
  }

  function applyYear(event: Event): void {
    const value = (event.currentTarget as HTMLInputElement).value.trim();
    year = value ? normalizeYear(Number(value)) : null;
    visibleCount = 48;
    void refreshRecords();
  }

  async function showMore(): Promise<void> {
    visibleCount += 48;
    if (
      !release ||
      !staticSearchIndex ||
      query.trim() ||
      entity ||
      year !== null ||
      loadedPageCount >= staticSearchIndex.pages.pages.length ||
      visibleCount <= records.length
    ) return;
    const page = await loadSearchPage(release, staticSearchIndex, loadedPageCount);
    records = [...records, ...page];
    loadedPageCount += page.length ? 1 : 0;
  }

  onMount(async () => {
    const params = new URL(window.location.href).searchParams;
    query = params.get('q') ?? '';
    entity = params.get('entity') ?? '';
    const queryLens = params.get('lens');
    if (isHistoricalLens(queryLens)) lens = queryLens;
    const candidateYear = Number(params.get('year'));
    if (Number.isFinite(candidateYear) && candidateYear !== 0) year = normalizeYear(candidateYear);
    try {
      release = await loadRelease(DATA_BASE);
      void loadYearIndex(release).then((index) => {
        yearsWithDossier = availableYears(index);
      });
      staticSearchIndex = await loadStaticSearchIndex(release);
      if (staticSearchIndex) {
        await refreshRecords();
      } else {
        const searchArtifact = artifact(release, 'search.ndjson');
        if (!searchArtifact) throw new Error('This release does not include a searchable record index.');
        records = await loadSearchIndex(release, searchArtifact.path);
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'The record index could not be opened.';
    } finally {
      loading = false;
    }
  });
</script>


<svelte:head>
  <title>{year ? `The world in ${formatYear(year)}` : 'Browse history'} — Palimpsest</title>
  <meta name="description" content={year ? `Explore source-backed places and stories active in ${formatYear(year)}.` : 'An accessible text view of the historical records published in the current Palimpsest release.'} />
</svelte:head>

<header class="masthead">
  <a class="brand" href="/">
    <span class="brand-mark" aria-hidden="true"></span>
    <span>Palimpsest</span>
  </a>
  <a class="to-map" href={`/?${new URLSearchParams({ ...(year ? { year: String(year) } : {}), ...(lens !== 'all' ? { lens } : {}) })}`}>Return to the map <span aria-hidden="true">↗</span></a>
</header>

<main>
  <header class="hero">
    <div class="hero-inner">
      <p class="hero-kicker">
        <span class="hj-numeral">{year ? formatYear(year) : 'All years'}</span>
        <i></i>
        <span>{year ? eraLabel(eraForYear(year)).replace('Archive · ', 'Archive ') : 'Across the archive'}</span>
      </p>

      <h1>{year ? `The world in ${year < 0 ? `${Math.abs(year)} BCE` : year}` : 'Explore the historical record'}</h1>

      <p class="hero-note">
        {year
          ? `A source-aware reading of the places, events and longer continuities that intersect ${formatYear(year)}. Start with the deliberately researched records, then follow the wider archive.`
          : 'Search places and historical records across the published archive, with source roles and uncertainty kept visible.'}
      </p>

      {#if year}
        <nav class="year-nav" aria-label="Move between years">
          <a href={`/browse?year=${normalizeYear(year - 1, year)}`}><span aria-hidden="true">←</span> {formatYear(normalizeYear(year - 1, year))}</a>
          {#if hasDossier}
            <a class="map-cta" href={`/year?year=${year}`}>Read {formatYear(year)} <span aria-hidden="true">→</span></a>
            <a class="secondary-cta" href={`/?year=${year}${lens !== 'all' ? `&lens=${lens}` : ''}`}>Open on the map <span aria-hidden="true">↗</span></a>
          {:else}
            <a class="map-cta" href={`/?year=${year}${lens !== 'all' ? `&lens=${lens}` : ''}`}>Open {formatYear(year)} on the map <span aria-hidden="true">↗</span></a>
          {/if}
          <a href={`/browse?year=${normalizeYear(year + 1, year)}`}>{formatYear(normalizeYear(year + 1, year))} <span aria-hidden="true">→</span></a>
        </nav>
      {/if}
    </div>
  </header>

  <section class="filters" aria-label="Filter historical records">
    <label>
      <span class="hj-label">Name or alternate name</span>
      <input type="search" bind:value={query} oninput={() => { entity = ''; visibleCount = 48; void refreshRecords(); }} placeholder="Search this historical world" />
    </label>
    <label>
      <span class="hj-label">Active in year</span>
      <input type="number" value={year ?? ''} min="-3400" max="2026" oninput={applyYear} placeholder="Any year — negative for BCE" />
    </label>
    <label>
      <span class="hj-label">Historical lens</span>
      <select bind:value={lens} onchange={() => (visibleCount = 48)}>
        {#each HISTORICAL_LENSES as option}<option value={option.id}>{option.label}</option>{/each}
      </select>
    </label>
    {#if query || year !== null || entity || lens !== 'all'}
      <button onclick={() => { query = ''; year = null; entity = ''; lens = 'all'; visibleCount = 48; void refreshRecords(); }}>Clear filters</button>
    {/if}
  </section>

  {#if loading}
    <p class="status" aria-live="polite">Opening the current release…</p>
  {:else if errorMessage}
    <p class="status error" role="alert">{errorMessage}</p>
  {:else}
    {#if showEditorialFrame}
      <section class="cross-section" aria-labelledby="cross-section-title">
        <div class="cross-copy">
          <p class="hj-section-label">How to read this year</p>
          <h2 id="cross-section-title">A year is a cross-section, not a list of events.</h2>
          <p class="hj-prose">
            {yearRecords.length.toLocaleString('en')} records intersect {formatYear(year!)}, but only
            {exactYearRecords.toLocaleString('en')} {exactYearRecords === 1 ? 'is' : 'are'} bounded to the year itself.
            The rest are places, institutions and reconstructions with longer date ranges. Presence here means
            “active or attested”, never “began this year”.
          </p>
        </div>

        <!-- The proportion is the argument, so it is measured rather than asserted:
             the sliver of year-bounded records is exactly the point being made. -->
        <figure class="proportion">
          <div class="bar" role="img" aria-label={`${exactYearRecords} of ${yearRecords.length} records are bounded to this year`}>
            <span class="bounded" style={`width: ${yearRecords.length ? Math.max((exactYearRecords / yearRecords.length) * 100, 0.6) : 0}%`}></span>
          </div>
          <figcaption>
            <span><b class="hj-numeral">{exactYearRecords.toLocaleString('en')}</b> bounded to {formatYear(year!)}</span>
            <span class="rest"><b class="hj-numeral">{(yearRecords.length - exactYearRecords).toLocaleString('en')}</b> spanning it</span>
          </figcaption>
        </figure>
      </section>

      {#if featuredRecords.length}
        <section class="featured" aria-labelledby="featured-title">
          <header>
            <div>
              <p class="hj-section-label">Begin with a record</p>
              <h2 id="featured-title">Evidence-backed paths into {formatYear(year!)}</h2>
            </div>
            <p class="hj-note">Deliberately curated for this pilot. Their map locations are reading anchors, not claims that history happened at a single point.</p>
          </header>
          <ul>
            {#each featuredRecords as record (record.entity_id)}
              <li>
                <a href={mapHref(record)}>
                  <p class="source-line">{sourceLabel(record)} · {record.kind.replaceAll('_', ' ')}</p>
                  <h3>{displayName(record)}</h3>
                  {#if alternateNames(record).length}<p class="alternate">{alternateNames(record).slice(0, 2).join(' · ')}</p>{/if}
                  <div class="marks">
                    {#each record.themes ?? [] as theme}
                      <span><LensMark lens={theme as HistoricalLens} size={11} />{lensDefinition(theme as HistoricalLens).shortLabel}</span>
                    {/each}
                  </div>
                  <span class="go">Open on the map <i aria-hidden="true">↗</i></span>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      <section class="lenses" aria-labelledby="lens-title">
        <header>
          <p class="hj-section-label">Change the question</p>
          <h2 id="lens-title">Read {formatYear(year!)} through a lens</h2>
        </header>
        <ul>
          {#each lensCounts as option}
            <li>
              <a class:active={lens === option.id} href={`/browse?year=${year}&lens=${option.id}`}>
                <span class="mark"><LensMark lens={option.id} size={22} /></span>
                <strong>{option.shortLabel}</strong>
                <p>{option.description}</p>
                <small class="hj-numeral">{option.count.toLocaleString('en')} sourced classification{option.count === 1 ? '' : 's'} <i aria-hidden="true">→</i></small>
              </a>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <section class="results" aria-labelledby="results-title">
      <header>
        <div>
          <p class="hj-section-label">{showEditorialFrame ? 'Continue into the archive' : 'Search results'}</p>
          <h2 id="results-title"><span class="hj-numeral">{archiveRecords.length.toLocaleString('en')}</span> {archiveRecords.length === 1 ? 'record' : 'records'}{staticSearchIndex && !query && year === null ? ' loaded' : ''}</h2>
        </div>
        <p class="hj-meta">{year ? `${selectedLens.label} · ${formatYear(year)}` : 'Across all published years'}</p>
      </header>

      {#if archiveRecords.length}
        <ul class="record-grid">
          {#each archiveRecords.slice(0, visibleCount) as record (record.entity_id)}
            <li>
              <a href={mapHref(record)}>
                <p class="source-line">{record.kind.replaceAll('_', ' ')} · {sourceLabel(record)}</p>
                <h3>{displayName(record)}</h3>
                {#if alternateNames(record).length}<p class="alternate">{alternateNames(record).slice(0, 3).join(' · ')}</p>{/if}
                <footer>
                  <time class="hj-numeral">{formatRange(record.valid_from, record.valid_to)}</time>
                  <span class="hj-numeral">{record.latitude.toFixed(1)}°, {record.longitude.toFixed(1)}°</span>
                  {#if record.themes?.length}
                    <em>{record.themes.map((theme) => lensDefinition(theme as HistoricalLens).shortLabel).join(' · ')}</em>
                  {/if}
                </footer>
              </a>
            </li>
          {/each}
        </ul>
        {#if visibleCount < archiveRecords.length || (staticSearchIndex && !query && year === null && loadedPageCount < staticSearchIndex.pages.pages.length)}
          <button class="show-more" onclick={() => void showMore()}>
            Show 48 more
            <span class="hj-numeral">{Math.min(visibleCount, archiveRecords.length).toLocaleString('en')} shown</span>
          </button>
        {/if}
      {:else}
        <p class="empty">No records match these filters. A gap in this index is not evidence that nothing existed.</p>
      {/if}
    </section>
  {/if}

  <footer class="release-footer hj-mono">
    {#if release}Release {release.manifest.build_id} · generated {new Date(release.manifest.generated_at).toLocaleDateString('en', { year: 'numeric', month: 'long', day: 'numeric' })}{/if}
  </footer>
</main>

<style>
  :global(body) { background: var(--bg); color: var(--text); }

  .masthead {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--s-6);
    border-bottom: 1px solid var(--line);
    background: var(--surface);
    color: var(--text);
  }
  .brand { display: flex; align-items: center; gap: var(--s-3); color: inherit; font-family: var(--font-display); font-size: var(--t-md); text-decoration: none; }
  .brand-mark {
    width: 17px;
    height: 17px;
    flex: none;
    border: 1px solid var(--accent);
    background: linear-gradient(to right, transparent calc(50% - 0.5px), var(--accent) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px));
  }
  .to-map { color: var(--accent); font-size: var(--t-sm); font-weight: 500; text-decoration: none; }
  .to-map:hover { color: var(--accent-hover); text-decoration: underline; text-underline-offset: 4px; }

  main { --gutter: max(var(--s-5), calc((100vw - 1180px) / 2)); }

  /* A single left-aligned column. The previous hero end-aligned three columns with
     72px of internal padding, which left a dead band across its middle. */
  .hero { padding: var(--s-8) var(--gutter) var(--s-7); border-bottom: 1px solid var(--line); background: var(--surface); color: var(--text); }
  /* The hero is a column, not a spread. Constraining it keeps the rule under the
     headline the same width as the headline instead of stranding the text at the left. */
  .hero-inner { max-width: 940px; }
  .hero-kicker { display: flex; align-items: center; gap: var(--s-3); margin: 0 0 var(--s-5); color: var(--accent); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase; }
  .hero-kicker i { width: 32px; height: 1px; background: var(--accent-line); }

  .hero h1 {
    max-width: 15ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(44px, 6.4vw, 86px);
    font-weight: 300;
    line-height: 0.96;
    letter-spacing: -0.04em;
    text-wrap: balance;
  }
  .hero-note { max-width: 56ch; margin: var(--s-5) 0 0; color: var(--text-dim); font-family: var(--font-display); font-size: var(--t-md); line-height: var(--lh-body); }

  .year-nav { display: flex; align-items: center; gap: var(--s-5); margin-top: var(--s-7); padding-top: var(--s-4); border-top: 1px solid var(--line); }
  .year-nav a { color: var(--text-dim); font-size: var(--t-sm); text-decoration: none; }
  .year-nav a:hover { color: var(--accent); }
  .year-nav a:last-child { margin-left: auto; }
  .year-nav .map-cta { margin-left: auto; padding: var(--s-3) var(--s-4); border: 1px solid var(--accent); background: var(--accent); color: #fff; font-weight: 600; }
  .year-nav .map-cta:hover { border-color: var(--accent-hover); background: var(--accent-hover); color: #fff; }
  .year-nav .secondary-cta { padding: var(--s-3) var(--s-4); border: 1px solid var(--line-strong); color: var(--text-dim); }
  .year-nav .secondary-cta:hover { border-color: var(--accent); color: var(--accent); }

  .filters {
    position: sticky;
    top: 0;
    z-index: 5;
    display: grid;
    grid-template-columns: minmax(240px, 1fr) 200px 220px auto;
    align-items: end;
    gap: var(--s-4);
    padding: var(--s-4) var(--gutter);
    border-bottom: 1px solid var(--line-strong);
    background: rgb(246 247 252 / 0.92);
    backdrop-filter: blur(12px);
  }
  .filters label { display: flex; flex-direction: column; gap: var(--s-2); color: var(--text-faint); }
  .filters input, .filters select {
    height: 42px;
    padding: 0 var(--s-3);
    border: 1px solid var(--line-strong);
    border-radius: 0;
    background: var(--surface);
    color: var(--text);
    font-size: var(--t-sm);
  }
  .filters input:focus-visible, .filters select:focus-visible { outline-color: var(--accent); }
  .filters button { height: 42px; padding: 0 var(--s-4); border: 1px solid var(--accent); background: transparent; color: var(--accent); cursor: pointer; font-size: var(--t-xs); font-weight: 600; }
  .filters button:hover { background: var(--accent); color: #fff; }

  main > section, main > .status, main > .release-footer { padding-inline: var(--gutter); }

  .status, .empty { padding-block: var(--s-8); color: var(--text-dim); font-family: var(--font-display); font-size: var(--t-lg); }
  .status.error { color: var(--conf-d); }

  h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(30px, 3.6vw, 46px);
    font-weight: 300;
    line-height: 1.02;
    letter-spacing: -0.028em;
    text-wrap: balance;
  }

  .cross-section { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr); gap: var(--s-8); padding-block: var(--s-9); border-bottom: 1px solid var(--line); }
  .cross-copy h2 { max-width: 24ch; margin-bottom: var(--s-5); }
  .cross-copy .hj-prose { max-width: 60ch; }

  .proportion { align-self: end; margin: 0; }
  .proportion .bar { height: 14px; border: 1px solid var(--line-strong); background: repeating-linear-gradient(90deg, var(--line-strong) 0 1px, transparent 1px 5px); }
  .proportion .bounded { display: block; height: 100%; min-width: 3px; background: var(--accent); }
  .proportion figcaption { display: flex; justify-content: space-between; gap: var(--s-4); margin-top: var(--s-3); color: var(--text-dim); font-size: var(--t-sm); }
  .proportion b { font-family: var(--font-display); font-size: var(--t-lg); font-weight: 400; }
  .proportion .rest { color: var(--text-faint); text-align: right; }

  .featured, .lenses { padding-block: var(--s-9); border-bottom: 1px solid var(--line); }
  .featured > header { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 360px); gap: var(--s-7); align-items: end; margin-bottom: var(--s-6); }
  .lenses > header { margin-bottom: var(--s-6); }

  .featured ul, .lenses ul, .record-grid { margin: 0; padding: 0; list-style: none; }

  .featured ul { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); }
  .featured li { min-width: 0; background: var(--surface); }
  .featured a { min-height: 232px; display: flex; flex-direction: column; padding: var(--s-5); color: inherit; text-decoration: none; transition: background 0.2s var(--ease); }
  .featured a:hover { background: var(--accent-soft); }
  .featured h3 { margin: 0; font-family: var(--font-display); font-size: var(--t-xl); font-weight: 400; line-height: 1.08; letter-spacing: -0.02em; }

  .source-line { margin: 0 0 var(--s-3); color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
  .alternate { margin: var(--s-2) 0 0; color: var(--text-faint); font-size: var(--t-xs); }

  .marks { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-4); }
  .marks span { display: inline-flex; align-items: center; gap: 5px; padding: 4px var(--s-2); border: 1px solid var(--line-strong); color: var(--text-dim); font-size: var(--t-xs); }
  .marks span :global(svg) { color: var(--text-dim); }

  .go { margin-top: auto; padding-top: var(--s-5); color: var(--accent); font-size: var(--t-xs); font-weight: 600; }
  .featured a:hover .go i { display: inline-block; transform: translate(2px, -2px); }
  .go i { font-style: normal; transition: transform 0.16s var(--ease); }

  .lenses ul { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); }
  .lenses li { min-width: 0; background: var(--surface); }
  .lenses a { min-height: 200px; display: flex; flex-direction: column; padding: var(--s-4); color: inherit; text-decoration: none; }
  .lenses a:hover, .lenses a.active { background: var(--accent-soft); }
  .lenses a.active { box-shadow: inset 0 3px 0 var(--accent); }
  .lenses .mark { color: var(--accent); font-size: var(--t-lg); line-height: 1; }
  .lenses strong { margin-top: var(--s-5); font-family: var(--font-display); font-size: var(--t-lg); font-weight: 400; }
  .lenses p { margin: var(--s-2) 0 0; color: var(--text-faint); font-size: var(--t-xs); line-height: 1.5; }
  .lenses small { margin-top: auto; padding-top: var(--s-4); color: var(--text-dim); font-size: var(--t-xs); font-weight: 500; }
  .lenses small i { font-style: normal; }

  .results { padding-block: var(--s-9) var(--s-7); }
  .results > header { display: flex; justify-content: space-between; align-items: baseline; gap: var(--s-5); margin-bottom: var(--s-5); }

  .record-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); }
  .record-grid li { min-width: 0; background: var(--surface); }
  .record-grid a { min-height: 180px; display: flex; flex-direction: column; padding: var(--s-4); color: inherit; text-decoration: none; transition: background 0.2s var(--ease); }
  .record-grid a:hover { background: var(--accent-soft); }
  .record-grid h3 { margin: 0; font-family: var(--font-display); font-size: var(--t-lg); font-weight: 400; line-height: 1.1; letter-spacing: -0.014em; }
  .record-grid footer { display: grid; gap: var(--s-1); margin-top: auto; padding-top: var(--s-4); color: var(--text-faint); font-size: var(--t-xs); }
  .record-grid footer em { color: var(--text-dim); font-style: normal; }

  .show-more {
    width: 100%;
    display: flex;
    justify-content: space-between;
    margin-top: var(--s-4);
    padding: var(--s-4);
    border: 1px solid var(--line-strong);
    background: transparent;
    color: var(--text);
    cursor: pointer;
    font-size: var(--t-sm);
    font-weight: 500;
  }
  .show-more span { color: var(--text-faint); }
  .show-more:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }

  .release-footer { padding-block: var(--s-4) var(--s-7); border-top: 1px solid var(--line); color: var(--text-faint); }

  @media (max-width: 1080px) {
    .cross-section { grid-template-columns: 1fr; gap: var(--s-6); }
    .featured ul { grid-template-columns: repeat(2, 1fr); }
    .lenses ul { grid-template-columns: repeat(3, 1fr); }
    .record-grid { grid-template-columns: repeat(2, 1fr); }
    .filters { grid-template-columns: 1fr 1fr; }
  }

  @media (max-width: 720px) {
    .masthead { padding-inline: var(--s-4); }
    .hero { padding-block: var(--s-6) var(--s-6); }
    .year-nav { flex-wrap: wrap; gap: var(--s-3); margin-top: var(--s-6); }
    .year-nav .map-cta { order: -1; width: 100%; margin-left: 0; text-align: center; }
    .year-nav a:last-child { margin-left: auto; }
    .featured > header { grid-template-columns: 1fr; gap: var(--s-4); }
    .featured ul, .lenses ul, .record-grid { grid-template-columns: 1fr; }
    .featured a { min-height: 0; }
    .cross-section, .featured, .lenses, .results { padding-block: var(--s-7); }
    .results > header { flex-direction: column; align-items: flex-start; gap: var(--s-2); }
  }
</style>
