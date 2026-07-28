/**
 * Year page contracts, mirroring the published `years/` artifacts.
 *
 * Two things in here are load-bearing and easy to get wrong:
 *
 *   `lede_kind` distinguishes a lede nobody wrote from one a model did, so the reader's
 *   warning can be accurate rather than uniform.
 *
 *   Every `links` / `gloss_links` array holds character offsets into its sibling prose
 *   string. They were verified against that exact string at build time.
 */

export interface YearProseLink {
  start: number;
  end: number;
  text: string;
  title: string;
  url: string;
}

export interface YearImage {
  commons_file: string;
  descriptor_url: string;
  image_url: string;
  attribution: string;
  license_id: string;
  license_short_name?: string | null;
  rights_uri?: string | null;
  mime_type?: string | null;
  caption?: string | null;
  subject_title?: string | null;
  subject_wikidata_id?: string | null;
  width?: number | null;
  height?: number | null;
}

export interface YearHeadline {
  entry_id: string;
  date_text: string | null;
  text: string;
  subject_title: string | null;
  subject_url: string | null;
  sitelink_count: number;
}

export interface YearRegisterEntry {
  entry_id: string;
  kind: 'birth' | 'death' | 'event' | 'incumbent';
  /** The record as the source carries it. This is the content; the rest is apparatus. */
  text: string;
  topic?: string | null;
  subject_wikidata_id?: string | null;
  month: number | null;
  day: number | null;
  date_text: string | null;
  subject_title: string | null;
  subject_url: string | null;
  qualifier: string | null;
  gloss: string | null;
  gloss_links: YearProseLink[];
  image: YearImage | null;
  lens: string | null;
  prominent: boolean;
  related_year: number | null;
  sitelink_count: number;
  also_recorded_as: string[];
  source_pages: string[];
}

export interface YearWork {
  entry_id: string;
  kind: string;
  title: string;
  creator: string | null;
  subject_title: string | null;
  subject_url: string | null;
  gloss: string | null;
  gloss_links: YearProseLink[];
  image: YearImage | null;
  sitelink_count: number;
  source_page: string | null;
}

export interface YearAnchor {
  anchor_id: string;
  heading: string;
  date_text: string | null;
  lens: string | null;
  prose: string;
  links: YearProseLink[];
  image: YearImage | null;
  entry_ids: string[];
  quote?: string | null;
  records?: YearHeadline[];
}

export interface YearSection {
  section_id: string;
  heading: string;
  lens: string | null;
  prose: string;
  links: YearProseLink[];
  entry_ids: string[];
}

export interface YearOverview {
  prose: string;
  links: YearProseLink[];
  months: number[];
  event_count: number;
  birth_count: number;
  death_count: number;
  dated_count: number;
  undated_count: number;
  entry_ids: string[];
  themes?: string[];
  source_pages?: string[];
}

export interface YearIncumbent {
  entry_id: string;
  office: string;
  holder: string;
  place: string | null;
}

export interface YearConflict {
  title: string;
  url: string;
  wikidata_id: string | null;
  start_year: number | null;
  end_year: number | null;
  began_this_year: boolean;
  ended_this_year: boolean;
  sitelink_count: number;
}

export interface YearConnection {
  entry_id: string;
  kind: string;
  text: string;
  subject_title: string | null;
  subject_url: string | null;
}

export interface YearRelated {
  year: number;
  direction: 'earlier' | 'later';
  connections: YearConnection[];
}

export interface YearSourceRef {
  source_id: string;
  title: string;
  citation: string;
  url: string;
  publisher: string;
  license_id: string;
  retrieved_at?: string;
  checksum_sha256?: string;
  modified?: boolean;
}

export interface YearGeneration {
  model_identifier: string;
  generated_at: string;
  prompt_version: string;
  prompt_sha256?: string;
  output_sha256?: string;
  source_sha256?: string;
  provider_response_id?: string;
}

export interface YearDossier {
  schema_version: string;
  dossier_id: string;
  year: number;
  language: string;
  editorial_state: string;
  chronicle_id: string;
  chronicle_revision_id: number;
  lede: string;
  lede_kind: 'assembled' | 'generated';
  lede_links: YearProseLink[];
  headlines: YearHeadline[];
  overview: YearOverview;
  anchors: YearAnchor[];
  sections: YearSection[];
  register_entries: YearRegisterEntry[];
  works: YearWork[];
  incumbents: YearIncumbent[];
  conflicts: YearConflict[];
  related_years: YearRelated[];
  source_refs: YearSourceRef[];
  generation: YearGeneration;
  removed_sentences: string[];
}

export interface YearIndexEntry {
  year: number;
  dossier_id: string;
  path: string;
  language: string;
  chronicle_revision_id: number;
  record_count: number;
  anchor_count: number;
  image_count: number;
  headline: string;
  related_years: number[];
}

export interface YearIndex {
  schema_version: string;
  path_template: string;
  years: YearIndexEntry[];
}

/**
 * The disclosure wording is fixed by the frontend contract. It applies to machine-written
 * prose only — never to the assembled parts, which nobody generated.
 */
export const MACHINE_PROSE_DISCLOSURE =
  'This dossier was written by a machine and has not been read by a person. Every name and ' +
  'date in the prose appears in the records it was written from — checked, not trusted. The ' +
  'connections are ours.';
