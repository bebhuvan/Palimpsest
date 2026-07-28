<script lang="ts">
  let {
    name,
    kindLabel,
    alternateNames,
    onClose
  }: {
    name: string;
    kindLabel: string;
    alternateNames: string[];
    onClose: () => void;
  } = $props();
</script>

<header class="record-header">
  <div>
    <p class="hj-section-label">{kindLabel}</p>
    <h1 id="record-title">{name}</h1>
    {#if alternateNames.length}
      <p class="alternate">Also {alternateNames.slice(0, 3).join(' · ')}</p>
    {/if}
  </div>
  <button class="close" onclick={onClose} aria-label={`Close ${name}`}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6.6 6.6 10.8 10.8M17.4 6.6 6.6 17.4" /></svg>
  </button>
</header>

<style>
  .record-header {
    flex: none;
    display: flex;
    justify-content: space-between;
    gap: var(--s-4);
    padding: var(--s-6) var(--s-6) var(--s-5);
    border-bottom: 1px solid var(--line);
  }

  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--t-2xl);
    font-weight: 400;
    line-height: 1.04;
    letter-spacing: -0.022em;
    text-wrap: balance;
  }

  .alternate { margin: var(--s-3) 0 0; color: var(--text-faint); font-size: var(--t-xs); line-height: 1.5; }

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
    transition: border-color 0.18s var(--ease), color 0.18s var(--ease), background 0.18s var(--ease);
  }
  .close svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.4; stroke-linecap: round; }
  .close:hover { border-color: var(--accent); background: var(--accent); color: #fff; }

  @media (max-width: 860px) {
    .record-header { padding: var(--s-4); }
    h1 { font-size: var(--t-xl); }
  }
</style>
