export type HistoricalLens = 'all' | 'power' | 'belief' | 'knowledge' | 'culture' | 'trade';

export interface HistoricalLensDefinition {
  id: HistoricalLens;
  shortLabel: string;
  label: string;
  description: string;
  marker: string;
  accent: string;
}

/**
 * Lenses are non-ordinal categories, so they are distinguished by mark rather than
 * hue. Colour in this product is reserved for the confidence ramp, and only one
 * lens is ever active at a time, so a single highlight ink is sufficient on the map
 * and keeps the theme layer legible for colour-blind readers.
 */
export const LENS_HIGHLIGHT = '#13232b';

export const HISTORICAL_LENSES: HistoricalLensDefinition[] = [
  {
    id: 'all',
    shortLabel: 'All',
    label: 'All history',
    description: 'All published records, without forcing them into a single theme.',
    marker: '○',
    accent: LENS_HIGHLIGHT
  },
  {
    id: 'power',
    shortLabel: 'Power',
    label: 'Power & governance',
    description: 'Polities, administration, territorial control, conflict and claims.',
    marker: '◆',
    accent: LENS_HIGHLIGHT
  },
  {
    id: 'belief',
    shortLabel: 'Belief',
    label: 'Belief & ritual',
    description: 'Sourced places and networks of worship, ritual, burial and pilgrimage.',
    marker: '✦',
    accent: LENS_HIGHLIGHT
  },
  {
    id: 'knowledge',
    shortLabel: 'Knowledge',
    label: 'Knowledge & technology',
    description: 'Schools, libraries, observatories and the movement of practical knowledge.',
    marker: '●',
    accent: LENS_HIGHLIGHT
  },
  {
    id: 'culture',
    shortLabel: 'Culture',
    label: 'Culture & society',
    description: 'Sourced cultural regions, arts, monuments, performance and social life.',
    marker: '■',
    accent: LENS_HIGHLIGHT
  },
  {
    id: 'trade',
    shortLabel: 'Trade',
    label: 'Trade & movement',
    description: 'Explicit trade routes, ports, markets, transport and networks of exchange.',
    marker: '↔',
    accent: LENS_HIGHLIGHT
  }
];

export function isHistoricalLens(value: string | null): value is HistoricalLens {
  return HISTORICAL_LENSES.some((lens) => lens.id === value);
}

export function lensDefinition(lens: HistoricalLens): HistoricalLensDefinition {
  return HISTORICAL_LENSES.find((candidate) => candidate.id === lens) ?? HISTORICAL_LENSES[0];
}

/** A tile filter over themes derived from published thematic assertions. */
export function reviewedLensFilter(lens: HistoricalLens): unknown {
  if (lens === 'all') return true;
  return ['in', lens, ['coalesce', ['get', 'themes'], ['literal', []]]];
}

export function recordMatchesLens(
  record: { kind: string; themes?: string[] },
  lens: HistoricalLens
): boolean {
  return lens === 'all' || Boolean(record.themes?.includes(lens));
}
