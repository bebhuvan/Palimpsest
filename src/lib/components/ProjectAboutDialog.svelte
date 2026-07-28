<script lang="ts">
  import type { AttributionReport, LoadedRelease, QualityReport } from '$lib/data';
  import { gradeInk, gradeMeaning } from '$lib/density';

  let {
    release,
    quality,
    attributions
  }: {
    release: LoadedRelease | null;
    quality: QualityReport | null;
    attributions: AttributionReport | null;
  } = $props();

  let dialog: HTMLDialogElement;

  export function open(): void {
    dialog?.showModal();
  }

  function close(): void {
    dialog?.close();
  }

  const GRADES = ['A', 'B', 'C', 'D'];
</script>

<dialog
  class="about"
  bind:this={dialog}
  onclick={(event) => event.currentTarget === event.target && close()}
>
  <div class="inner">
    <header>
      <div>
        <p class="hj-section-label">Read the map critically</p>
        <h2>This map shows source claims, not settled borders.</h2>
      </div>
      <button class="close" onclick={close} aria-label="Close about this map">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6.6 6.6 10.8 10.8M17.4 6.6 6.6 17.4" /></svg>
      </button>
    </header>

    <div class="grid">
      <div class="method">
        <p>Each shape preserves one source’s interpretation and date interval. Control could overlap, change seasonally, or be understood differently elsewhere. The interface never interpolates a new boundary between dated geometries.</p>
        <p>Hatched cells mean this release has no mapped coverage for that place and year. They do not mean nobody lived there or nothing happened there.</p>
        <p>OpenHistoricalMap supplies live, contributor-built detail and labels. The reviewed Palimpsest layer stays separate; overlapping geometries are never merged or presented as agreement. Natural Earth land and water are modern reference geography for orientation only.</p>
        <p>The thematic lenses are non-exclusive discovery views. A record may appear in several, and an empty lens means this release has no classified record — not that the history is absent.</p>

        <h3 class="hj-section-label">Colour means one thing</h3>
        <p class="key-intro">Hue in this interface encodes evidential confidence and nothing else. The lenses are told apart by mark, so a colour you see is always a claim about how well something is known.</p>
        <ul class="grades">
          {#each GRADES as grade}
            <li style={`--grade: ${gradeInk(grade)}`}><b>{grade}</b><span>{gradeMeaning(grade)}</span></li>
          {/each}
        </ul>

        <h3 class="hj-section-label">Map key</h3>
        <ul class="key">
          <li><i class="control"></i><span><strong>Territorial control</strong> — reconstructed area with a firmer edge</span></li>
          <li><i class="soft"></i><span><strong>Region, influence or claim</strong> — softer fill and broken edge</span></li>
          <li><i class="contested"></i><span><strong>Contested interpretation</strong> — a distinct broken edge</span></li>
          <li><i class="gap"></i><span><strong>Coverage gap</strong> — absent from this release</span></li>
        </ul>

        <p class="archive-note">The timeline gives each archive band equal width, so horizontal distance is not proportional to elapsed time. The boundary years are marked on the scale, and the ribbon above it plots how many features this release actually holds at each date.</p>
      </div>

      <aside class="release">
        <dl class="stats">
          <div><dt>Release</dt><dd class="hj-mono">{release?.manifest.build_id ?? '—'}</dd></div>
          <div><dt>Published</dt><dd>{release ? new Date(release.manifest.generated_at).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}</dd></div>
          <div><dt>Map records</dt><dd class="hj-numeral">{quality?.accepted_feature_count?.toLocaleString('en') ?? '—'}</dd></div>
          <div><dt>Rejected</dt><dd class="hj-numeral">{quality?.rejected_record_count?.toLocaleString('en') ?? release?.manifest.rejected_record_count ?? '—'}</dd></div>
        </dl>

        <h3 class="hj-section-label">Sources in this release</h3>
        <div class="sources">
          <a href="https://www.openhistoricalmap.org/copyright" target="_blank" rel="noreferrer">
            <span>OpenHistoricalMap live detail</span>
            <small>OpenHistoricalMap contributors · CC0 by default; element overrides may apply</small>
          </a>
          {#each attributions ?? release?.manifest.sources ?? [] as source (source.source_id)}
            <a href={source.url} target="_blank" rel="noreferrer">
              <span>{source.title}</span>
              <small>{source.publisher} · {source.license_id}</small>
            </a>
          {/each}
        </div>

        <p class="release-id hj-mono">Schema {release?.manifest.schema_version ?? '—'} · immutable build {release?.manifest.build_id ?? '—'}</p>
      </aside>
    </div>
  </div>
</dialog>

<style>
  .about {
    width: min(980px, calc(100vw - 32px));
    max-height: calc(100dvh - 48px);
    padding: 0;
    border: 1px solid var(--line-strong);
    border-radius: 0;
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 40px 100px rgb(20 23 42 / 0.12);
  }
  .about::backdrop { background: rgb(20 23 42 / 0.42); }

  .inner { padding: var(--s-6) var(--s-7) var(--s-6); }

  header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--s-6); padding-bottom: var(--s-5); border-bottom: 1px solid var(--line); }
  h2 {
    max-width: 20ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--t-3xl);
    font-weight: 400;
    line-height: 1.04;
    letter-spacing: -0.024em;
    text-wrap: balance;
  }

  .close {
    flex: none;
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--line);
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
  }
  .close svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.4; stroke-linecap: round; }
  .close:hover { border-color: var(--accent); background: var(--accent); color: #fff; }

  .grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr); gap: var(--s-7); padding-top: var(--s-5); }

  .method > p { margin: 0 0 var(--s-3); color: var(--text-dim); font-family: var(--font-display); font-size: var(--t-base); line-height: var(--lh-body); }
  .method h3 { margin: var(--s-6) 0 var(--s-3); color: var(--text-faint); }
  .key-intro { font-size: var(--t-sm) !important; }

  .grades { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
  .grades li { display: flex; align-items: center; gap: var(--s-3); padding: var(--s-2) 0; border-bottom: 1px solid var(--line); }
  .grades b {
    width: 26px;
    flex: none;
    color: var(--grade);
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-weight: 400;
    text-align: center;
  }
  .grades li span { color: var(--text-dim); font-size: var(--t-sm); }

  .key { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
  .key li { display: flex; align-items: center; gap: var(--s-3); padding: var(--s-2) 0; border-bottom: 1px solid var(--line); color: var(--text-dim); font-size: var(--t-sm); line-height: 1.45; }
  .key strong { color: var(--text); font-weight: 600; }
  .key i { display: inline-block; flex: none; width: 24px; height: 11px; }
  .key .control { border: 1px solid #625d59; background: rgb(118 88 79 / 0.11); }
  .key .soft { border: 1px dashed #68766f; background: rgb(95 113 107 / 0.075); }
  .key .contested { border: 1px dashed #8e5a50; background: rgb(142 90 80 / 0.055); }
  .key .gap { opacity: 0.72; background-image: radial-gradient(circle, #3d4840 0.8px, transparent 1px); background-size: 6px 6px; }

  .archive-note {
    margin-top: var(--s-5) !important;
    padding: var(--s-3) var(--s-4);
    border-left: 2px solid var(--line-strong);
    background: var(--bg-sunk);
    font-family: var(--font-ui) !important;
    font-size: var(--t-sm) !important;
  }

  .release { border-left: 1px solid var(--line); padding-left: var(--s-6); }
  .release h3 { margin: var(--s-6) 0 var(--s-3); color: var(--text-faint); }

  .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 0; border: 1px solid var(--line); background: var(--line); }
  .stats div { min-width: 0; padding: var(--s-3); background: var(--surface); }
  .stats dt { margin-bottom: var(--s-1); color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
  .stats dd { margin: 0; overflow: hidden; font-family: var(--font-display); font-size: var(--t-md); text-overflow: ellipsis; white-space: nowrap; }
  .stats dd.hj-mono { font-family: var(--font-mono); font-size: var(--t-sm); }

  .sources { border-top: 1px solid var(--line); }
  .sources a { display: grid; gap: 2px; padding: var(--s-3) 0; border-bottom: 1px solid var(--line); color: inherit; text-decoration: none; }
  .sources span { font-family: var(--font-display); font-size: var(--t-md); }
  .sources a:hover span { text-decoration: underline; text-underline-offset: 3px; }
  .sources small { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.45; }

  .release-id { margin: var(--s-4) 0 0; color: var(--text-faint); }

  @media (max-width: 860px) {
    .inner { padding: var(--s-5) var(--s-4); }
    h2 { font-size: var(--t-2xl); }
    .grid { grid-template-columns: 1fr; gap: var(--s-5); }
    .release { border-left: 0; border-top: 1px solid var(--line); padding-left: 0; padding-top: var(--s-5); }
  }
</style>
