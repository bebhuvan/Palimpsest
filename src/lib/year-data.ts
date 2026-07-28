import { artifact, loadJsonArtifact } from '$lib/release-data';
import type { LoadedRelease } from '$lib/release-contracts';
import type { YearDossier, YearIndex, YearIndexEntry, YearProseLink } from '$lib/year-contracts';

export const YEAR_INDEX_PATH = 'years/index.json';

/**
 * Every year this release carries, or null when it carries none.
 *
 * A release without year pages is complete, not degraded, so an absent index is a normal
 * answer rather than an error. It is one small fetch, and it must happen before the
 * interface offers a year anywhere.
 */
export async function loadYearIndex(release: LoadedRelease): Promise<YearIndex | null> {
  const path = release.manifest.year_index_path ?? YEAR_INDEX_PATH;
  if (!artifact(release, path)) return null;
  try {
    return await loadJsonArtifact<YearIndex>(release, path);
  } catch {
    return null;
  }
}

export function yearEntry(index: YearIndex | null, year: number): YearIndexEntry | undefined {
  return index?.years.find((entry) => entry.year === year);
}

/** Addressed by the year itself: the reader already has that integer, so there is no shard lookup. */
export async function loadYearDossier(
  release: LoadedRelease,
  index: YearIndex | null,
  year: number
): Promise<YearDossier | null> {
  const entry = yearEntry(index, year);
  if (!entry) return null;
  return loadJsonArtifact<YearDossier>(release, entry.path);
}

export interface ProseSegment {
  text: string;
  href?: string;
  title?: string;
}

/**
 * Turn prose plus its character offsets into renderable segments.
 *
 * The offsets were verified against this exact string at build time, so they are sliced
 * rather than re-matched: re-tokenising or re-flowing the prose first would invalidate
 * them silently. If a link's recorded `text` does not equal the slice, the contract says
 * to render the prose unlinked rather than guess, so one bad offset degrades that
 * paragraph to plain text instead of corrupting it.
 */
export function proseSegments(prose: string, links: YearProseLink[] = []): ProseSegment[] {
  if (!prose) return [];
  const ordered = [...links]
    .filter((link) => Number.isInteger(link.start) && Number.isInteger(link.end) && link.end > link.start)
    .sort((left, right) => left.start - right.start);

  for (const link of ordered) {
    if (prose.slice(link.start, link.end) !== link.text) return [{ text: prose }];
  }

  const segments: ProseSegment[] = [];
  let cursor = 0;
  for (const link of ordered) {
    // Overlapping spans cannot both be honoured; skipping is safer than nesting them.
    if (link.start < cursor) continue;
    if (link.start > cursor) segments.push({ text: prose.slice(cursor, link.start) });
    segments.push({ text: link.text, href: link.url, title: link.title });
    cursor = link.end;
  }
  if (cursor < prose.length) segments.push({ text: prose.slice(cursor) });
  return segments;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export function monthName(month: number): string {
  return MONTHS[month - 1] ?? 'Undated';
}

/**
 * A year in `related_years` is only reachable if the release actually carries it. The
 * contract forbids fetching a year page to discover whether it exists, so availability is
 * answered from the index alone and an absent year renders as plain text.
 */
export function availableYears(index: YearIndex | null): Set<number> {
  return new Set(index?.years.map((entry) => entry.year) ?? []);
}
