<script lang="ts">
  import { onMount, tick } from 'svelte';
  import YearFigure from '$lib/components/YearFigure.svelte';
  import YearProse from '$lib/components/YearProse.svelte';
  import YearRegister from '$lib/components/YearRegister.svelte';
  import { loadRelease, type LoadedRelease } from '$lib/data';
  import { formatYear, normalizeYear } from '$lib/history';
  import {
    MACHINE_PROSE_DISCLOSURE,
    type YearDossier,
    type YearIndex
  } from '$lib/year-contracts';
  import { availableYears, loadYearDossier, loadYearIndex, yearEntry } from '$lib/year-data';

  const DATA_BASE = (import.meta.env.VITE_DATA_BASE as string | undefined) || '/data';

  let release: LoadedRelease | null = null;
  let index: YearIndex | null = null;
  let dossier: YearDossier | null = null;
  let year: number | null = null;
  let loading = true;
  let errorMessage = '';

  $: reachable = availableYears(index);
  $: neighbours = index
    ? index.years.map((entry) => entry.year).sort((left, right) => left - right)
    : [];
  $: position = year === null ? -1 : neighbours.indexOf(year);
  $: previousYear = position > 0 ? neighbours[position - 1] : null;
  $: nextYear = position >= 0 && position < neighbours.length - 1 ? neighbours[position + 1] : null;
  $: entry = year === null ? undefined : yearEntry(index, year);

  // A document this long needs a spine. The rail also puts the empty left margin to work.
  let activeSection = 'shape';
  const CONTENTS = [
    { id: 'shape', label: 'The shape of the year' },
    { id: 'anchors', label: 'What it is remembered for' },
    { id: 'strands', label: 'Across the year' },
    { id: 'works', label: 'What was made' },
    { id: 'standing', label: 'Standing through the year' },
    { id: 'register', label: 'The register' },
    { id: 'related', label: 'Years it names' },
    { id: 'provenance', label: 'Where this came from' }
  ];

  function watchSections(): () => void {
    let queued = false;
    const measure = (): void => {
      queued = false;
      let current = CONTENTS[0].id;
      for (const item of CONTENTS) {
        const element = document.getElementById(item.id);
        if (element && element.getBoundingClientRect().top <= 140) current = item.id;
      }
      activeSection = current;
    };
    const onScroll = (): void => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }

  // onMount stays synchronous so it can return a cleanup; the load runs inside it.
  onMount(() => {
    let stop: (() => void) | undefined;
    void (async () => {
    const params = new URL(window.location.href).searchParams;
    const candidate = Number(params.get('year'));
    if (Number.isFinite(candidate) && candidate !== 0) year = normalizeYear(candidate);

    try {
      release = await loadRelease(DATA_BASE);
      index = await loadYearIndex(release);
      if (year === null) year = index?.years[0]?.year ?? null;
      if (year !== null) dossier = await loadYearDossier(release, index, year);
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'The year page could not be opened.';
    } finally {
      loading = false;
    }
    // The sections only exist once the dossier has rendered.
    await tick();
    if (dossier) stop = watchSections();
    })();
    return () => stop?.();
  });
</script>

<svelte:head>
  <title>{year ? `${formatYear(year)} — Palimpsest` : 'A year in the world — Palimpsest'}</title>
  <meta
    name="description"
    content={dossier ? dossier.headlines[0]?.text ?? dossier.lede.slice(0, 150) : 'A source-assembled account of a single year.'}
  />
</svelte:head>

