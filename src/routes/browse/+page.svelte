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
  import { HISTORICAL_LENSES, isHistoricalLens, recordMatchesLens, type HistoricalLens } from '$lib/lenses';

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
  let visibleCount = 100;
  let loadedPageCount = 0;
  let filterRequest = 0;

  $: normalizedQuery = query.trim().toLocaleLowerCase();
  $: filtered = records.filter((record) => {
    const matchesQuery = !normalizedQuery || searchableNames(record).some((name) => name.toLocaleLowerCase().includes(normalizedQuery));
    const matchesEntity = !entity || record.entity_id === entity;
    const matchesLens = recordMatchesLens(record, lens);
    const matchesYear = year === null || (record.name_attestations?.length
      ? record.name_attestations.some((name) => name.valid_from <= year! && name.valid_to >= year!)
      : record.valid_from <= year && record.valid_to >= year);
    return matchesQuery && matchesEntity && matchesLens && matchesYear;
  });

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
    visibleCount = 100;
    void refreshRecords();
  }

  async function showMore(): Promise<void> {
    visibleCount += 100;
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
  <title>Browse records — History Joice</title>
  <meta name="description" content="An accessible text view of the historical records published in the current History Joice release." />
</svelte:head>

<header class="browse-header">
  <a class="brand" href="/"><span>History Joice</span><small>World history map</small></a>
  <a class="map-link" href={`/?${new URLSearchParams({ ...(year ? { year: String(year) } : {}), ...(lens !== 'all' ? { lens } : {}) })}`}>Return to the map <span aria-hidden="true">↗</span></a>
</header>

<main>
  <header class="page-intro">
    <p>Text view</p>
    <h1>Records in this release</h1>
    <span>Every result links back to its representative map point and active date. This view remains usable without the interactive map.</span>
  </header>

  <section class="filters" aria-label="Filter historical records">
    <label><span>Name or alternate name</span><input type="search" bind:value={query} oninput={() => { entity = ''; visibleCount = 100; void refreshRecords(); }} placeholder="Search records" /></label>
    <label><span>Active in year <small>(negative for BCE)</small></span><input type="number" value={year ?? ''} min="-3400" max="2026" oninput={applyYear} placeholder="Any year" /></label>
    <label><span>Historical lens</span><select bind:value={lens} onchange={() => (visibleCount = 100)}>{#each HISTORICAL_LENSES as option}<option value={option.id}>{option.label}</option>{/each}</select></label>
    {#if query || year !== null || entity || lens !== 'all'}<button onclick={() => { query = ''; year = null; entity = ''; lens = 'all'; visibleCount = 100; void refreshRecords(); }}>Clear filters</button>{/if}
  </section>

  {#if loading}
    <p class="status" aria-live="polite">Opening the current release…</p>
  {:else if errorMessage}
    <p class="status error" role="alert">{errorMessage}</p>
  {:else}
    <section class="results" aria-labelledby="results-title">
      <div class="results-heading"><h2 id="results-title">{filtered.length.toLocaleString()} {filtered.length === 1 ? 'record' : 'records'}{staticSearchIndex && !query && year === null ? ' loaded' : ''}</h2><p>{year ? `Active in ${formatYear(year)}` : 'Across all published years'}</p></div>
      {#if filtered.length}
        <ol>
          {#each filtered.slice(0, visibleCount) as record (record.entity_id)}
            <li>
              <a href={`/?year=${year && year >= record.valid_from && year <= record.valid_to ? year : record.valid_from}&entity=${encodeURIComponent(record.entity_id)}${lens !== 'all' ? `&lens=${lens}` : ''}`}>
                <span class="record-kind">{record.kind.replaceAll('_', ' ')}</span>
                <h3>{displayName(record)}</h3>
                {#if alternateNames(record).length}<p>{alternateNames(record).slice(0, 3).join(' · ')}</p>{/if}
                <footer><time>{formatRange(record.valid_from, record.valid_to)}</time><span>{record.latitude.toFixed(2)}°, {record.longitude.toFixed(2)}°</span><b>Show on map →</b></footer>
              </a>
            </li>
          {/each}
        </ol>
        {#if visibleCount < filtered.length || (staticSearchIndex && !query && year === null && loadedPageCount < staticSearchIndex.pages.pages.length)}<button class="show-more" onclick={() => void showMore()}>Show 100 more <span>{Math.min(visibleCount, filtered.length).toLocaleString()} shown</span></button>{/if}
      {:else}<p class="empty">No records match these filters. A gap in this index is not evidence that nothing existed.</p>{/if}
    </section>
  {/if}

  <footer class="release-footer">{#if release}Release {release.manifest.build_id} · generated {new Date(release.manifest.generated_at).toLocaleDateString('en', { year: 'numeric', month: 'long', day: 'numeric' })}{/if}</footer>
</main>

<style>
  :global(*) { box-sizing: border-box; }
  :global(:root) { font-family: 'Manrope', 'Inter', system-ui, sans-serif; color: #1b2523; background: #f4f3ee; }
  :global(body) { margin: 0; }
  :global(button), :global(input) { font: inherit; }
  :global(a:focus-visible), :global(button:focus-visible), :global(input:focus-visible) { outline: 2px solid #17413e; outline-offset: 3px; }
  .browse-header { height: 65px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; border-bottom: 1px solid #aeb4af; }
  .brand { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; color: inherit; text-decoration: none; }
  .brand span { font-size: 13px; font-weight: 650; letter-spacing: -.01em; }
  .brand small { color: #69726f; font-size: 8px; font-weight: 500; }
  .map-link { color: #294b47; font-size: 10px; font-weight: 600; letter-spacing: .01em; text-underline-offset: 3px; }
  main { width: min(1040px, calc(100% - 40px)); margin: 0 auto; }
  .page-intro { display: grid; grid-template-columns: 150px minmax(250px, 500px) 1fr; align-items: end; gap: 28px; padding: 66px 0 42px; border-bottom: 1px solid #aeb4af; }
  .page-intro > p { margin: 0; color: #754259; font: 8px 'DM Mono', monospace; letter-spacing: .05em; }
  .page-intro h1 { margin: 0; font-size: 40px; line-height: 1; font-weight: 520; letter-spacing: -.03em; }
  .page-intro > span { color: #56615e; font-size: 11px; line-height: 1.65; }
  .filters { display: grid; grid-template-columns: minmax(240px, 1fr) 190px 190px auto; align-items: end; gap: 18px; padding: 22px 0; border-bottom: 1px solid #bfc3bf; }
  .filters label { display: flex; flex-direction: column; gap: 7px; color: #5d6764; font: 8px 'DM Mono', monospace; letter-spacing: .06em; text-transform: uppercase; }
  .filters label small { font-size: 7px; text-transform: none; }
  .filters input, .filters select { height: 40px; padding: 0 10px; border: 1px solid #9fa6a1; border-radius: 0; background: #faf9f5; color: #1c2725; font-size: 12px; }
  .filters button { height: 40px; padding: 0 14px; border: 1px solid #46524f; background: transparent; color: #34413e; cursor: pointer; font-size: 9px; text-transform: uppercase; }
  .status, .empty { padding: 50px 0; color: #5d6764; font-family: 'Instrument Serif', Georgia, serif; font-size: 24px; }
  .status.error { color: #7f382e; }
  .results { padding: 25px 0 60px; }
  .results-heading { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 12px; }
  .results-heading h2 { margin: 0; font: 11px 'DM Mono', monospace; letter-spacing: .08em; text-transform: uppercase; }
  .results-heading p { margin: 0; color: #67716e; font: 8px 'DM Mono', monospace; text-transform: uppercase; }
  ol { display: grid; grid-template-columns: repeat(2, 1fr); margin: 0; padding: 0; border-top: 1px solid #929b96; border-left: 1px solid #929b96; list-style: none; }
  li { min-width: 0; border-right: 1px solid #929b96; border-bottom: 1px solid #929b96; }
  li a { min-height: 176px; display: flex; flex-direction: column; padding: 18px 20px; color: inherit; text-decoration: none; }
  li a:hover { background: #e8e9e3; }
  .record-kind { color: #754259; font: 7px 'DM Mono', monospace; letter-spacing: .04em; }
  h3 { margin: 12px 0 5px; font-size: 21px; line-height: 1.1; font-weight: 550; letter-spacing: -.015em; }
  li p { margin: 0; color: #66706d; font-size: 9px; }
  li footer { display: grid; grid-template-columns: 1fr auto; gap: 5px 15px; margin-top: auto; padding-top: 18px; color: #626c69; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  li footer b { grid-column: 1 / -1; color: #294b47; font-weight: 600; }
  .show-more { width: 100%; display: flex; justify-content: space-between; margin-top: 15px; padding: 13px 16px; border: 1px solid #8e9692; background: transparent; color: #35423f; cursor: pointer; font: 9px 'DM Mono', monospace; text-transform: uppercase; }
  .show-more:hover { background: #e6e7e1; }
  .release-footer { padding: 20px 0 35px; border-top: 1px solid #bfc3bf; color: #707976; font: 7px 'DM Mono', monospace; text-transform: uppercase; }
  @media (max-width: 720px) {
    .browse-header { padding: 0 16px; }
    main { width: min(100% - 28px, 1040px); }
    .page-intro { grid-template-columns: 1fr; gap: 14px; padding: 40px 0 28px; }
    .page-intro h1 { font-size: 34px; }
    .page-intro > span { max-width: 460px; }
    .filters { grid-template-columns: 1fr 1fr; gap: 12px; }
    .filters button { grid-column: 1 / -1; }
    ol { grid-template-columns: 1fr; }
  }
  @media (max-width: 440px) {
    .map-link { font-size: 0; }
    .map-link span { font-size: 16px; }
    .filters { grid-template-columns: 1fr; }
    .filters button { grid-column: auto; }
  }
</style>
