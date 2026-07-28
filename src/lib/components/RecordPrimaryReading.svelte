<script lang="ts">
  import RecordRestatement from '$lib/components/RecordRestatement.svelte';
  import type {
    DossierRestatement,
    FeatureContentLink,
    HistoricalDossier,
    HistoricalEntity
  } from '$lib/data';
  import { gradeInk } from '$lib/density';
  import { formatYear } from '$lib/history';
  import { OHM_COPYRIGHT_URL } from '$lib/ohm';
  import {
    dossierLabel,
    geometryStatement,
    humanize,
    primaryReadingEligibility
  } from '$lib/reader-presentation';
  import type { MapSelection } from '$lib/selection-contracts';

  let {
    selection,
    selectedYear,
    entity,
    dossiers,
    restatements,
    link,
    loading,
    error
  }: {
    selection: MapSelection;
    selectedYear: number;
    entity: HistoricalEntity | null;
    dossiers: HistoricalDossier[];
    restatements: Map<string, DossierRestatement>;
    link: FeatureContentLink | null;
    loading: boolean;
    error: string;
  } = $props();

  const eligibility = $derived(
    primaryReadingEligibility(
      link,
      entity,
      selection.validFrom,
      selection.validTo,
      selection.sourceId,
      selection.kind
    )
  );
  const readingEligible = $derived(eligibility?.reading_eligible === true);
  const eligibleEntityIds = $derived(
    new Set(
      link?.reading_eligibility?.filter((decision) => decision.reading_eligible)
        .map((decision) => decision.entity_id) ??
        (readingEligible && entity ? [entity.entity_id] : [])
    )
  );
  const eligibleDossiers = $derived(
    dossiers.filter((dossier) =>
      (dossier.entity_ids ?? []).some((entityId) => eligibleEntityIds.has(entityId))
    )
  );
  const hasEligibleDescription = $derived(
    Boolean(readingEligible && entity && Object.values(entity.descriptions).length)
  );
</script>

