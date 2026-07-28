<script lang="ts">
  import type { EvidenceAssertion, HistoricalEntity } from '$lib/data';
  import { gradeInk } from '$lib/density';
  import { formatRange, formatYear } from '$lib/history';
  import { humanize } from '$lib/reader-presentation';

  let {
    assertions,
    linkedEntities,
    selectedYear
  }: {
    assertions: EvidenceAssertion[];
    linkedEntities: HistoricalEntity[];
    selectedYear: number;
  } = $props();

  const activeAssertions = $derived(
    assertions.filter(
      (assertion) =>
        assertion.valid_from <= selectedYear &&
        assertion.valid_to >= selectedYear &&
        (!assertion.object.entity_id ||
          linkedEntities.some((entity) => entity.entity_id === assertion.object.entity_id))
    )
  );

  const quantity = new Intl.NumberFormat('en', { maximumFractionDigits: 2 });

  function objectLabel(assertion: EvidenceAssertion): string {
    if (assertion.object.entity_id) {
      const entity = linkedEntities.find((candidate) => candidate.entity_id === assertion.object.entity_id);
      return entity?.names.en ?? Object.values(entity?.names ?? {})[0] ?? 'Linked record';
    }
    if (assertion.object.year) return formatYear(assertion.object.year);
    if (assertion.object.kind === 'number_range') {
      const lower = assertion.object.value_from;
      const upper = assertion.object.value_to;
      const unit = assertion.object.unit ?? '';
      if (lower != null && upper != null && lower !== upper) {
        return `${quantity.format(lower)}–${quantity.format(upper)} ${unit}`.trim();
      }
      if (lower != null) return `${quantity.format(lower)} ${unit}`.trim();
      if (upper != null) return `Up to ${quantity.format(upper)} ${unit}`.trim();
    }
    return assertion.object.value ?? 'Unspecified value';
  }
</script>

{#if activeAssertions.length}
  <section class="hj-section" aria-labelledby="assertion-title">
    <p class="hj-section-label" id="assertion-title">Structured sourced facts</p>
    <p class="hj-caveat">Subject–predicate–object assertions taken from the release. Not generated narrative prose.</p>
    {#each activeAssertions as assertion (assertion.assertion_id)}
      {@const primarySource = assertion.source_refs[0]}
      <article class="hj-entry">
        <strong>{humanize(assertion.predicate)}</strong>
        <p class="object">{objectLabel(assertion)}</p>
        <p class="hj-meta">
          <span class="hj-grade" style={`--grade: ${gradeInk(assertion.confidence.grade)}`}>Confidence {assertion.confidence.grade}</span>
          · {formatRange(assertion.valid_from, assertion.valid_to)} · {humanize(assertion.evidence_basis)}
          {#if primarySource}
            · <a class="hj-link" href={primarySource.url} target="_blank" rel="noreferrer">{primarySource.publisher}</a>
          {/if}
        </p>
        {#if assertion.restatement}
          <p class="explanation">{assertion.restatement.text}</p>
          <p class="generated-note">
            Plain-English restatement by {assertion.restatement.model_identifier}; the value above is unchanged source data.
          </p>
        {:else if assertion.source_excerpt}
          <p class="explanation">{assertion.source_excerpt}</p>
        {/if}
        <details class="hj-disclosure">
          <summary>Evidence and uncertainty</summary>
          <p class="hj-note">{assertion.confidence.rationale}</p>
          {#if assertion.temporal_uncertainty}
            <p class="hj-note">{assertion.temporal_uncertainty.rationale}</p>
          {/if}
          {#if assertion.restatement && assertion.source_excerpt}
            <p class="hj-section-label">Original Seshat explanation</p>
            <p class="hj-note">{assertion.source_excerpt}</p>
          {/if}
          {#if assertion.source_citations?.length}
            <p class="hj-section-label">References named by Seshat</p>
            <ul>
              {#each assertion.source_citations as citation}
                <li>{citation}</li>
              {/each}
            </ul>
          {/if}
          <ul>
            {#each assertion.source_refs as source}
              <li><a class="hj-link" href={source.url} target="_blank" rel="noreferrer">{source.citation}</a> · {source.license_id}</li>
            {/each}
          </ul>
        </details>
      </article>
    {/each}
  </section>
{/if}

<style>
  .object { margin: 0; color: var(--text); font-family: var(--font-display); font-size: var(--t-base); line-height: var(--lh-snug); }
  .explanation { margin: var(--s-2) 0 0; color: var(--text-dim); font-size: var(--t-sm); line-height: var(--lh-body); }
  .generated-note { margin: var(--s-2) 0 0; color: var(--text-faint); font-size: var(--t-xs); line-height: var(--lh-body); }
  .hj-entry:first-of-type { border-top: 0; padding-top: 0; }
</style>
