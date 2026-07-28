<script lang="ts">
  import type { DossierRestatement, HistoricalDossier, RestatementTimelineEntry } from '$lib/data';
  import { formatYear } from '$lib/history';
  import { restatementLabel } from '$lib/reader-presentation';

  let {
    restatement,
    dossier,
    selectedYear
  }: {
    restatement: DossierRestatement;
    dossier: HistoricalDossier;
    selectedYear: number;
  } = $props();

  let showSource = $state(false);

  // The prose is year-agnostic and cached; the year-awareness comes from the structured timeline,
  // which the reader re-anchors on every slider move without refetching anything.
  const anchored = $derived(anchorIndex(restatement.timeline, selectedYear));

  function anchorIndex(timeline: RestatementTimelineEntry[], year: number): number {
    let index = -1;
    for (let position = 0; position < timeline.length; position += 1) {
      if (timeline[position].sort_year <= year) index = position;
    }
    return index;
  }

  function relation(entry: RestatementTimelineEntry, position: number): string {
    if (position === anchored) return 'current';
    return entry.sort_year <= selectedYear ? 'past' : 'future';
  }

  const paragraphs = $derived(restatement.text.trim().split('\n').filter(Boolean));
  const sourceParagraphs = $derived(dossier.extract.trim().split('\n').filter(Boolean));
</script>

<section class="hj-section restatement" aria-labelledby="restatement-heading">
  <p class="hj-section-label" id="restatement-heading">{restatementLabel(dossier)}</p>
  <h2>{dossier.title}</h2>
  <p class="headline">{restatement.headline}</p>

  {#each paragraphs as paragraph}
    <p class="hj-prose">{paragraph}</p>
  {/each}

  {#if restatement.timeline.length}
    <ol class="timeline" aria-label={`Dated moments, read against ${formatYear(selectedYear)}`}>
      {#each restatement.timeline as entry, position (entry.sort_year + entry.year_text)}
        <li data-relation={relation(entry, position)}>
          <span class="when hj-numeral">{entry.year_text}</span>
          <span class="what">{entry.text}</span>
          {#if position === anchored}<span class="anchor">by {formatYear(selectedYear)}</span>{/if}
        </li>
      {/each}
    </ol>
  {/if}

  <footer>
    <button class="hj-inline-button" onclick={() => (showSource = !showSource)} aria-expanded={showSource}>
      {showSource ? 'Hide' : 'Show'} the original extract
    </button>
    <a class="hj-link" href={dossier.url} target="_blank" rel="noreferrer">Read at source <span aria-hidden="true">↗</span></a>
    <small>
      {dossier.source_ref.citation} · {dossier.source_ref.license_id}{restatement.source_revision_id ? ` · revision ${restatement.source_revision_id}` : ''}
    </small>
    <small class="method">
      Reworded from that one revision by {restatement.generation.model_identifier}. No fact was added:
      every name and number here also appears in the extract.
    </small>
  </footer>

  {#if showSource}
    <div class="source" aria-label="Original source extract">
      {#each sourceParagraphs as paragraph}<p>{paragraph}</p>{/each}
    </div>
  {/if}
</section>

<style>
  h2 {
    margin: 0 0 var(--s-2);
    font-family: var(--font-display);
    font-size: var(--t-xl);
    font-weight: 500;
    line-height: var(--lh-tight);
    letter-spacing: -0.016em;
  }
  .headline {
    margin: 0 0 var(--s-4);
    color: var(--text);
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-style: italic;
    font-weight: 400;
    line-height: var(--lh-snug);
  }

  /* The reader's selected year is a real position in this list, so it is marked as
     one: everything after the anchor has not happened yet at this date. */
  .timeline { margin: var(--s-5) 0 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
  .timeline li {
    position: relative;
    display: grid;
    grid-template-columns: 78px minmax(0, 1fr);
    gap: var(--s-1) var(--s-4);
    padding: var(--s-2) 0 var(--s-2) var(--s-4);
    border-bottom: 1px solid var(--line);
  }
  .timeline li::before {
    content: '';
    position: absolute;
    top: 15px;
    left: 0;
    width: 5px;
    height: 5px;
    border: 1px solid var(--line-strong);
    border-radius: 50%;
    background: var(--surface);
  }
  .timeline li[data-relation='past']::before { background: var(--line-strong); }
  .timeline li[data-relation='current']::before {
    border-color: var(--text);
    background: var(--text);
    box-shadow: 0 0 0 3px var(--bg-sunk);
  }
  .timeline li[data-relation='future'] { opacity: 0.48; }
  .when { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.55; }
  .timeline li[data-relation='current'] .when { color: var(--text); font-weight: 600; }
  .what { color: var(--text-dim); font-size: var(--t-sm); line-height: 1.5; }
  .anchor { grid-column: 2; color: var(--text); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.04em; }

  footer {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--s-2) var(--s-4);
    margin-top: var(--s-4);
    padding-top: var(--s-3);
    border-top: 1px solid var(--line);
    color: var(--text-faint);
    font-size: var(--t-xs);
    line-height: 1.5;
  }
  footer a { text-align: right; }
  footer small { grid-column: 1 / -1; }
  footer .method { line-height: var(--lh-body); }

  .source { margin-top: var(--s-4); padding: var(--s-4); border-left: 2px solid var(--line-strong); background: var(--bg-sunk); }
  .source p { margin: 0 0 var(--s-3); color: var(--text-dim); font-family: var(--font-display); font-size: var(--t-sm); line-height: var(--lh-body); }
  .source p:last-child { margin: 0; }

  @media (max-width: 860px) {
    .timeline li { grid-template-columns: 1fr; }
    .anchor { grid-column: 1; }
  }
</style>
