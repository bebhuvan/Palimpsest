import type { CoverageCell } from '$lib/release-contracts';
import { TIMELINE_MAX, yearForScale } from '$lib/history';

export const DENSITY_BUCKETS = 96;

export interface DensityBucket {
  /** Position on the timeline scale, 0…TIMELINE_MAX. */
  scale: number;
  /** The year sampled at the centre of this bucket. */
  year: number;
  /** Observed features active in that year across every coverage cell. */
  count: number;
  /** Share of the tallest bucket, 0…1. */
  height: number;
  /** The confidence grade contributing the most observations at this year. */
  grade: string;
}

export interface DensityProfile {
  buckets: DensityBucket[];
  peak: number;
}

/**
 * How much this release actually knows, plotted across the timeline.
 *
 * The archive's coverage is genuinely uneven — it thins to almost nothing before
 * roughly 1100 BCE — and the previous four equal-width "archive bands" hid that
 * behind a flat gradient, to the point where the About dialog had to apologise for
 * them in prose. Sampling the release's own coverage cells lets the scrubber state
 * the same fact without a disclaimer.
 *
 * Each bucket is sampled at a single year rather than over a span. Coverage cells
 * are coarsely binned in time, so summing everything that *overlaps* a span double
 * counts wherever two bins meet and produces spikes that mean nothing.
 */
export function densityProfile(coverage: CoverageCell[]): DensityProfile {
  if (!coverage.length) return { buckets: [], peak: 0 };

  const buckets: DensityBucket[] = [];
  let peak = 0;

  for (let index = 0; index < DENSITY_BUCKETS; index += 1) {
    const scale = ((index + 0.5) * TIMELINE_MAX) / DENSITY_BUCKETS;
    const year = yearForScale(scale);
    let count = 0;
    const grades = new Map<string, number>();

    for (const cell of coverage) {
      if (cell.valid_from > year || cell.valid_to < year) continue;
      count += cell.feature_count;
      for (const [grade, amount] of Object.entries(cell.confidence_counts ?? {})) {
        grades.set(grade, (grades.get(grade) ?? 0) + amount);
      }
    }

    let grade = 'unknown';
    let best = 0;
    for (const [candidate, amount] of grades) {
      if (amount > best) {
        best = amount;
        grade = candidate;
      }
    }

    peak = Math.max(peak, count);
    buckets.push({ scale, year, count, height: 0, grade });
  }

  if (peak > 0) {
    for (const bucket of buckets) {
      // Square-root scaling. A linear axis would flatten the ancient world into an
      // invisible sliver and read as "no data" rather than "little data".
      bucket.height = Math.sqrt(bucket.count / peak);
    }
  }

  return { buckets, peak };
}

/** Chart and swatch fills: brighter, so a ribbon of them reads on white. */
export function gradeColour(grade: string): string {
  const key = grade.toUpperCase();
  if (key === 'A') return 'var(--conf-a-fill)';
  if (key === 'B') return 'var(--conf-b-fill)';
  if (key === 'C') return 'var(--conf-c-fill)';
  if (key === 'D') return 'var(--conf-d-fill)';
  return 'var(--conf-unknown-fill)';
}

/** Type and rules: darker, so a grade letter stays legible as text. */
export function gradeInk(grade: string): string {
  const key = grade.toUpperCase();
  if (key === 'A') return 'var(--conf-a)';
  if (key === 'B') return 'var(--conf-b)';
  if (key === 'C') return 'var(--conf-c)';
  if (key === 'D') return 'var(--conf-d)';
  return 'var(--conf-unknown)';
}

export function gradeMeaning(grade: string): string {
  return (
    {
      A: 'High documentary precision',
      B: 'Specialist reconstruction',
      C: 'Approximate atlas reconstruction',
      D: 'Location or influence only'
    }[grade.toUpperCase()] ?? 'Not yet assessed'
  );
}
