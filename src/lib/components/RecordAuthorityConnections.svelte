<script lang="ts">
  import type { AuthorityMatch } from '$lib/data';
  import { humanize } from '$lib/reader-presentation';

  let { matches }: { matches: AuthorityMatch[] } = $props();
</script>

{#if matches.length}
  <section class="hj-section" aria-labelledby="authority-connections-title">
    <p class="hj-section-label" id="authority-connections-title">Authority connections</p>
    <p class="hj-note">
      Editors linked this record to external place authorities. These links identify records;
      they do not replace the map's reviewed dates or geometry.
    </p>
    <ul>
      {#each matches as match (match.match_id)}
        <li>
          <a href={match.source_ref.url} target="_blank" rel="noreferrer">
            <strong>{match.label}</strong>
            <span>{match.authority_namespace.toUpperCase()} · {match.authority_id}</span>
          </a>
          <p>
            {humanize(match.relation)} · reviewed · {match.rights.attribution}
            · {match.rights.license_id}
          </p>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  ul { display: grid; gap: var(--s-3); margin: var(--s-4) 0 0; padding: 0; list-style: none; }
  li { padding: var(--s-3); border: 1px solid var(--line); background: var(--surface); }
  a { display: grid; gap: 3px; color: inherit; text-decoration: none; overflow-wrap: anywhere; }
  a:hover strong { text-decoration: underline; text-underline-offset: 3px; }
  strong { font-family: var(--font-display); font-size: var(--t-md); font-weight: 500; }
  a span, li p { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.5; }
  li p { margin: var(--s-2) 0 0; }
</style>