<header class="masthead">
  <a class="brand" href="/"><span class="brand-mark" aria-hidden="true"></span><span>Palimpsest</span></a>
  <nav>
    {#if year !== null}<a href={`/browse?year=${year}`}>Browse {formatYear(year)}</a>{/if}
    <a href={year !== null ? `/?year=${year}` : '/'}>Return to the map <span aria-hidden="true">↗</span></a>
  </nav>
</header>

<main>
  {#if loading}
    <p class="status" aria-live="polite">Opening the year…</p>
  {:else if errorMessage}
    <p class="status error" role="alert">{errorMessage}</p>
  {:else if !dossier}
    <section class="status-block">
      <p class="hj-section-label">No dossier for this year</p>
      <h1>{year !== null ? formatYear(year) : 'A year in the world'}</h1>
      <p class="hj-prose">
        This release does not carry a written year page for {year !== null ? formatYear(year) : 'that year'}.
        That is a gap in what has been written, not evidence that the year was uneventful.
      </p>
      {#if neighbours.length}
        <p class="hj-section-label" style="margin-top:var(--s-6)">Years this release does carry</p>
        <ul class="year-chips">
          {#each neighbours as available}
            <li><a href={`/year?year=${available}`} class="hj-numeral">{formatYear(available)}</a></li>
          {/each}
        </ul>
      {/if}
    </section>
  {:else}
    <article>
      <header class="hero">
        <p class="hero-kicker">A year in the world</p>
        <h1 class="hj-numeral">{Math.abs(dossier.year)}<small>{dossier.year < 0 ? 'BCE' : 'CE'}</small></h1>

        <!--
          The lede is assembled from the sources' own words, so it carries no machine-written
          warning. Applying one uniformly would make the warning meaningless where it matters.
        -->
        <div class="lede">
          <YearProse prose={dossier.lede} links={dossier.lede_links} tone="lede" />
          <p class="provenance">
            {dossier.lede_kind === 'assembled'
              ? 'The three records the sources say most about, in their own words. Nothing here was generated.'
              : 'Machine-written from the records below.'}
          </p>
        </div>
      </header>

      <div class="spread">
      <aside class="contents" aria-label="On this page">
        <nav>
          {#each CONTENTS as item (item.id)}
            <a href={`#${item.id}`} class:current={activeSection === item.id}>{item.label}</a>
          {/each}
        </nav>
      </aside>

      <div class="column">
      <section id="shape" class="shape" aria-labelledby="shape-title">
        <h2 class="opener" id="shape-title">The shape of the year</h2>
        <dl class="counts">
          <div><dt class="hj-numeral">{dossier.overview.event_count.toLocaleString('en')}</dt><dd>events</dd></div>
          <div><dt class="hj-numeral">{dossier.overview.birth_count.toLocaleString('en')}</dt><dd>born</dd></div>
          <div><dt class="hj-numeral">{dossier.overview.death_count.toLocaleString('en')}</dt><dd>died</dd></div>
          <div><dt class="hj-numeral">{dossier.overview.dated_count.toLocaleString('en')}</dt><dd>dated to the day</dd></div>
        </dl>

        <div class="generated">
          <p class="machine-tag">Machine-written</p>
          <YearProse prose={dossier.overview.prose} links={dossier.overview.links} />
        </div>

        <p class="disclosure">{MACHINE_PROSE_DISCLOSURE}</p>
      </section>

      {#if dossier.anchors.length}
        <section id="anchors" class="anchors" aria-labelledby="anchors-title">
          <h2 class="opener" id="anchors-title">What the year is remembered for</h2>
          {#each dossier.anchors as anchor (anchor.anchor_id)}
            <article class="anchor" class:no-image={!anchor.image}>
              <div class="anchor-body">
                <p class="anchor-date">{anchor.date_text ?? 'Undated'}</p>
                <h3>{anchor.heading}</h3>
                <div class="generated">
                  <p class="machine-tag">Machine-written</p>
                  <YearProse prose={anchor.prose} links={anchor.links} />
                </div>
              </div>
              {#if anchor.image}
                <div class="anchor-figure"><YearFigure image={anchor.image} /></div>
              {/if}
            </article>
          {/each}
        </section>
      {/if}

      {#if dossier.sections.length}
        <section id="strands" class="sections" aria-labelledby="sections-title">
          <h2 class="opener" id="sections-title">Across the year</h2>
          <div class="strands-grid">
          {#each dossier.sections as section (section.section_id)}
            <article class="strand">
              <h3>{section.heading}</h3>
              <div class="generated">
                <p class="machine-tag">Machine-written</p>
                <YearProse prose={section.prose} links={section.links} />
              </div>
            </article>
          {/each}
        </div>
        </section>
      {/if}

      {#if dossier.works.length}
        <section id="works" class="works" aria-labelledby="works-title">
          <h2 class="opener" id="works-title">What was made</h2>
          <ul>
            {#each dossier.works as work (work.entry_id)}
              <li>
                <p class="work-kind">{work.kind.replaceAll('_', ' ')}</p>
                <div class="work-body">
                  <!-- `title` is a clean title for some records and a whole source sentence
                       for others (6 to 391 characters here), so it is set as prose once it
                       stops being a title. -->
                  <h4 class:sentence={work.title.length > 80}>
                    {#if work.subject_url}
                      <a href={work.subject_url} target="_blank" rel="noreferrer">{work.title}</a>
                    {:else}{work.title}{/if}
                  </h4>
                  {#if work.creator}<p class="work-creator">{work.creator}</p>{/if}
                  {#if work.gloss}
                    <div class="generated tight">
                      <span class="machine-tag">Machine-written</span>
                      <YearProse prose={work.gloss} links={work.gloss_links} />
                    </div>
                  {/if}
                </div>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      {#if dossier.incumbents.length || dossier.conflicts.length}
        <section id="standing" class="standing" aria-labelledby="standing-title">
          <h2 class="opener" id="standing-title">Standing through the year</h2>
          <div class="standing-grid">
            {#if dossier.incumbents.length}
              <div>
                <h3>Offices held</h3>
                <ul class="rows">
                  {#each dossier.incumbents as incumbent (incumbent.entry_id)}
                    <li>
                      <span class="row-label">{incumbent.office}{incumbent.place ? `, ${incumbent.place}` : ''}</span>
                      <span class="row-value">{incumbent.holder}</span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            {#if dossier.conflicts.length}
              <div>
                <h3>Wars in progress</h3>
                <ul class="rows">
                  {#each dossier.conflicts as conflict (conflict.title)}
                    <li>
                      <span class="row-label hj-numeral">{conflict.start_year ?? '?'}–{conflict.end_year ?? '?'}</span>
                      <span class="row-value">
                        <a href={conflict.url} target="_blank" rel="noreferrer">{conflict.title}</a>
                        {#if conflict.began_this_year}<em>began this year</em>{/if}
                        {#if conflict.ended_this_year}<em>ended this year</em>{/if}
                      </span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          </div>
        </section>
      {/if}

      <section id="register" class="register-section" aria-labelledby="register-title">
        <div class="register-head">
          <h2 class="opener" id="register-title">The register</h2>
          <p class="hj-caveat">
            Every record the sources carry for this year, verbatim. Ordered by date, not by
            importance — the sources' own emphasis is not a ranking of what mattered.
          </p>
        </div>
        <YearRegister entries={dossier.register_entries} />
      </section>

      {#if dossier.related_years.length}
        <section id="related" class="related" aria-labelledby="related-title">
          <h2 class="opener" id="related-title">Years this one names</h2>
          <p class="hj-caveat">
            Parsed from the records. A year is only a link when this release actually carries a
            page for it; the rest are shown as the plain numbers they are.
          </p>
          <ul class="year-chips">
            {#each dossier.related_years as related (related.year)}
              <li>
                {#if reachable.has(related.year)}
                  <a href={`/year?year=${related.year}`} class="hj-numeral">{formatYear(related.year)}</a>
                {:else}
                  <span class="hj-numeral unreachable">{formatYear(related.year)}</span>
                {/if}
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      <footer id="provenance" class="provenance-footer">
        <div>
          <p class="hj-section-label">Where this came from</p>
          <ul class="plain">
            {#each dossier.source_refs as source (source.url)}
              <li>
                <a class="office" href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                <span class="holder">{source.citation} · {source.license_id}</span>
              </li>
            {/each}
          </ul>
        </div>
        <div>
          <p class="hj-section-label">How the prose was made</p>
          <p class="hj-meta">
            Written by {dossier.generation.model_identifier} on prompt {dossier.generation.prompt_version},
            from chronicle revision {dossier.chronicle_revision_id}. Editorial state:
            {dossier.editorial_state.replaceAll('_', ' ')}.
          </p>
          <p class="hj-mono build-id">{dossier.dossier_id}</p>
        </div>
      </footer>

      </div>
      </div>

      <nav class="year-nav" aria-label="Move between years this release carries">
        {#if previousYear !== null}
          <a href={`/year?year=${previousYear}`}><span aria-hidden="true">←</span> {formatYear(previousYear)}</a>
        {:else}<span></span>{/if}
        {#if entry}<p class="hj-meta">{entry.record_count.toLocaleString('en')} records · {entry.image_count.toLocaleString('en')} pictures</p>{/if}
        {#if nextYear !== null}
          <a href={`/year?year=${nextYear}`}>{formatYear(nextYear)} <span aria-hidden="true">→</span></a>
        {:else}<span></span>{/if}
      </nav>
    </article>
  {/if}
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
  }
  .brand { display: flex; align-items: center; gap: var(--s-3); color: inherit; font-family: var(--font-display); font-size: var(--t-md); text-decoration: none; }
  .brand-mark {
    width: 17px;
    height: 17px;
    flex: none;
    border: 1px solid var(--accent);
    background: linear-gradient(to right, transparent calc(50% - 0.5px), var(--accent) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px));
  }
  .masthead nav { display: flex; gap: var(--s-5); }
  .masthead nav a { color: var(--accent); font-size: var(--t-sm); font-weight: 500; text-decoration: none; }
  .masthead nav a:hover { text-decoration: underline; text-underline-offset: 4px; }

  main { --gutter: max(var(--s-5), calc((100vw - 1160px) / 2)); --measure: 68ch; }
  .hero, .year-nav, .status-block { padding-inline: var(--gutter); }

  /*
    The reading column was 576px of a 1440px viewport, left-aligned, for 24,000px — most of
    the page was empty margin and there was no way to navigate it. The spread puts a sticky
    contents rail in that margin and lets wide blocks use the full column.
  */
  .spread {
    display: grid;
    grid-template-columns: 196px minmax(0, 1fr);
    gap: var(--s-8);
    padding-inline: var(--gutter);
  }
  /* The alternating sections paint their full-bleed ground with a 100vmax box-shadow,
     which reaches across the rail. The nav has to sit above it or it gets covered. */
  .contents { position: relative; z-index: 2; }
  /* One continuous hairline the whole nav hangs from, with the reader's position marked
     as a segment of it. Per-link borders with gaps between them drew a dashed line that
     described nothing. */
  .contents nav {
    position: sticky;
    top: var(--s-5);
    display: grid;
    gap: 0;
    padding: var(--s-3) 0;
  }
  .contents nav::before {
    content: '';
    position: absolute;
    top: var(--s-3);
    bottom: var(--s-3);
    left: 0;
    width: 1px;
    background: var(--line);
  }
  .contents a {
    position: relative;
    padding: 8px 0 8px var(--s-4);
    color: var(--text-faint);
    font-size: var(--t-xs);
    line-height: 1.45;
    text-decoration: none;
    transition: color 0.16s var(--ease);
  }
  .contents a::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 2px;
    background: transparent;
    transition: background 0.16s var(--ease);
  }
  .contents a:hover { color: var(--text); }
  .contents a:hover::before { background: var(--line-strong); }
  .contents a.current { color: var(--accent); font-weight: 600; }
  .contents a.current::before { background: var(--accent); }

  .column { min-width: 0; }
  .column > section:nth-of-type(odd) {
    background: var(--surface);
    box-shadow: 0 0 0 100vmax var(--surface);
    clip-path: inset(0 -100vmax);
  }
  .column > section:first-child { padding-top: var(--s-6); }

  .status, .status-block { padding: var(--s-9) var(--gutter); }
  .status { color: var(--text-dim); font-family: var(--font-display); font-size: var(--t-lg); }
  .status.error { color: var(--conf-d); }
  .status-block h1 { margin: 0 0 var(--s-4); font-family: var(--font-display); font-size: var(--t-3xl); font-weight: 300; }
  .status-block .hj-prose { max-width: 60ch; }

  /* The year itself is the whole hero. Nothing else in the product is one integer this large. */
  .hero {
    display: grid;
    grid-template-columns: 208px minmax(0, 1fr);
    gap: 0 var(--s-8);
    padding-top: var(--s-8);
    padding-bottom: var(--s-7);
    background: var(--surface);
    border-bottom: 1px solid var(--line);
  }
  .hero-kicker, .hero h1 { grid-column: 1 / -1; }
  .hero .lede { grid-column: 2; }
  .hero-kicker { margin: 0 0 var(--s-3); color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.11em; text-transform: uppercase; }
  .hero h1 {
    display: flex;
    align-items: baseline;
    gap: var(--s-4);
    margin: 0 0 var(--s-6);
    font-family: var(--font-display);
    font-size: clamp(72px, 13vw, 168px);
    font-weight: 300;
    line-height: 0.86;
    letter-spacing: -0.05em;
  }
  .hero h1 small { color: var(--text-faint); font-size: clamp(18px, 2vw, 28px); font-weight: 400; letter-spacing: 0.04em; }
  .lede { max-width: 60ch; }
  .lede :global(p:not(.provenance)) { font-size: 24px; line-height: 1.5; }
  .provenance { margin: var(--s-4) 0 0; color: var(--text-faint); font-size: var(--t-xs); line-height: var(--lh-body); }

  section { padding-block: var(--s-7); border-bottom: 1px solid var(--line); }

  /* A chapter opener. Without one, eight sections read as a single undifferentiated
     ribbon when the page is seen whole — which is exactly how it read. */
  .opener {
    max-width: 18ch;
    margin: 0 0 var(--s-6);
    font-family: var(--font-display);
    font-size: var(--t-3xl);
    font-weight: 300;
    line-height: 1.02;
    letter-spacing: -0.03em;
    text-wrap: balance;
  }

  .counts { display: flex; flex-wrap: wrap; gap: var(--s-4) var(--s-7); margin: 0 0 var(--s-6); }
  .counts div { display: flex; align-items: baseline; gap: var(--s-2); }
  .counts dt { font-family: var(--font-display); font-size: var(--t-xl); font-weight: 400; }
  .counts dd { margin: 0; color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; }

  /*
    Assembled and generated must not look alike. Generated prose is inset behind a rule and
    tagged; assembled prose runs full measure with nothing attached to it. The distinction is
    formal rather than chromatic, because colour here already means confidence or interaction.
  */
  .generated { max-width: var(--measure); padding-left: var(--s-5); border-left: 1px solid var(--line-strong); }
  .generated :global(p) { font-size: var(--t-read); line-height: var(--lh-body); }
  .generated.tight { padding-left: var(--s-3); }
  .machine-tag {
    margin: 0 0 var(--s-2);
    color: var(--text-faint);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }
  .disclosure {
    max-width: var(--measure);
    margin: var(--s-6) 0 0;
    padding: var(--s-4);
    background: var(--bg-sunk);
    color: var(--text-dim);
    font-size: var(--t-sm);
    line-height: var(--lh-body);
  }

  .anchor { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: var(--s-7); padding: var(--s-7) 0; border-top: 1px solid var(--line); }
  /* Without a picture the second column is dead space, not a layout. */
  .anchor.no-image { grid-template-columns: minmax(0, 1fr); }
  .anchor-figure { grid-column: 1; grid-row: 1; }
  .anchor-body { min-width: 0; }
  /* Portraits are much taller than the paragraph beside them, and an unbounded figure
     sets the row height, leaving a column of dead space. Bounded and letterboxed rather
     than cropped: cropping someone's portrait to fit a grid is a decision about the
     artwork, not about the layout. */
  .anchor-figure :global(img) { max-height: 380px; object-fit: contain; object-position: top; }
  .anchors > .anchor:first-of-type { border-top: 0; }
  .anchor-date { margin: 0 0 var(--s-2); color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; }
  .anchor h3, .strand h3 {
    margin: 0 0 var(--s-4);
    font-family: var(--font-display);
    font-size: var(--t-2xl);
    font-weight: 300;
    line-height: 1.06;
    letter-spacing: -0.025em;
    text-wrap: balance;
  }
  .strands-grid { display: grid; gap: var(--s-6); }
  .strand { padding: 0; }

  .strand h3 { font-size: var(--t-lg); }

  /* Rows on the register's rhythm. A grid of equal-height cells gave two-line entries the
     same box as a twenty-line one, so most of the section was void. */
  .works ul { margin: 0; padding: 0; list-style: none; }
  .works li {
    display: grid;
    grid-template-columns: 108px minmax(0, 1fr);
    gap: var(--s-5);
    padding: var(--s-4) 0;
    border-bottom: 1px solid var(--line);
  }
  .works li:last-child { border-bottom: 0; }
  .work-body { min-width: 0; max-width: 62ch; }
  .work-kind { margin: 0; color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; line-height: 1.9; letter-spacing: 0.07em; text-transform: uppercase; }
  .works h4 { margin: 0; font-family: var(--font-display); font-size: var(--t-lg); font-weight: 400; line-height: 1.24; letter-spacing: -0.012em; }
  .works h4.sentence { font-size: var(--t-md); line-height: 1.6; letter-spacing: 0; }
  .work-creator { margin: var(--s-1) 0 0; color: var(--text-dim); font-size: var(--t-sm); }
  .works h4 a { color: inherit; text-decoration: underline; text-decoration-color: var(--accent-line); text-underline-offset: 4px; }
  .works h4 a:hover { color: var(--accent); text-decoration-color: var(--accent); }
  .works .generated { margin-top: var(--s-2); }
  .works .generated :global(p) { font-size: var(--t-sm); line-height: 1.6; }
  .works .machine-tag { display: block; margin-bottom: 2px; }

  .standing-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-7); align-items: start; }
  .standing h3 { margin: 0 0 var(--s-3); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase; color: var(--text-faint); }
  ul.plain { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
  ul.plain li { display: grid; gap: 2px; padding: var(--s-3) 0; border-bottom: 1px solid var(--line); }

  ul.rows { margin: 0; padding: 0; list-style: none; }
  ul.rows li {
    display: grid;
    grid-template-columns: 132px minmax(0, 1fr);
    gap: var(--s-4);
    padding: var(--s-3) 0;
    border-bottom: 1px solid var(--line);
  }
  ul.rows li:last-child { border-bottom: 0; }
  .row-label { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.85; letter-spacing: 0.02em; }
  .row-value { min-width: 0; color: var(--text); font-family: var(--font-display); font-size: var(--t-md); line-height: 1.45; }
  .row-value a { color: inherit; text-decoration: underline; text-decoration-color: var(--accent-line); text-underline-offset: 3px; }
  .row-value a:hover { color: var(--accent); text-decoration-color: var(--accent); }
  .row-value em {
    display: block;
    color: var(--text-faint);
    font-family: var(--font-ui);
    font-size: var(--t-xs);
    font-style: normal;
    letter-spacing: 0.04em;
  }
  .office { font-family: var(--font-display); font-size: var(--t-base); color: var(--text); text-decoration: none; }
  a.office { text-decoration: underline; text-decoration-color: var(--accent-line); text-underline-offset: 3px; }
  a.office:hover { color: var(--accent); text-decoration-color: var(--accent); }
  .holder { color: var(--text-faint); font-size: var(--t-xs); }

  .register-head { max-width: var(--measure); margin-bottom: var(--s-6); }

  .year-chips { display: flex; flex-wrap: wrap; gap: var(--s-2); margin: 0; padding: 0; list-style: none; }
  .year-chips a, .year-chips .unreachable {
    display: inline-block;
    padding: 5px var(--s-3);
    border: 1px solid var(--line);
    font-size: var(--t-xs);
    text-decoration: none;
  }
  .year-chips a { border-color: var(--accent-line); color: var(--accent); font-weight: 500; }
  .year-chips a:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
  .year-chips .unreachable { color: var(--text-faint); }

  .provenance-footer { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-7); padding-block: var(--s-8); border-bottom: 1px solid var(--line); }
  .build-id { margin: var(--s-3) 0 0; color: var(--text-faint); overflow-wrap: anywhere; }

  .year-nav { display: flex; align-items: center; justify-content: space-between; gap: var(--s-4); padding-block: var(--s-6) var(--s-9); }
  .year-nav a { color: var(--accent); font-size: var(--t-sm); font-weight: 500; text-decoration: none; }
  .year-nav a:hover { text-decoration: underline; text-underline-offset: 4px; }

  /* Below the rail's width the spread collapses, and the contents become a sticky strip —
     a 16,000px document needs navigation more on a phone, not less. */
  @media (max-width: 1080px) {
    .spread { grid-template-columns: minmax(0, 1fr); gap: 0; }
    .hero { grid-template-columns: minmax(0, 1fr); }
    .hero .lede { grid-column: 1; }
    .contents { position: sticky; top: 0; z-index: 5; margin-inline: calc(-1 * var(--gutter)); background: var(--surface); border-bottom: 1px solid var(--line); }
    .contents nav {
      position: static;
      display: flex;
      gap: 0;
      padding: 0 var(--gutter);
      overflow-x: auto;
      scrollbar-width: none;
    }
    .contents nav::-webkit-scrollbar { display: none; }
    .contents a { flex: none; padding: var(--s-3) var(--s-3); border-left: 0; border-bottom: 2px solid transparent; white-space: nowrap; }
    .contents a:hover { border-left: 0; border-bottom-color: var(--line-strong); }
    .contents a.current { border-left: 0; border-bottom-color: var(--accent); }
  }

  @media (max-width: 1000px) {
    .anchor { grid-template-columns: 1fr; gap: var(--s-4); }
    .anchor-figure { max-width: 320px; }
    .works ul { grid-template-columns: repeat(2, 1fr); }

  }

  @media (max-width: 720px) {
    .masthead { padding-inline: var(--s-4); }
    .masthead nav a:first-child { display: none; }
    .hero { padding-top: var(--s-6); }
    section, .provenance-footer { padding-block: var(--s-6); }
    .standing-grid, .provenance-footer { grid-template-columns: 1fr; gap: var(--s-5); }
    .works ul { grid-template-columns: 1fr; }
  }
</style>
