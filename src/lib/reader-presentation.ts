import type {
  EntityReadingEligibility,
  FeatureContentLink,
  HistoricalDossier,
  HistoricalEntity
} from '$lib/content-contracts';

export function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function geometryStatement(meaning: string): string {
  const statements: Record<string, string> = {
    territorial_control: 'A source reconstruction of territorial control. Authority may have varied within this area.',
    legal_boundary: 'A boundary documented as a legal or surveyed line for its stated date.',
    claim: 'A claimed extent, which may not represent effective control.',
    territorial_claim: 'A claimed extent from a stated perspective, which may not represent effective control.',
    occupation: 'An area represented as under occupation for this interval.',
    tributary_relationship: 'A tributary relationship, not uniform territorial administration.',
    cultural_region: 'A cultural region with a deliberately soft edge, not a state border.',
    influence_zone: 'An approximate zone of influence rather than exclusive control.',
    location: 'A location or representative point, not an asserted territorial extent.',
    route: 'A route reconstructed from the cited source.',
    mobility_range: 'A mobile range with variable use and deliberately soft edges.',
    seasonal_use: 'A seasonal-use area, not permanent or exclusive control.',
    network: 'A network of relationships and movement, not a bounded territory.',
    ohm_contributor_detail: 'Contributor-built historical detail from OpenHistoricalMap. Its dates and geometry are shown separately from the reviewed reconstruction.',
    unknown_extent: 'An approximate extent whose precise spatial meaning is not known.',
    unknown: 'The release does not yet describe what this geometry represents.'
  };
  return statements[meaning] ?? statements.unknown;
}

/**
 * Name the restatement tier without overstating it. A restatement is one source retold, so the
 * label credits the source and says plainly that the wording is ours.
 */
export function restatementLabel(dossier: HistoricalDossier): string {
  if (dossier.source_ref.source_id === 'wikipedia') {
    return `Plain English · restated from ${dossier.language.toUpperCase()} Wikipedia`;
  }
  return `Plain English · restated from ${dossier.source_ref.publisher}`;
}

export function dossierLabel(dossier: HistoricalDossier): string {
  if (dossier.content_role === 'primary_source') return 'Primary source transcription';
  if (dossier.content_role === 'project_interpretation') return 'Palimpsest interpretation';
  if (dossier.source_ref.source_id === 'wikipedia') {
    return `From ${dossier.language.toUpperCase()} Wikipedia`;
  }
  return `Tertiary summary · ${dossier.source_ref.publisher}`;
}

export function primaryReadingEligibility(
  link: FeatureContentLink | null,
  entity: HistoricalEntity | null,
  validFrom: number,
  validTo: number,
  sourceId?: string,
  featureKind?: string
): EntityReadingEligibility | null {
  if (!entity) return null;
  const published = link?.reading_eligibility?.find(
    (candidate) => candidate.entity_id === entity.entity_id
  );
  if (published) return published;

  let identityRelation: EntityReadingEligibility['identity_relation'] =
    sourceId?.toLowerCase() === 'pleiades' ? 'place_continuity' : 'exact_match';
  const expectedKinds: Record<string, string[]> = {
    polity: ['polity'],
    settlement: ['place'],
    archaeological_site: ['place'],
    route: ['route'],
    event: ['event'],
    archival_map: ['artifact']
  };
  const expected = featureKind ? expectedKinds[featureKind] : undefined;
  if (
    identityRelation === 'exact_match' &&
    expected &&
    entity.entity_kind &&
    !expected.includes(entity.entity_kind)
  ) {
    identityRelation = 'broader_topic';
  }
  let temporalOverlap: EntityReadingEligibility['temporal_overlap'];
  let reasonCodes: string[];
  if (entity.valid_to != null && entity.valid_to < validFrom) {
    temporalOverlap = 'none';
    reasonCodes = ['entity_interval_ends_before_feature'];
  } else if (entity.valid_from != null && entity.valid_from > validTo) {
    temporalOverlap = 'none';
    reasonCodes = ['entity_interval_starts_after_feature'];
  } else if (entity.valid_from == null || entity.valid_to == null) {
    temporalOverlap = 'unknown';
    reasonCodes = ['entity_interval_unbounded'];
  } else {
    temporalOverlap = 'overlaps';
    reasonCodes = ['feature_entity_intervals_overlap'];
  }
  if (identityRelation === 'place_continuity') {
    reasonCodes.push('place_continuity_requires_review');
  } else if (identityRelation === 'broader_topic') {
    reasonCodes.push('entity_kind_incompatible_with_feature');
  }
  return {
    entity_id: entity.entity_id,
    identity_basis: 'source_asserted',
    identity_relation: identityRelation,
    temporal_overlap: temporalOverlap,
    reading_eligible: temporalOverlap === 'overlaps' && identityRelation === 'exact_match',
    reason_codes: reasonCodes
  };
}
