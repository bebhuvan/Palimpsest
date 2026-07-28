<script lang="ts">
  import { proseSegments } from '$lib/year-data';
  import type { YearProseLink } from '$lib/year-contracts';

  let {
    prose,
    links = [],
    tone = 'body'
  }: {
    prose: string;
    links?: YearProseLink[];
    /** 'lede' sets the opening statement; 'body' is running prose. */
    tone?: 'lede' | 'body';
  } = $props();

  const segments = $derived(proseSegments(prose, links));
</script>

<p class={tone}>
  {#each segments as segment}
    {#if segment.href}
      <a href={segment.href} title={segment.title} target="_blank" rel="noreferrer">{segment.text}</a>
    {:else}{segment.text}{/if}
  {/each}
</p>

<style>
  p { margin: 0 0 var(--s-4); font-family: var(--font-display); }
  p:last-child { margin-bottom: 0; }
  .body { color: var(--text-dim); font-size: var(--t-base); line-height: var(--lh-body); }
  .lede { color: var(--text); font-size: var(--t-lg); line-height: 1.44; letter-spacing: -0.008em; }

  a {
    color: inherit;
    text-decoration: underline;
    text-decoration-color: var(--accent-line);
    text-decoration-thickness: 1px;
    text-underline-offset: 3px;
  }
  a:hover { color: var(--accent); text-decoration-color: var(--accent); }
</style>
