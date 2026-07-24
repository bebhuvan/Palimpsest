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
  import { formatRange, formatYear, normalizeYear } from '$lib/history';
  import { HISTORICAL_LENSES, isHistoricalLens, lensDefinition, recordMatchesLens, type HistoricalLens } from '$lib/lenses';

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

  $: normalizedQuery = query.trim().toLocaleLowerCase();
  $: filtered = records.filter((record) => {
    const matchesQuery = !normalizedQuery || searchableNames(record).some((name) => name.toLocaleLowerCase().includes(normalizedQuery));
    const matchesEntity = !entity || record.entity_id === entity;
    const matchesLens = recordMatchesLens(record, lens);
    const matchesYear = year === null || recordActiveInYear(record, year);
    return matchesQuery && matchesEntity && matchesLens && matchesYear;
  }).sort(compareRecords);
  $: yearRecords = year === null ? records : records.filter((record) => recordActiveInYear(record, year!));
  $: featuredRecords = filtered.filter((record) => record.entity_id.startsWith('historyjoice:')).slice(0, 6);
  $: featuredIds = new Set(featuredRecords.map((record) => record.entity_id));
  $: showEditorialFrame = year !== null && !normalizedQuery && !entity;
  $: archiveRecords = showEditorialFrame ? filtered.filter((record) => !featuredIds.has(record.entity_id)) : filtered;
  $: exactYearRecords = year === null ? 0 : yearRecords.filter((record) => record.valid_from === year && record.valid_to === year).length;
  $: lensCounts = HISTORICAL_LENSES
    .filter((option) => option.id !== 'all')
    .map((option) => ({ ...option, count: yearRecords.filter((record) => recordMatchesLens(record, option.id)).length }));
  $: selectedLens = lensDefinition(lens);

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
    const leftCurated = left.entity_id.startsWith('historyjoice:') ? 0 : 1;
    const rightCurated = right.entity_id.startsWith('historyjoice:') ? 0 : 1;
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
  <title>{year ? `The world in ${formatYear(year)}` : 'Browse history'} — History Joice</title>
  <meta name="description" content={year ? `Explore source-backed places and stories active in ${formatYear(year)}.` : 'An accessible text view of the historical records published in the current History Joice release.'} />
</svelte:head>

<header class="browse-header">
  <a class="brand" href="/"><span>History Joice</span><small>World history map</small></a>
  <a class="map-link" href={`/?${new URLSearchParams({ ...(year ? { year: String(year) } : {}), ...(lens !== 'all' ? { lens } : {}) })}`}>Return to the map <span aria-hidden="true">↗</span></a>
</header>

