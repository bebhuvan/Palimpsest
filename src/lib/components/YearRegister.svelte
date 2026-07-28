<script lang="ts">
  import YearProse from '$lib/components/YearProse.svelte';
  import { monthName } from '$lib/year-data';
  import type { YearRegisterEntry } from '$lib/year-contracts';

  let { entries }: { entries: YearRegisterEntry[] } = $props();

  const KIND_LABEL: Record<string, string> = {
    event: 'Event',
    birth: 'Born',
    death: 'Died',
    incumbent: 'In office'
  };

  // Grouped by the month the sources dated it to, with everything undated held back rather
  // than guessed into a month it might not belong to.
  const grouped = $derived(
    (() => {
      const months = new Map<number, YearRegisterEntry[]>();
      const undated: YearRegisterEntry[] = [];
      for (const entry of entries) {
        if (entry.month === null) undated.push(entry);
        else months.set(entry.month, [...(months.get(entry.month) ?? []), entry]);
      }
      const ordered = [...months.entries()]
        .sort(([left], [right]) => left - right)
        .map(([month, items]) => ({
          key: String(month),
          label: monthName(month),
          items: items.sort((left, right) => (left.day ?? 0) - (right.day ?? 0))
        }));
      if (undated.length) ordered.push({ key: 'undated', label: 'Undated in the sources', items: undated });
      return ordered;
    })()
  );
</script>

<div class="register">
  {#each grouped as group (group.key)}
    <section class="month" aria-labelledby={`month-${group.key}`}>
      <h3 id={`month-${group.key}`}>
        <span>{group.label}</span>
        <small class="hj-numeral">{group.items.length}</small>
      </h3>

      <ul>
        {#each group.items as entry (entry.entry_id)}
          <li class:prominent={entry.prominent}>
            <span class="when hj-numeral">{entry.date_text ?? '—'}</span>
            <div class="what">
              <!-- The record verbatim. This is the thing the register exists to carry. -->
              <p class="record">{entry.text}</p>

              <p class="meta">
                <span class="kind">{KIND_LABEL[entry.kind] ?? entry.kind}</span>
                {#if entry.subject_url}
                  <a href={entry.subject_url} target="_blank" rel="noreferrer">{entry.subject_title}</a>
                {:else if entry.subject_title}
                  <span>{entry.subject_title}</span>
                {/if}
                {#if entry.qualifier}<span class="qualifier">{entry.qualifier}</span>{/if}
                {#if entry.also_recorded_as.length}
                  <span class="qualifier">also recorded as {entry.also_recorded_as.join(' · ')}</span>
                {/if}
              </p>

              {#if entry.gloss}
                <div class="gloss">
                  <span class="machine-tag">Machine-written</span>
                  <YearProse prose={entry.gloss} links={entry.gloss_links} tone="body" />
                </div>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    </section>
  {/each}
</div>

<style>
  .register { display: grid; gap: var(--s-8); }

  h3 {
    display: grid;
    grid-template-columns: 108px minmax(0, 1fr);
    align-items: baseline;
    gap: var(--s-5);
    margin: 0 0 var(--s-3);
    padding-bottom: var(--s-3);
    border-bottom: 1px solid var(--text);
  }
  h3 span { font-family: var(--font-display); font-size: var(--t-lg); font-weight: 400; letter-spacing: -0.015em; }
  h3 small { color: var(--text-faint); font-size: var(--t-xs); font-weight: 500; }

  /* One column at a readable size. Two columns of 13px halved the height and turned the
     archive into a grey slab; a register you cannot comfortably read is not a register. */
  ul { margin: 0; padding: 0; list-style: none; }
  li {
    display: grid;
    grid-template-columns: 108px minmax(0, 1fr);
    gap: var(--s-5);
    padding: var(--s-3) 0;
    border-bottom: 1px solid var(--line);
  }
  li:last-child { border-bottom: 0; }
  .when {
    color: var(--text-faint);
    font-size: var(--t-xs);
    font-weight: 500;
    line-height: 1.85;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }
  .what { min-width: 0; max-width: 62ch; }

  .record {
    margin: 0;
    color: var(--text);
    font-family: var(--font-display);
    font-size: var(--t-md);
    line-height: 1.62;
  }
  .prominent .record { font-size: var(--t-lg); }

  .meta { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s-2); margin: var(--s-1) 0 0; }
  .kind { color: var(--text-faint); font-size: 10px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; }
  .meta a { color: var(--text-dim); font-size: var(--t-xs); text-decoration: underline; text-decoration-color: var(--accent-line); text-underline-offset: 3px; }
  .meta a:hover { color: var(--accent); text-decoration-color: var(--accent); }
  .meta > span:not(.kind) { color: var(--text-faint); font-size: var(--t-xs); }
  .qualifier { color: var(--text-faint); font-size: var(--t-xs); }

  /* A gloss is machine-written, so it is set apart from the record it describes. */
  .gloss { margin-top: var(--s-2); padding-left: var(--s-4); border-left: 1px solid var(--line-strong); }
  .machine-tag { display: block; margin-bottom: 2px; color: var(--text-faint); font-size: 10px; font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase; }
  .gloss :global(p) { margin: 0; font-size: var(--t-sm); line-height: 1.6; }

  @media (max-width: 720px) {
    h3, li { grid-template-columns: 1fr; gap: var(--s-1); }
    h3 { gap: 0; }
  }
</style>