{#if selection.sourceRole === 'ohm'}
  <section class="hj-section" aria-label="OpenHistoricalMap record provenance">
    <p class="hj-section-label">Live contributor detail</p>
    <p class="hj-note">This contributor record is shown as historical context. It has not been merged with, or reviewed as, the Palimpsest reconstruction.</p>
    <dl>
      <div><dt>Vector layer</dt><dd>{selection.ohm?.sourceLayer}</dd></div>
      {#if selection.ohm?.elementId}<div><dt>OHM/OSM ID</dt><dd class="hj-mono">{selection.ohm.elementId}</dd></div>{/if}
      <div><dt>Date metadata</dt><dd>{selection.ohm?.datesComplete ? 'Start and end supplied' : 'Incomplete or undated'}</dd></div>
      {#if selection.ohm?.source}<div><dt>Source tag</dt><dd>{selection.ohm.source}</dd></div>{/if}
      {#if selection.ohm?.sourceRef}<div><dt>Source reference</dt><dd>{selection.ohm.sourceRef}</dd></div>{/if}
      {#if selection.ohm?.license}<div><dt>Licence override</dt><dd>{selection.ohm.license}</dd></div>{/if}
      {#if selection.ohm?.changeset}<div><dt>Changeset</dt><dd class="hj-mono">{selection.ohm.changeset}</dd></div>{/if}
    </dl>
    <p class="hj-caveat">The live tile does not always expose complete element provenance or per-feature licence tags. A future curated snapshot must retain and validate those fields before publication.</p>
    <a class="hj-link" href={OHM_COPYRIGHT_URL} target="_blank" rel="noreferrer">OpenHistoricalMap copyright and attribution <span aria-hidden="true">↗</span></a>
  </section>
{:else if loading}
  <div class="loading" aria-live="polite"><span></span>Checking this release for linked reading material…</div>
{:else if error}
  <p class="error" role="alert">{error}</p>
{:else}
  {#if hasEligibleDescription && entity}
    <section class="hj-section" aria-labelledby="wikidata-heading">
      <p class="hj-section-label" id="wikidata-heading">At this date</p>
      <p class="hj-lede">{entity.descriptions.en ?? Object.values(entity.descriptions)[0]}</p>
      {#if entity.links.wikidata}
        <p class="follow"><a class="hj-link" href={entity.links.wikidata} target="_blank" rel="noreferrer">Open the Wikidata item <span aria-hidden="true">↗</span></a></p>
      {/if}
    </section>
  {/if}

  {#if readingEligible}
    {#each eligibleDossiers as dossier (dossier.dossier_id)}
      {@const restatement = restatements.get(dossier.dossier_id)}
      {#if restatement}
        <RecordRestatement {restatement} {dossier} {selectedYear} />
      {:else}
        <section class="hj-section extract" aria-labelledby={`dossier-${dossier.page_id}`}>
          <p class="hj-section-label" id={`dossier-${dossier.page_id}`}>{dossierLabel(dossier)}</p>
          <h2>{dossier.title}</h2>
          {#each dossier.extract.trim().split('\n').filter(Boolean) as paragraph}
            <p class="hj-prose">{paragraph}</p>
          {/each}
          <footer>
            <span>{dossier.source_ref.citation} · {dossier.source_ref.license_id}</span>
            <a class="hj-link" href={dossier.url} target="_blank" rel="noreferrer">Read at source <span aria-hidden="true">↗</span></a>
            {#if dossier.revision_id}
              <small>Revision {dossier.revision_id}{dossier.revision_timestamp ? ` · ${new Date(dossier.revision_timestamp).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}</small>
            {/if}
          </footer>
        </section>
      {/if}
    {/each}
    {#if !hasEligibleDescription && !eligibleDossiers.length}
      <section class="hj-section" aria-label="No eligible narrative reading">
        <p class="hj-section-label">Coverage at this date</p>
        <p class="hj-lede">This release has sourced facts for the record, but no narrative passage is linked to an eligible historical identity at {formatYear(selectedYear)}.</p>
      </section>
    {/if}
  {:else if entity}
    <section class="hj-section coverage" aria-label="Linked reading not eligible">
      {#if eligibility?.identity_relation === 'broader_topic' && eligibility.temporal_overlap === 'overlaps' && Object.values(entity.descriptions).length}
        <p class="hj-section-label">Related historical context</p>
        <p class="hj-lede"><strong>{entity.names.en ?? Object.values(entity.names)[0]}</strong> — {entity.descriptions.en ?? Object.values(entity.descriptions)[0]}</p>
        <p class="hj-caveat">The source links this broader topic to the map record. It is context for {formatYear(selectedYear)}, not the identity of {selection.name}.</p>
        {#if entity.links.wikidata}
          <p class="follow"><a class="hj-link" href={entity.links.wikidata} target="_blank" rel="noreferrer">Open the related Wikidata item <span aria-hidden="true">↗</span></a></p>
        {/if}
      {:else if eligibility?.temporal_overlap === 'none'}
        <p class="hj-section-label">Coverage at this date</p>
        <p class="hj-lede">The linked source describes a different historical interval, so its prose is not presented as a reading for {formatYear(selectedYear)}.</p>
      {:else if eligibility?.identity_relation === 'place_continuity'}
        <p class="hj-section-label">Coverage at this date</p>
        <p class="hj-lede">The linked place may continue into a later settlement, but this release has not verified that the modern article describes this place in {formatYear(selectedYear)}.</p>
      {:else if eligibility?.identity_relation === 'broader_topic'}
        <p class="hj-section-label">Coverage at this date</p>
        <p class="hj-lede">The linked source covers a broader historical topic, not this mapped record itself, so its prose is not presented as the history of {selection.name}.</p>
      {:else}
        <p class="hj-section-label">Coverage at this date</p>
        <p class="hj-lede">The linked source has no bounded dates that establish its prose as a reading for {formatYear(selectedYear)}.</p>
      {/if}
      {#if dossiers.length}
        <details class="hj-disclosure">
          <summary>Linked source records</summary>
          <ul>
            {#each dossiers as dossier (dossier.dossier_id)}
              <li><a class="hj-link" href={dossier.url} target="_blank" rel="noreferrer">{dossier.title} <span aria-hidden="true">↗</span></a></li>
            {/each}
          </ul>
        </details>
      {/if}
    </section>
  {/if}

  {#if !dossiers.length && !entity}
    <section class="hj-section" aria-label="Reading material unavailable">
      <p class="hj-section-label">Reading dossier</p>
      <p class="hj-lede">This release maps the record but publishes no dossier linked to this exact feature. Nothing has been inferred or filled in.</p>
      {#if link?.missing_entity_ids.length}
        <p class="hj-caveat">The feature-to-entity join is published, but metadata for {link.missing_entity_ids.join(', ')} was not enriched in this build.</p>
      {/if}
      {#if selection.wikidataId}
        <p class="follow"><a class="hj-link" href={`https://www.wikidata.org/wiki/${selection.wikidataId}`} target="_blank" rel="noreferrer">Open {selection.wikidataId} on Wikidata <span aria-hidden="true">↗</span></a></p>
      {/if}
    </section>
  {/if}
{/if}

{#if selection.sourceRole === 'reviewed'}
  <details class="record-apparatus">
    <summary>About this map record</summary>
    <section class="apparatus-section" aria-labelledby="geometry-title">
      <p class="hj-section-label" id="geometry-title">What the shape means</p>
      <p class="hj-note">{geometryStatement(selection.spatialMeaning)}</p>
    </section>
    {#if selection.nameAttestation}
      <section class="apparatus-section" aria-label="Historical name attestation">
        <p class="hj-section-label">Name at this date</p>
        <p class="hj-note"><strong>{selection.nameAttestation.text}</strong> is the sourced label active in {formatYear(selectedYear)}.</p>
        <p class="hj-meta">
          <span class="hj-grade" style={`--grade: ${gradeInk(selection.nameAttestation.temporal_confidence)}`}>Confidence {selection.nameAttestation.temporal_confidence}</span>
          · {selection.nameAttestation.language} · {humanize(selection.nameAttestation.name_kind)}
          · {selection.nameAttestation.temporal_basis === 'attested' ? 'independently dated name' : 'date inherited from this feature interval'}
        </p>
      </section>
    {/if}
  </details>
{/if}

<style>
  dl { margin: var(--s-4) 0; border-top: 1px solid var(--line); }
  dl div { display: grid; grid-template-columns: 108px 1fr; gap: var(--s-3); padding: var(--s-2) 0; border-bottom: 1px solid var(--line); }
  dt { color: var(--text-faint); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
  dd { margin: 0; overflow-wrap: anywhere; color: var(--text-dim); font-size: var(--t-sm); line-height: 1.5; }

  .extract h2 {
    margin: 0 0 var(--s-3);
    font-family: var(--font-display);
    font-size: var(--t-xl);
    font-weight: 500;
    line-height: var(--lh-tight);
    letter-spacing: -0.016em;
  }
  .extract footer {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--s-2) var(--s-4);
    margin-top: var(--s-4);
    padding-top: var(--s-3);
    border-top: 1px solid var(--line);
    color: var(--text-faint);
    font-size: var(--t-xs);
    line-height: 1.5;
  }
  .extract footer a { text-align: right; }
  .extract footer small { grid-column: 1 / -1; }

  .follow { margin: var(--s-4) 0 0; }
  .record-apparatus { border-bottom: 1px solid var(--line); padding: var(--s-4) var(--s-6); }
  .record-apparatus > summary { cursor: pointer; color: var(--text-dim); font-size: var(--t-sm); font-weight: 600; }
  .apparatus-section { margin-top: var(--s-4); padding-top: var(--s-4); border-top: 1px solid var(--line); }
  .apparatus-section:first-of-type { border-top: 0; }
  .apparatus-section p:last-child { margin-bottom: 0; }

  .loading, .error { margin: 0; padding: var(--s-5) var(--s-6); border-bottom: 1px solid var(--line); color: var(--text-dim); font-size: var(--t-sm); line-height: var(--lh-body); }
  .loading { display: flex; align-items: center; gap: var(--s-3); }
  .loading span { width: 12px; height: 12px; flex: none; border: 1px solid var(--line-strong); border-top-color: var(--text); border-radius: 50%; animation: spin 0.8s linear infinite; }
  .error { color: var(--conf-d); }

  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 860px) {
    .loading, .error { padding: var(--s-4); }
    .record-apparatus { padding: var(--s-4); }
  }
</style>
