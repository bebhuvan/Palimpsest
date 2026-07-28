import {
  loadCausalContext,
  loadChronologyContext,
  loadEvidenceAssertions,
  loadRegionalContext,
  loadThemeAssertions,
  loadWikiContext,
  type CausalClaim,
  type CausalPath,
  type EvidenceAssertion,
  type HistoricalPeriodDefinition,
  type LoadedRelease,
  type SelectedRegionalContext,
  type SelectedWikiContext,
  type ThematicAssertion
} from '$lib/data';
import type { MapSelection } from '$lib/selection-contracts';

export interface SelectionSupplement {
  causalClaims: CausalClaim[];
  causalPaths: CausalPath[];
  periods: HistoricalPeriodDefinition[];
  wikiContext: SelectedWikiContext | null;
  regionalContext: SelectedRegionalContext | null;
  thematicAssertions: ThematicAssertion[];
  evidenceAssertions: EvidenceAssertion[];
}

function regionalContext(
  release: LoadedRelease,
  selection: MapSelection,
  year: number
): Promise<SelectedRegionalContext | null> {
  if (selection.longitude === undefined || selection.latitude === undefined) {
    return Promise.resolve(null);
  }
  return loadRegionalContext(
    release,
    selection.longitude,
    selection.latitude,
    year,
    selection.featureId
  );
}

export async function loadSelectionSupplement(
  release: LoadedRelease,
  selection: MapSelection,
  entityIds: string[],
  year: number
): Promise<SelectionSupplement> {
  const [
    causal,
    periods,
    wikiContext,
    selectedRegionalContext,
    thematicAssertions,
    evidenceAssertions
  ] = await Promise.all([
    loadCausalContext(release, entityIds),
    loadChronologyContext(release, entityIds, year),
    loadWikiContext(release, selection.featureId, year),
    regionalContext(release, selection, year),
    loadThemeAssertions(release, selection.featureId),
    loadEvidenceAssertions(release, selection.featureId)
  ]);

  return {
    causalClaims: causal.claims,
    causalPaths: causal.paths,
    periods,
    wikiContext,
    regionalContext: selectedRegionalContext,
    thematicAssertions,
    evidenceAssertions
  };
}
