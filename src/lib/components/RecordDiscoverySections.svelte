<script lang="ts">
  import {
    displayNameForYear,
    type HistoricalEntity,
    type RegionTimeEntry,
    type SearchRecord,
    type SelectedRegionalContext
  } from '$lib/data';
  import { formatRange, formatYear } from '$lib/history';
  import { humanize } from '$lib/reader-presentation';

  let {
    relationships,
    linkedEntities,
    searchIndex,
    regionalContext,
    elsewhere,
    selectedYear,
    onRecordSelect
  }: {
    relationships: Array<{
      relation_type: string;
      target_entity_id: string;
      qualifiers?: Array<{ predicate: string; datatype?: string | null; value: unknown }>;
    }>;
    linkedEntities: HistoricalEntity[];
    searchIndex: SearchRecord[];
    regionalContext: SelectedRegionalContext | null;
    elsewhere: SearchRecord[];
    selectedYear: number;
    onRecordSelect: (record: SearchRecord) => void;
  } = $props();

  function regionalRecord(entry: RegionTimeEntry): SearchRecord | undefined {
    return searchIndex.find(
      (record) =>
        record.entity_id === entry.entity_id ||
        Boolean(entry.feature_id && record.feature_ids.includes(entry.feature_id))
    );
  }

  function regionalName(entry: RegionTimeEntry): string {
    const record = regionalRecord(entry);
    if (record) return displayNameForYear(record, selectedYear);
    const entity = regionalContext?.entities.get(entry.entity_id);
    return entity?.names.en ?? Object.values(entity?.names ?? {})[0] ?? entry.entity_id;
  }

  function qualifierYear(value: unknown): number | null {
    if (!value || typeof value !== 'object') return null;
    const time = String((value as { time?: unknown }).time ?? '');
    const match = /^([+-])(\d+)/.exec(time);
    if (!match) return null;
    const year = Number(match[2]);
    return match[1] === '-' ? -year : year;
  }

  function relationshipApplies(
    relationship: {
      qualifiers?: Array<{ predicate: string; datatype?: string | null; value: unknown }>;
    }
  ): boolean {
    const temporal = (relationship.qualifiers ?? []).filter((qualifier) =>
      ['P580', 'P582', 'P585'].includes(qualifier.predicate)
    );
    if (!temporal.length) return true;
    return temporal.every((qualifier) => {
      const year = qualifierYear(qualifier.value);
      if (year == null) return false;
      if (qualifier.predicate === 'P580') return selectedYear >= year;
      if (qualifier.predicate === 'P582') return selectedYear <= year;
      return selectedYear === year;
    });
  }

  const displayableRelationships = $derived(
    relationships.filter(
      (relationship) =>
        relationshipApplies(relationship) &&
        (linkedEntities.some(
          (entity) => entity.entity_id === relationship.target_entity_id
        ) ||
          searchIndex.some(
            (record) =>
              record.entity_id === relationship.target_entity_id ||
              record.entity_id === relationship.target_entity_id.replace('wikidata:', '')
          ))
    )
  );
  const displayableRegionalEntries = $derived(
    (regionalContext?.entries ?? [])
      .filter(
        (entry) =>
          Boolean(regionalRecord(entry)) || regionalContext?.entities.has(entry.entity_id)
      )
      .slice(0, 3)
  );
</script>