<main>
  <header class="year-hero">
    <div class="hero-kicker"><span>Year view</span><i></i><span>{year ? 'Early modern archive' : 'Across the archive'}</span></div>
    <div class="hero-copy">
      <p class="year-mark">{year ? formatYear(year) : 'All years'}</p>
      <h1>{year ? `The world in ${year < 0 ? `${Math.abs(year).toLocaleString('en')} BCE` : year.toLocaleString('en')}` : 'Explore the historical record'}</h1>
      <p>
        {year
          ? `A source-aware reading of places, events and longer historical continuities that intersect ${formatYear(year)}. Start with the deliberately researched stories, then explore the wider archive.`
          : 'Search places and historical records across the published archive, with source roles and uncertainty kept visible.'}
      </p>
    </div>
    {#if year}
      <nav class="year-nav" aria-label="Move between years">
        <a href={`/browse?year=${normalizeYear(year - 1, year)}`} aria-label={`Open ${formatYear(normalizeYear(year - 1, year))}`}>← {formatYear(normalizeYear(year - 1, year))}</a>
        <a class="map-cta" href={`/?year=${year}${lens !== 'all' ? `&lens=${lens}` : ''}`}>Explore {formatYear(year)} on the map <span>↗</span></a>
        <a href={`/browse?year=${normalizeYear(year + 1, year)}`} aria-label={`Open ${formatYear(normalizeYear(year + 1, year))}`}>{formatYear(normalizeYear(year + 1, year))} →</a>
      </nav>
    {/if}
  </header>

  <section class="filters" aria-label="Filter historical records">
    <label><span>Name or alternate name</span><input type="search" bind:value={query} oninput={() => { entity = ''; visibleCount = 48; void refreshRecords(); }} placeholder="Search this historical world" /></label>
    <label><span>Active in year <small>(negative for BCE)</small></span><input type="number" value={year ?? ''} min="-3400" max="2026" oninput={applyYear} placeholder="Any year" /></label>
    <label><span>Historical lens</span><select bind:value={lens} onchange={() => (visibleCount = 48)}>{#each HISTORICAL_LENSES as option}<option value={option.id}>{option.label}</option>{/each}</select></label>
    {#if query || year !== null || entity || lens !== 'all'}<button onclick={() => { query = ''; year = null; entity = ''; lens = 'all'; visibleCount = 48; void refreshRecords(); }}>Clear filters</button>{/if}
  </section>

  {#if loading}
    <p class="status" aria-live="polite">Opening the current release…</p>
  {:else if errorMessage}
    <p class="status error" role="alert">{errorMessage}</p>
  {:else}
    {#if showEditorialFrame}
      <section class="year-reading" aria-labelledby="year-reading-title">
        <div class="reading-intro">
          <p class="eyebrow">How to read this year</p>
          <h2 id="year-reading-title">A year is a cross-section,<br />not a list of events.</h2>
          <p>{yearRecords.length.toLocaleString()} records intersect this date, but only {exactYearRecords.toLocaleString()} are bounded to {formatYear(year!)} itself. The rest are places, institutions or reconstructions with longer date ranges. Presence here means “active or attested,” not “began this year.”</p>
        </div>
        <dl class="year-stats">
          <div><dt>{yearRecords.length.toLocaleString()}</dt><dd>records intersect this year</dd></div>
          <div><dt>{exactYearRecords.toLocaleString()}</dt><dd>records bounded to this year</dd></div>
          <div><dt>{featuredRecords.length.toLocaleString()}</dt><dd>deliberately researched starting points</dd></div>
        </dl>
      </section>

      {#if featuredRecords.length}
        <section class="featured" aria-labelledby="featured-title">
          <header>
            <div><p class="eyebrow">Begin with a story</p><h2 id="featured-title">Evidence-backed paths into {formatYear(year!)}</h2></div>
            <p>These records were deliberately curated for this pilot. Their map locations are reading anchors, not claims that history happened at a single point.</p>
          </header>
          <ol>
            {#each featuredRecords as record, index (record.entity_id)}
              <li>
                <a href={mapHref(record)}>
                  <div class="feature-number">0{index + 1}</div>
                  <div class="feature-body">
                    <p class="source-line">{sourceLabel(record)} · {record.kind.replaceAll('_', ' ')}</p>
                    <h3>{displayName(record)}</h3>
                    {#if alternateNames(record).length}<p class="alternate">{alternateNames(record).slice(0, 2).join(' · ')}</p>{/if}
                    <div class="theme-row">{#each record.themes ?? [] as theme}<span>{lensDefinition(theme as HistoricalLens).marker} {lensDefinition(theme as HistoricalLens).shortLabel}</span>{/each}</div>
                  </div>
                  <span class="feature-action">Open story on map ↗</span>
                </a>
              </li>
            {/each}
          </ol>
        </section>
      {/if}

      <section class="lens-overview" aria-labelledby="lens-title">
        <header><p class="eyebrow">Change the question</p><h2 id="lens-title">Read {formatYear(year!)} through a lens</h2></header>
        <div class="lens-grid">
          {#each lensCounts as option}
            <a class:active={lens === option.id} href={`/browse?year=${year}&lens=${option.id}`} style={`--accent:${option.accent}`}>
              <span>{option.marker}</span>
              <strong>{option.shortLabel}</strong>
              <p>{option.description}</p>
              <small>{option.count.toLocaleString()} sourced classification{option.count === 1 ? '' : 's'} →</small>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <section class="results" aria-labelledby="results-title">
      <div class="results-heading">
        <div><p class="eyebrow">{showEditorialFrame ? 'Continue into the archive' : 'Search results'}</p><h2 id="results-title">{archiveRecords.length.toLocaleString()} {archiveRecords.length === 1 ? 'record' : 'records'}{staticSearchIndex && !query && year === null ? ' loaded' : ''}</h2></div>
        <p>{year ? `${selectedLens.label} · ${formatYear(year)}` : 'Across all published years'}</p>
      </div>
      {#if archiveRecords.length}
        <ol>
          {#each archiveRecords.slice(0, visibleCount) as record (record.entity_id)}
            <li>
              <a href={mapHref(record)}>
                <span class="record-kind">{record.kind.replaceAll('_', ' ')} · {sourceLabel(record)}</span>
                <h3>{displayName(record)}</h3>
                {#if alternateNames(record).length}<p>{alternateNames(record).slice(0, 3).join(' · ')}</p>{/if}
                <footer>
                  <time>{formatRange(record.valid_from, record.valid_to)}</time>
                  <span>{record.latitude.toFixed(2)}°, {record.longitude.toFixed(2)}°</span>
                  {#if record.themes?.length}<em>{record.themes.map((theme) => lensDefinition(theme as HistoricalLens).shortLabel).join(' · ')}</em>{/if}
                  <b>Read on map →</b>
                </footer>
              </a>
            </li>
          {/each}
        </ol>
        {#if visibleCount < archiveRecords.length || (staticSearchIndex && !query && year === null && loadedPageCount < staticSearchIndex.pages.pages.length)}<button class="show-more" onclick={() => void showMore()}>Show 48 more <span>{Math.min(visibleCount, archiveRecords.length).toLocaleString()} shown</span></button>{/if}
      {:else}<p class="empty">No records match these filters. A gap in this index is not evidence that nothing existed.</p>{/if}
    </section>
  {/if}

  <footer class="release-footer">{#if release}Release {release.manifest.build_id} · generated {new Date(release.manifest.generated_at).toLocaleDateString('en', { year: 'numeric', month: 'long', day: 'numeric' })}{/if}</footer>
</main>

<style>
  :global(*) { box-sizing: border-box; }
  :global(:root) { font-family: 'Manrope', 'Inter', system-ui, sans-serif; color: #172320; background: #f3f0e8; }
  :global(body) { margin: 0; }
  :global(button), :global(input), :global(select) { font: inherit; }
  :global(a:focus-visible), :global(button:focus-visible), :global(input:focus-visible), :global(select:focus-visible) { outline: 2px solid #c9874d; outline-offset: 3px; }
  .browse-header { height: 68px; display: flex; align-items: center; justify-content: space-between; padding: 0 32px; border-bottom: 1px solid rgba(220, 225, 216, .28); background: #162b28; color: #f4f0e6; }
  .brand { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; color: inherit; text-decoration: none; }
  .brand span { font-size: 14px; font-weight: 650; letter-spacing: -.01em; }
  .brand small { color: #aab9b3; font-size: 8px; font-weight: 500; }
  .map-link { color: #e6ddd0; font-size: 10px; font-weight: 600; letter-spacing: .01em; text-underline-offset: 4px; }
  main { width: min(1180px, calc(100% - 48px)); margin: 0 auto; }
  .year-hero { margin: 0 calc((100vw - min(1180px, calc(100vw - 48px))) / -2); padding: 42px max(24px, calc((100vw - 1180px) / 2)) 50px; background: #162b28; color: #f4f0e6; }
  .hero-kicker { display: flex; align-items: center; gap: 12px; color: #b7c5bf; font: 9px 'DM Mono', monospace; letter-spacing: .11em; text-transform: uppercase; }
  .hero-kicker i { width: 34px; height: 1px; background: #7e938b; }
  .hero-copy { display: grid; grid-template-columns: 180px minmax(400px, 1fr) minmax(250px, 390px); gap: 28px; align-items: end; padding: 72px 0 54px; }
  .year-mark { margin: 0; color: #d59a64; font: 15px 'DM Mono', monospace; }
  .hero-copy h1 { margin: 0; max-width: 650px; font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(52px, 6.5vw, 92px); font-weight: 400; line-height: .88; letter-spacing: -.045em; }
  .hero-copy > p:last-child { margin: 0; max-width: 380px; color: #c4cec9; font-size: 13px; line-height: 1.75; }
  .year-nav { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 25px; border-top: 1px solid rgba(220, 225, 216, .25); padding-top: 20px; }
  .year-nav a { color: #bdc9c4; font: 9px 'DM Mono', monospace; letter-spacing: .04em; text-decoration: none; text-transform: uppercase; }
  .year-nav a:last-child { justify-self: end; }
  .year-nav .map-cta { justify-self: center; padding: 13px 20px; border: 1px solid #d59a64; color: #f4f0e6; }
  .year-nav .map-cta:hover { background: #d59a64; color: #162b28; }
  .filters { position: sticky; top: 0; z-index: 5; display: grid; grid-template-columns: minmax(240px, 1fr) 190px 210px auto; align-items: end; gap: 18px; margin: 0 calc((100vw - min(1180px, calc(100vw - 48px))) / -2); padding: 18px max(24px, calc((100vw - 1180px) / 2)); border-bottom: 1px solid #aeb5ae; background: rgba(243, 240, 232, .96); backdrop-filter: blur(14px); }
  .filters label { display: flex; flex-direction: column; gap: 7px; color: #5d6764; font: 8px 'DM Mono', monospace; letter-spacing: .07em; text-transform: uppercase; }
  .filters label small { font-size: 7px; text-transform: none; }
  .filters input, .filters select { height: 43px; padding: 0 12px; border: 1px solid #9fa6a1; border-radius: 0; background: #fbf9f3; color: #1c2725; font-size: 12px; }
  .filters button { height: 43px; padding: 0 14px; border: 1px solid #46524f; background: transparent; color: #34413e; cursor: pointer; font-size: 9px; text-transform: uppercase; }
  .status, .empty { padding: 50px 0; color: #5d6764; font-family: 'Instrument Serif', Georgia, serif; font-size: 24px; }
  .status.error { color: #7f382e; }
  .eyebrow { margin: 0 0 14px; color: #89536a; font: 8px 'DM Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
  .year-reading { display: grid; grid-template-columns: 1.3fr 1fr; gap: 70px; padding: 80px 0; border-bottom: 1px solid #acb4ad; }
  .reading-intro h2 { margin: 0 0 25px; font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(38px, 5vw, 63px); font-weight: 400; line-height: .98; letter-spacing: -.025em; }
  .reading-intro > p:last-child { max-width: 650px; margin: 0; color: #58635f; font-size: 13px; line-height: 1.75; }
  .year-stats { display: grid; grid-template-columns: repeat(3, 1fr); align-self: end; margin: 0; border-top: 1px solid #9ba59e; border-left: 1px solid #9ba59e; }
  .year-stats div { min-height: 145px; padding: 20px 16px; border-right: 1px solid #9ba59e; border-bottom: 1px solid #9ba59e; }
  .year-stats dt { color: #1d4741; font-family: 'Instrument Serif', Georgia, serif; font-size: 42px; line-height: 1; }
  .year-stats dd { margin: 40px 0 0; color: #606b67; font: 8px/1.5 'DM Mono', monospace; text-transform: uppercase; }
  .featured { padding: 78px 0; border-bottom: 1px solid #acb4ad; }
  .featured > header { display: grid; grid-template-columns: 1fr 360px; gap: 50px; align-items: end; margin-bottom: 34px; }
  .featured h2, .lens-overview h2 { margin: 0; font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(38px, 4.5vw, 58px); font-weight: 400; line-height: 1; letter-spacing: -.02em; }
  .featured > header > p { margin: 0; color: #5d6864; font-size: 12px; line-height: 1.7; }
  .featured ol { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin: 0; padding: 1px; background: #929c95; list-style: none; }
  .featured li { min-width: 0; background: #f8f5ed; }
  .featured a { min-height: 330px; display: flex; flex-direction: column; padding: 23px; color: inherit; text-decoration: none; transition: background .2s ease, transform .2s ease; }
  .featured a:hover { background: #ede5d9; transform: translateY(-3px); }
  .feature-number { color: #96724e; font: 9px 'DM Mono', monospace; }
  .feature-body { margin-top: 68px; }
  .source-line { margin: 0 0 12px; color: #7c4c60; font: 8px 'DM Mono', monospace; letter-spacing: .04em; text-transform: uppercase; }
  .featured h3 { margin: 0; font-family: 'Instrument Serif', Georgia, serif; font-size: 31px; font-weight: 400; line-height: 1.05; }
  .featured .alternate { margin: 9px 0 0; color: #65706b; font-size: 9px; }
  .theme-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 20px; }
  .theme-row span { padding: 6px 8px; border: 1px solid #a8afa8; color: #52605b; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  .feature-action { margin-top: auto; color: #24564f; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .lens-overview { padding: 78px 0; border-bottom: 1px solid #acb4ad; }
  .lens-overview > header { margin-bottom: 32px; }
  .lens-grid { display: grid; grid-template-columns: repeat(5, 1fr); border-top: 1px solid #9aa39d; border-left: 1px solid #9aa39d; }
  .lens-grid a { min-height: 230px; display: flex; flex-direction: column; padding: 20px 18px; border-right: 1px solid #9aa39d; border-bottom: 1px solid #9aa39d; color: inherit; text-decoration: none; }
  .lens-grid a:hover, .lens-grid a.active { box-shadow: inset 0 4px var(--accent); background: #faf7ef; }
  .lens-grid a > span { color: var(--accent); font-size: 20px; }
  .lens-grid strong { margin-top: 32px; font-family: 'Instrument Serif', Georgia, serif; font-size: 24px; font-weight: 400; }
  .lens-grid p { margin: 10px 0 0; color: #68716e; font-size: 9px; line-height: 1.5; }
  .lens-grid small { margin-top: auto; color: #405852; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  .results { padding: 76px 0 60px; }
  .results-heading { display: flex; justify-content: space-between; align-items: end; padding-bottom: 18px; }
  .results-heading h2 { margin: 0; font-family: 'Instrument Serif', Georgia, serif; font-size: 38px; font-weight: 400; line-height: 1; }
  .results-heading > p { margin: 0; color: #67716e; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  .results ol { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; padding: 0; border-top: 1px solid #929b96; border-left: 1px solid #929b96; list-style: none; }
  .results li { min-width: 0; border-right: 1px solid #929b96; border-bottom: 1px solid #929b96; }
  .results li a { min-height: 190px; display: flex; flex-direction: column; padding: 18px 20px; color: inherit; text-decoration: none; }
  .results li a:hover { background: #e8e7df; }
  .record-kind { color: #754259; font: 7px 'DM Mono', monospace; letter-spacing: .04em; }
  .results h3 { margin: 12px 0 5px; font-family: 'Instrument Serif', Georgia, serif; font-size: 25px; line-height: 1.05; font-weight: 400; letter-spacing: -.01em; }
  .results li p { margin: 0; color: #66706d; font-size: 9px; }
  .results li footer { display: grid; grid-template-columns: 1fr auto; gap: 5px 15px; margin-top: auto; padding-top: 18px; color: #626c69; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  .results li footer em { grid-column: 1 / -1; color: #7d5666; font-style: normal; }
  .results li footer b { grid-column: 1 / -1; color: #294b47; font-weight: 600; }
  .show-more { width: 100%; display: flex; justify-content: space-between; margin-top: 15px; padding: 13px 16px; border: 1px solid #8e9692; background: transparent; color: #35423f; cursor: pointer; font: 9px 'DM Mono', monospace; text-transform: uppercase; }
  .show-more:hover { background: #e6e7e1; }
  .release-footer { padding: 20px 0 35px; border-top: 1px solid #bfc3bf; color: #707976; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  @media (max-width: 980px) {
    .hero-copy { grid-template-columns: 130px 1fr; }
    .hero-copy > p:last-child { grid-column: 2; }
    .year-reading { grid-template-columns: 1fr; gap: 40px; }
    .featured ol { grid-template-columns: repeat(2, 1fr); }
    .lens-grid { grid-template-columns: repeat(2, 1fr); }
    .results ol { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 720px) {
    .browse-header { padding: 0 16px; }
    main { width: min(100% - 28px, 1180px); }
    .year-hero { margin-inline: -14px; padding: 32px 14px 38px; }
    .hero-copy { grid-template-columns: 1fr; gap: 25px; padding: 48px 0 40px; }
    .hero-copy > p:last-child { grid-column: auto; }
    .year-nav { grid-template-columns: 1fr 1fr; }
    .year-nav .map-cta { grid-column: 1 / -1; grid-row: 1; width: 100%; text-align: center; }
    .filters { grid-template-columns: 1fr 1fr; gap: 12px; }
    .filters button { grid-column: 1 / -1; }
    .year-stats { grid-template-columns: 1fr; }
    .year-stats div { min-height: 105px; }
    .year-stats dd { margin-top: 20px; }
    .featured > header { grid-template-columns: 1fr; gap: 20px; }
    .featured ol, .results ol { grid-template-columns: 1fr; }
    .featured a { min-height: 270px; }
    .feature-body { margin-top: 45px; }
  }
  @media (max-width: 440px) {
    .map-link { font-size: 0; }
    .map-link span { font-size: 16px; }
    .filters { grid-template-columns: 1fr; }
    .filters button { grid-column: auto; }
    .lens-grid { grid-template-columns: 1fr; }
  }
</style>
