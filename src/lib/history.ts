export const MINIMUM_YEAR = -3400;
export const MAXIMUM_YEAR = 2026;
export const TIMELINE_MAX = 1000;

export type Era = 'ancient' | 'medieval' | 'early-modern' | 'modern';

export interface TimelineBand {
  era: Era;
  from: number;
  to: number;
  label: string;
}

// These are archive boundaries, not claims about universal historical periods.
export const TIMELINE_BANDS: TimelineBand[] = [
  { era: 'ancient', from: -3400, to: 499, label: 'Before 500 CE' },
  { era: 'medieval', from: 500, to: 1499, label: '500–1499' },
  { era: 'early-modern', from: 1500, to: 1799, label: '1500–1799' },
  { era: 'modern', from: 1800, to: 2026, label: '1800–now' }
];

export function eraForYear(year: number): Era {
  if (year < 500) return 'ancient';
  if (year < 1500) return 'medieval';
  if (year < 1800) return 'early-modern';
  return 'modern';
}

export function eraLabel(era: Era): string {
  return {
    ancient: 'Archive · before 500 CE',
    medieval: 'Archive · 500–1499',
    'early-modern': 'Archive · 1500–1799',
    modern: 'Archive · 1800–present'
  }[era];
}

export function formatYear(year: number): string {
  if (year < 0) return `${Math.abs(year).toLocaleString('en')} BCE`;
  return `${year.toLocaleString('en')} CE`;
}

export function normalizeYear(
  candidate: number,
  previous = 1,
  minimumYear = MINIMUM_YEAR,
  maximumYear = MAXIMUM_YEAR
): number {
  const rounded = Math.round(candidate);
  if (rounded === 0) return previous < 0 ? 1 : -1;
  return Math.max(minimumYear, Math.min(maximumYear, rounded));
}

export function stepYear(
  year: number,
  amount: number,
  minimumYear = MINIMUM_YEAR,
  maximumYear = MAXIMUM_YEAR
): number {
  let next = year + amount;
  if (year < 0 && next >= 0) next += 1;
  if (year > 0 && next <= 0) next -= 1;
  return normalizeYear(next, year, minimumYear, maximumYear);
}

export function formatRange(from: number, to: number): string {
  return from === to ? formatYear(from) : `${formatYear(from)} – ${formatYear(to)}`;
}

function chronologyOrdinal(year: number): number {
  return year > 0 ? year - 1 : year;
}

function yearFromOrdinal(ordinal: number): number {
  const rounded = Math.round(ordinal);
  return rounded >= 0 ? rounded + 1 : rounded;
}

export function scaleForYear(year: number): number {
  const normalized = normalizeYear(year);
  const index = TIMELINE_BANDS.findIndex((band) => normalized >= band.from && normalized <= band.to);
  const safeIndex = Math.max(0, index);
  const band = TIMELINE_BANDS[safeIndex];
  const start = chronologyOrdinal(band.from);
  const end = chronologyOrdinal(band.to);
  const progress = (chronologyOrdinal(normalized) - start) / (end - start);
  return Math.round((safeIndex + progress) * (TIMELINE_MAX / TIMELINE_BANDS.length));
}

export function yearForScale(scale: number): number {
  const clamped = Math.max(0, Math.min(TIMELINE_MAX, scale));
  const bandSize = TIMELINE_MAX / TIMELINE_BANDS.length;
  const index = Math.min(TIMELINE_BANDS.length - 1, Math.floor(clamped / bandSize));
  const band = TIMELINE_BANDS[index];
  const progress = (clamped - index * bandSize) / bandSize;
  const ordinal = chronologyOrdinal(band.from) + progress * (chronologyOrdinal(band.to) - chronologyOrdinal(band.from));
  return normalizeYear(yearFromOrdinal(ordinal));
}

export function parseYearInput(value: string, era: 'BCE' | 'CE', previous: number): number | null {
  const amount = Number(value.replaceAll(',', '').trim());
  if (!Number.isFinite(amount) || amount < 1) return null;
  return normalizeYear(era === 'BCE' ? -amount : amount, previous);
}