{#if displayableRelationships.length}
  <section class="hj-section" aria-labelledby="connections-title">
    <p class="hj-section-label" id="connections-title">Connected records</p>
    {#each displayableRelationships as relationship}
      {@const relatedEntity = linkedEntities.find((entity) => entity.entity_id === relationship.target_entity_id)}
      {@const relatedRecord = searchIndex.find((record) => record.entity_id === relationship.target_entity_id || record.entity_id === relationship.target_entity_id.replace('wikidata:', ''))}
      <article class="hj-entry">
        <p class="hj-meta">{humanize(relationship.relation_type)}</p>
        <strong>{relatedEntity?.names.en ?? Object.values(relatedEntity?.names ?? {})[0] ?? displayNameForYear(relatedRecord!, selectedYear)}</strong>
        <p class="hj-meta">{relationship.qualifiers?.some((qualifier) => ['P580', 'P582', 'P585'].includes(qualifier.predicate)) ? `Applies in ${formatYear(selectedYear)} according to the statement dates.` : 'The source publishes this relationship without a date.'}</p>
        {#if relatedRecord}
          <button class="hj-inline-button" onclick={() => onRecordSelect(relatedRecord)}>Show connected record →</button>
        {/if}
      </article>
    {/each}
  </section>
{/if}

{#if displayableRegionalEntries.length}
  <section class="hj-section" aria-labelledby="regional-context-title">
    <details class="regional-discovery">
      <summary id="regional-context-title">Explore nearby records at {formatYear(selectedYear)}</summary>
      <p class="hj-caveat">Up to three discovery results from a 10° grid cell — not a historical region or evidence of local influence.</p>
      {#each displayableRegionalEntries as entry (entry.entry_id)}
        {@const record = regionalRecord(entry)}
        {@const dossier = entry.dossier_ids.map((id) => regionalContext?.dossiers.get(id)).find(Boolean)}
        <article class="hj-entry">
          <p class="hj-meta">{humanize(entry.kind)} · {entry.spatial_basis === 'feature_geometry_intersection' ? 'reviewed geometry intersects cell' : 'dated Wikidata coordinate'}</p>
          <strong>{regionalName(entry)}</strong>
          <p class="hj-meta">{formatRange(entry.valid_from, entry.valid_to)} · {entry.source_ids.join(', ')}</p>
          {#if record}
            <button class="hj-inline-button" onclick={() => onRecordSelect(record)}>Open mapped record →</button>
          {:else if dossier}
            <a class="hj-link" href={dossier.url} target="_blank" rel="noreferrer">Read saved {dossier.language.toUpperCase()} Wikipedia introduction <span aria-hidden="true">↗</span></a>
          {/if}
        </article>
      {/each}
    </details>
  </section>
{/if}

{#if elsewhere.length}
  <section class="hj-section" aria-labelledby="elsewhere-title">
    <details class="elsewhere-discovery">
      <summary id="elsewhere-title">Explore elsewhere in {formatYear(selectedYear)}</summary>
      <p class="hj-caveat">Optional map jumps sampled from different longitudes. Proximity in this list is not a historical connection.</p>
      <div class="jumps">
        {#each elsewhere as record}
          <button onclick={() => onRecordSelect(record)}>
            <span>{displayNameForYear(record, selectedYear)}</span>
            <small class="hj-numeral">{formatRange(record.valid_from, record.valid_to)}</small>
          </button>
        {/each}
      </div>
    </details>
  </section>
{/if}

<style>
  .hj-entry:first-of-type { border-top: 0; padding-top: 0; }
  .regional-discovery > summary { cursor: pointer; color: var(--text); font-size: var(--t-sm); font-weight: 600; }
  .regional-discovery[open] > summary { margin-bottom: var(--s-3); }
  .elsewhere-discovery > summary { cursor: pointer; color: var(--text); font-size: var(--t-sm); font-weight: 600; }
  .elsewhere-discovery[open] > summary { margin-bottom: var(--s-3); }

  .jumps { border-top: 1px solid var(--line); }
  .jumps button {
    position: relative;
    width: 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: baseline;
    gap: var(--s-4);
    padding: var(--s-3) var(--s-4) var(--s-3) 0;
    border: 0;
    border-bottom: 1px solid var(--line);
    background: transparent;
    color: inherit;
    cursor: pointer;
    text-align: left;
  }
  .jumps button::after {
    content: '→';
    position: absolute;
    right: 0;
    color: var(--text-faint);
    opacity: 0;
    transition: opacity 0.16s var(--ease), transform 0.16s var(--ease);
  }
  .jumps button:hover::after { opacity: 1; transform: translateX(3px); }
  .jumps button span {
    overflow: hidden;
    font-family: var(--font-display);
    font-size: var(--t-md);
    line-height: var(--lh-snug);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .jumps button small { color: var(--text-faint); font-size: var(--t-xs); text-align: right; }
</style>
