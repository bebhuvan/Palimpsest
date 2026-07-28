<script lang="ts">
  import type {
    CausalClaim,
    CausalPath,
    HistoricalEntity,
    HistoricalPeriodDefinition,
    SelectedWikiContext
  } from '$lib/data';
  import { gradeInk } from '$lib/density';
  import { formatRange, formatYear } from '$lib/history';
  import { humanize } from '$lib/reader-presentation';

  let {
    wikiContext,
    periods,
    causalClaims,
    causalPaths,
    selectedYear
  }: {
    wikiContext: SelectedWikiContext | null;
    periods: HistoricalPeriodDefinition[];
    causalClaims: CausalClaim[];
    causalPaths: CausalPath[];
    selectedYear: number;
  } = $props();

  function periodLabel(period: HistoricalPeriodDefinition): string {
    return period.labels.en?.[0] ?? Object.values(period.labels)[0]?.[0] ?? period.period_id;
  }

  function causalSummary(claim: CausalClaim): string {
    return claim.mechanism_summary.en ?? Object.values(claim.mechanism_summary)[0] ?? claim.mechanism_type;
  }

  function contextName(entity: HistoricalEntity): string {
    return entity.names.en ?? Object.values(entity.names)[0] ?? entity.entity_id;
  }

  function contextDescription(entity: HistoricalEntity): string {
    return (
      entity.descriptions.en ??
      Object.values(entity.descriptions)[0] ??
      'No short description is published in this release.'
    );
  }
</script>

{#if wikiContext?.items.length}
  <section class="hj-section" aria-labelledby="wiki-context-title">
    <p class="hj-section-label" id="wiki-context-title">Historical context near this record</p>
    <p class="hj-caveat">A bounded, date-aware selection of explicit Wikidata relationships. A connection is not a claim of causation.</p>
    {#each wikiContext.items as item (item.context_entity_id)}
      <article class="hj-entry">
        <p class="hj-meta">{humanize(item.role)} · {item.relationship_types.map(humanize).join(' · ')}</p>
        <strong>{contextName(item.entity)}</strong>
        <p class="hj-note">{contextDescription(item.entity)}</p>
        <p class="hj-meta">
          {#if item.valid_from !== null || item.valid_to !== null}{formatRange(item.valid_from ?? item.valid_to ?? selectedYear, item.valid_to ?? item.valid_from ?? selectedYear)} · {/if}
          {item.source_strength === 'referenced_statement' ? 'Wikidata statement with retained reference' : 'Wikidata statement; no reference returned'}
        </p>
        {#if item.dossiers[0]}
          <details class="hj-disclosure">
            <summary>Read the saved Wikipedia introduction</summary>
            <p class="hj-prose">{item.dossiers[0].extract}</p>
            <a class="hj-link" href={item.dossiers[0].url} target="_blank" rel="noreferrer">{item.dossiers[0].title} · revision {item.dossiers[0].revision_id ?? 'recorded in release'} <span aria-hidden="true">↗</span></a>
          </details>
        {:else if item.entity.sitelinks?.en}
          <a class="hj-link" href={item.entity.sitelinks.en.url} target="_blank" rel="noreferrer">Open the linked Wikipedia page <span aria-hidden="true">↗</span></a>
        {/if}
      </article>
    {/each}
    {#if wikiContext.total_items > wikiContext.items.length}
      <p class="hj-meta trailing">{wikiContext.total_items - wikiContext.items.length} lower-ranked connections stay in the release shard, collapsed in this first reading view.</p>
    {/if}
  </section>
{/if}

{#if periods.length}
  <section class="hj-section" aria-labelledby="chronology-title">
    <p class="hj-section-label" id="chronology-title">Named periods in use here</p>
    <p class="hj-caveat">Attributed scholarly definitions that overlap at {formatYear(selectedYear)}. They are not one universal timeline.</p>
    {#each periods.slice(0, 12) as period (period.period_id)}
      <article class="hj-entry">
        <p class="hj-meta">{period.start_label} – {period.stop_label}</p>
        <strong>{periodLabel(period)}</strong>
        <p class="hj-meta">{period.spatial_coverage_description ?? period.spatial_coverage.map((place) => place.label).join(', ')}</p>
        <a class="hj-link" href={period.source_ref.url} target="_blank" rel="noreferrer">{period.authority_citation} <span aria-hidden="true">↗</span></a>
      </article>
    {/each}
    {#if periods.length > 12}
      <p class="hj-meta trailing">{periods.length - 12} further overlapping definitions are in this release; the reading view starts with the most specific twelve.</p>
    {/if}
  </section>
{/if}

{#if causalClaims.length || causalPaths.length}
  <section class="hj-section" aria-labelledby="causal-title">
    <p class="hj-section-label" id="causal-title">Interpretive pathways</p>
    <p class="hj-caveat">Attributed historical arguments, not automatic facts or a single authoritative chain.</p>
    {#each causalPaths as path (path.path_id)}
      <article class="hj-entry">
        <p class="hj-meta">Curated pathway · {humanize(path.review_status)}</p>
        <strong>{path.titles.en ?? Object.values(path.titles)[0]}</strong>
        <p class="hj-note">{path.summaries.en ?? Object.values(path.summaries)[0]}</p>
        <p class="hj-meta">{path.perspective} · {path.claim_ids.length} linked claims</p>
      </article>
    {/each}
    {#each causalClaims as claim (claim.claim_id)}
      <article class="hj-entry">
        <p class="hj-meta">{humanize(claim.relationship)} · {humanize(claim.mechanism_type)}</p>
        <p class="claim">{causalSummary(claim)}</p>
        <p class="hj-meta">{formatRange(claim.cause_period.valid_from, claim.cause_period.valid_to)} → {formatRange(claim.effect_period.valid_from, claim.effect_period.valid_to)}</p>
        <p class="hj-meta">
          <span class="hj-grade" style={`--grade: ${gradeInk(claim.confidence.grade)}`}>Confidence {claim.confidence.grade}</span>
          · {claim.perspective} · {claim.source_refs.length} source{claim.source_refs.length === 1 ? '' : 's'}
        </p>
        <details class="hj-disclosure">
          <summary>Evidence and authorship</summary>
          <p class="hj-note">{claim.confidence.rationale}</p>
          <p class="hj-note">Authored by {claim.authored_by}{claim.reviewed_by.length ? ` · reviewed by ${claim.reviewed_by.join(', ')}` : ''}</p>
          <ul>
            {#each claim.source_refs as source}
              <li><a class="hj-link" href={source.url} target="_blank" rel="noreferrer">{source.citation}</a></li>
            {/each}
          </ul>
        </details>
      </article>
    {/each}
  </section>
{/if}

<style>
  .claim { margin: 0; color: var(--text); font-family: var(--font-display); font-size: var(--t-base); line-height: var(--lh-body); }
  .trailing { margin-top: var(--s-4); }
  .hj-entry:first-of-type { border-top: 0; padding-top: 0; }
</style>
