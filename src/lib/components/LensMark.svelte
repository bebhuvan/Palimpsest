<script lang="ts">
  import type { HistoricalLens } from '$lib/lenses';

  let { lens, size = 15 }: { lens: HistoricalLens; size?: number } = $props();
</script>

<!--
  Drawn marks rather than the unicode glyphs the data carries. ○ ◆ ✦ ● ■ ↔ come from
  different type designs and land at wildly different optical weights, so a row of them
  reads as fallback characters. These are six distinct silhouettes — ring, diamond, star,
  triangle, square, arrow — balanced against each other by area, and they stay legible at
  15px where hue would not, which is the whole reason lenses are told apart by form.
-->
<svg
  class="mark"
  viewBox="0 0 16 16"
  width={size}
  height={size}
  aria-hidden="true"
  focusable="false"
>
  {#if lens === 'all'}
    <circle cx="8" cy="8" r="5.1" fill="none" stroke="currentColor" stroke-width="1.7" />
  {:else if lens === 'power'}
    <path d="M8 2.1 13.9 8 8 13.9 2.1 8Z" fill="currentColor" />
  {:else if lens === 'belief'}
    <path d="M8 1.2 9.55 6.45 14.8 8 9.55 9.55 8 14.8 6.45 9.55 1.2 8 6.45 6.45Z" fill="currentColor" />
  {:else if lens === 'knowledge'}
    <path d="M8 2.4 14.1 13.1H1.9Z" fill="currentColor" />
  {:else if lens === 'culture'}
    <rect x="3.3" y="3.3" width="9.4" height="9.4" fill="currentColor" />
  {:else}
    <path
      d="M2.2 8h11.6M5 5.2 2.2 8 5 10.8M11 5.2 13.8 8 11 10.8"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  {/if}
</svg>

<style>
  .mark { display: block; flex: none; }
</style>
