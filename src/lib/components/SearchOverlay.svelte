<script lang="ts">
  import { displayNameForYear, type SearchRecord } from '$lib/data';
  import { formatRange } from '$lib/history';
  import { humanize } from '$lib/reader-presentation';

  let {
    open = $bindable(),
    query = $bindable(),
    results,
    selectedYear,
    onQueryChange,
    onResultSelect
  }: {
    open: boolean;
    query: string;
    results: SearchRecord[];
    selectedYear: number;
    onQueryChange: () => void | Promise<void>;
    onResultSelect: (record: SearchRecord) => void;
  } = $props();

  let input = $state<HTMLInputElement | undefined>();
  let activeIndex = $state(-1);

  export function focusSearch(): void {
    open = true;
    queueMicrotask(() => input?.select());
  }

  function close(): void {
    open = false;
    activeIndex = -1;
  }

  function updateQuery(): void {
    activeIndex = -1;
    void onQueryChange();
  }

  function selectResult(record: SearchRecord): void {
    close();
    onResultSelect(record);
  }

  function handleKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' && results.length) {
      event.preventDefault();
      activeIndex = (activeIndex + 1) % results.length;
    } else if (event.key === 'ArrowUp' && results.length) {
      event.preventDefault();
      activeIndex = (activeIndex - 1 + results.length) % results.length;
    } else if (event.key === 'Enter' && results.length) {
      event.preventDefault();
      selectResult(results[Math.max(0, activeIndex)]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
    }
  }

  $effect(() => {
    if (open) queueMicrotask(() => input?.focus());
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="scrim" onclick={close}></div>

  <div class="palette" role="dialog" aria-modal="true" aria-label="Search historical places">
    <div class="field">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.6" /><path d="m15.8 15.8 4.9 4.9" /></svg>
      <input
        bind:this={input}
        type="search"
        role="combobox"
        bind:value={query}
        oninput={updateQuery}
        onkeydown={handleKey}
        placeholder="Find a historical place or polity"
        aria-label="Search historical places and alternate names"
        aria-autocomplete="list"
        aria-controls="place-results"
        aria-activedescendant={activeIndex >= 0 ? `place-result-${activeIndex}` : undefined}
        aria-expanded={query.trim().length >= 2}
      />
      <button class="dismiss" onclick={close} aria-label="Close search">Esc</button>
    </div>

    {#if query.trim().length >= 2}
      <div class="results" id="place-results" role="listbox" aria-label="Historical place results">
        {#if results.length}
          {#each results as result, index (result.entity_id)}
            <button
              id={`place-result-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              class:active={index === activeIndex}
              onmouseenter={() => (activeIndex = index)}
              onclick={() => selectResult(result)}
            >
              <span class="name">{displayNameForYear(result, selectedYear)}</span>
              <span class="kind">{humanize(result.kind)}</span>
              <time class="hj-numeral">{formatRange(result.valid_from, result.valid_to)}</time>
            </button>
          {/each}
        {:else}
          <p class="empty">No matching record in this release. A gap in this index is not evidence that nothing existed.</p>
        {/if}
      </div>
    {:else}
      <p class="hint">Search reviewed names and the alternate names attested for them. Type at least two characters.</p>
    {/if}
  </div>
{/if}

<style>
  .scrim { position: fixed; z-index: 30; inset: 0; background: rgb(20 23 42 / 0.34); }

  .palette {
    position: fixed;
    z-index: 31;
    top: 12vh;
    left: 50%;
    width: min(620px, calc(100vw - 32px));
    transform: translateX(-50%);
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: 0 32px 80px rgb(20 23 42 / 0.10);
  }

  .field { display: flex; align-items: center; gap: var(--s-3); padding: var(--s-4) var(--s-4) var(--s-4) var(--s-5); border-bottom: 1px solid var(--line); }
  .field svg { flex: none; width: 18px; height: 18px; fill: none; stroke: var(--text-faint); stroke-width: 1.5; stroke-linecap: round; }
  .field input {
    min-width: 0;
    flex: 1;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text);
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-weight: 400;
  }
  .field input::placeholder { color: var(--text-faint); }
  .field input::-webkit-search-cancel-button { display: none; }
  .dismiss {
    flex: none;
    padding: 4px 8px;
    border: 1px solid var(--line-strong);
    background: transparent;
    color: var(--text-faint);
    cursor: pointer;
    font-size: var(--t-xs);
  }
  .dismiss:hover { border-color: var(--text-faint); color: var(--text); }

  .results { max-height: min(52vh, 460px); overflow-y: auto; }
  .results button {
    width: 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: baseline;
    gap: 2px var(--s-5);
    padding: var(--s-3) var(--s-5);
    border: 0;
    border-bottom: 1px solid var(--hover);
    background: transparent;
    color: var(--text);
    cursor: pointer;
    text-align: left;
  }
  .results button:hover, .results button.active { background: var(--hover); }
  .name { grid-area: 1 / 1; overflow: hidden; font-family: var(--font-display); font-size: var(--t-md); text-overflow: ellipsis; white-space: nowrap; }
  .kind { grid-area: 2 / 1; color: var(--text-faint); font-size: var(--t-xs); }
  .results time { grid-area: 1 / 2 / span 2; align-self: center; color: var(--text-dim); font-size: var(--t-xs); white-space: nowrap; }

  .empty, .hint { margin: 0; padding: var(--s-5); color: var(--text-faint); font-size: var(--t-sm); line-height: var(--lh-body); }

  @media (max-width: 860px) {
    .palette { top: 0; width: 100vw; }
    .field { padding: var(--s-3) var(--s-3) var(--s-3) var(--s-4); }
    .field input { font-size: var(--t-md); }
    .results button { padding-inline: var(--s-4); }
  }
</style>
