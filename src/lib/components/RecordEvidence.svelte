<script lang="ts">
  import type { SourceReference } from '$lib/data';
  import { gradeInk, gradeMeaning } from '$lib/density';

  let {
    temporalConfidence,
    spatialConfidence,
    interpretiveConfidence,
    disputeGroup,
    source
  }: {
    temporalConfidence: string;
    spatialConfidence: string;
    interpretiveConfidence: string;
    disputeGroup?: string;
    source: SourceReference | null;
  } = $props();

  const axes = $derived([
    { axis: 'When', grade: temporalConfidence },
    { axis: 'Where', grade: spatialConfidence },
    { axis: 'Interpretation', grade: interpretiveConfidence }
  ]);
</script>

<section class="hj-section" aria-labelledby="evidence-title">
  <p class="hj-section-label" id="evidence-title">Evidence and uncertainty</p>

  <div class="axes">
    {#each axes as reading (reading.axis)}
      <div class="axis" style={`--grade: ${gradeInk(reading.grade)}`}>
        <span class="axis-name">{reading.axis}</span>
        <strong>{reading.grade === 'unknown' ? '—' : reading.grade.toUpperCase()}</strong>
        <span class="axis-meaning">{gradeMeaning(reading.grade)}</span>
      </div>
    {/each}
  </div>

  {#if disputeGroup}
    <p class="flag"><strong>Alternatives exist.</strong> This feature belongs to dispute group {disputeGroup}. The map does not average competing reconstructions.</p>
  {/if}

  <p class="flag">This global archive stops at zoom 7. Enlarging a shape does not make its source more precise.</p>

  {#if source}
    <div class="source">
      <p class="hj-section-label">Geometry source</p>
      <a href={source.url} target="_blank" rel="noreferrer">
        <strong>{source.title}</strong>
        <span>{source.publisher} · {source.license_id} · {source.version ?? 'release snapshot'}</span>
      </a>
    </div>
  {/if}
</section>

<style>
  /* The three confidence readings are the record's most consequential fact, so they
     are stated openly rather than folded into a disclosure the reader never opens. */
  .axes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    margin-bottom: var(--s-4);
    border: 1px solid var(--line);
    background: var(--line);
  }
  .axis { display: grid; gap: 2px; padding: var(--s-3); background: var(--surface); }
  .axis-name { color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
  .axis strong {
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--grade);
    font-family: var(--font-display);
    font-size: var(--t-xl);
    font-weight: 400;
    line-height: 1.1;
  }
  .axis strong::before { content: ''; width: 8px; height: 8px; flex: none; border-radius: 50%; background: var(--grade); }
  .axis-meaning { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.45; }

  .flag {
    margin: 0 0 var(--s-3);
    padding-left: var(--s-3);
    border-left: 2px solid var(--line-strong);
    color: var(--text-dim);
    font-size: var(--t-xs);
    line-height: var(--lh-body);
  }
  .flag strong { color: var(--text); font-weight: 600; }
  .flag:last-of-type { margin-bottom: 0; }

  .source { margin-top: var(--s-5); }
  .source a { display: grid; gap: 3px; color: inherit; text-decoration: none; }
  .source strong { font-family: var(--font-display); font-size: var(--t-md); font-weight: 500; }
  .source a:hover strong { text-decoration: underline; text-underline-offset: 3px; }
  .source span { color: var(--text-faint); font-size: var(--t-xs); }

  @media (max-width: 520px) {
    .axes { grid-template-columns: 1fr; }
  }
</style>
