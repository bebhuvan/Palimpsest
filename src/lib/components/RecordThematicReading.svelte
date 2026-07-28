<script lang="ts">
  import type { ThematicAssertion } from '$lib/data';
  import { gradeInk } from '$lib/density';
  import { formatRange } from '$lib/history';
  import type { HistoricalLens, HistoricalLensDefinition } from '$lib/lenses';
  import { humanize } from '$lib/reader-presentation';
  import LensMark from '$lib/components/LensMark.svelte';

  let {
    activeLens,
    lens,
    assertions,
    reviewed,
    contentLoading
  }: {
    activeLens: HistoricalLens;
    lens: HistoricalLensDefinition;
    assertions: ThematicAssertion[];
    reviewed: boolean;
    contentLoading: boolean;
  } = $props();
</script>

{#if activeLens !== 'all'}
  <section class="hj-section" aria-label="Active historical lens">
    <p class="hj-section-label"><LensMark lens={activeLens} size={12} /> Viewed through {lens.label}</p>
    <p class="hj-note">{lens.description}</p>
    <p class="hj-meta">Lenses are non-exclusive. The release must carry a structured, sourced assertion before a published record is highlighted.</p>
  </section>
{/if}

{#if reviewed && assertions.length}
  <section class="hj-section" aria-labelledby="classification-title">
    <p class="hj-section-label" id="classification-title">
      Why this record is in {activeLens === 'all' ? 'these lenses' : `the ${lens.label} lens`}
    </p>
    {#each assertions as assertion (assertion.assertion_id)}
      <article class="hj-entry">
        <strong>{activeLens === 'all' ? `${humanize(assertion.theme)} · ` : ''}{humanize(assertion.subtheme)}</strong>
        <p class="hj-note">{assertion.rationale}</p>
        <p class="hj-meta">
          <span class="hj-grade" style={`--grade: ${gradeInk(assertion.confidence.grade)}`}>Confidence {assertion.confidence.grade}</span>
          · {humanize(assertion.classification_basis)} · {humanize(assertion.role)}
          {#if assertion.matched_values.length} · matched {assertion.matched_values.map(humanize).join(', ')}{/if}
        </p>
        <details class="hj-disclosure">
          <summary>Rule and evidence</summary>
          <p class="hj-note">{assertion.confidence.rationale}</p>
          <p class="hj-meta">{assertion.rule_id} · {formatRange(assertion.valid_from, assertion.valid_to)} · {humanize(assertion.review_status)}</p>
          <ul>
            {#each assertion.source_refs as source}
              <li><a class="hj-link" href={source.url} target="_blank" rel="noreferrer">{source.citation}</a></li>
            {/each}
          </ul>
        </details>
      </article>
    {/each}
  </section>
{:else if reviewed && activeLens !== 'all' && !contentLoading}
  <section class="hj-section" aria-label="No thematic assertion">
    <p class="hj-section-label">Not classified in this lens</p>
    <p class="hj-note">
      This record stays visible as baseline geography, but the release carries no sourced
      {lens.label.toLocaleLowerCase()} assertion for it. That is a gap in classification, not evidence
      that the history did not happen.
    </p>
  </section>
{/if}

<style>
  .hj-section-label { display: flex; align-items: center; gap: 7px; }
  .hj-entry:first-of-type { border-top: 0; padding-top: 0; }
</style>
