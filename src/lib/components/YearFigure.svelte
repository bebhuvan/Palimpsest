<script lang="ts">
  import type { YearImage } from '$lib/year-contracts';

  let { image, size = 'full' }: { image: YearImage; size?: 'full' | 'thumb' } = $props();
</script>

<!--
  A file is redistributable on the terms attached to it and on no others, so the credit and
  licence are part of the figure rather than a caption that a layout change could drop.
-->
<figure class={size}>
  <img
    src={image.image_url}
    alt={image.caption ?? image.subject_title ?? ''}
    width={image.width ?? undefined}
    height={image.height ?? undefined}
    loading="lazy"
  />
  <figcaption>
    {#if image.caption}<span class="caption">{image.caption}</span>{/if}
    <span class="credit">
      {image.attribution}
      · <a href={image.descriptor_url} target="_blank" rel="noreferrer">{image.license_short_name ?? image.license_id}</a>
    </span>
  </figcaption>
</figure>

<style>
  figure { margin: 0; }
  img {
    display: block;
    width: 100%;
    height: auto;
    background: var(--bg-sunk);
    border: 1px solid var(--line);
  }
  .thumb img { aspect-ratio: 1 / 1; object-fit: cover; }

  figcaption { display: grid; gap: 3px; margin-top: var(--s-2); }
  .caption { color: var(--text-dim); font-size: var(--t-xs); line-height: 1.5; }
  .credit { color: var(--text-faint); font-size: 10px; line-height: 1.5; }
  .credit a { color: var(--text-faint); text-underline-offset: 2px; }
  .credit a:hover { color: var(--accent); }
</style>
