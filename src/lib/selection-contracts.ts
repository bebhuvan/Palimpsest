import type { HistoricalNameAttestation } from '$lib/search-records';
import type { SourceReference } from '$lib/release-contracts';

export interface MapSelection {
  sourceRole: 'reviewed' | 'ohm';
  featureId: string;
  entityId?: string;
  name: string;
  kind: string;
  validFrom: number;
  validTo: number;
  spatialMeaning: string;
  temporalConfidence: string;
  spatialConfidence: string;
  interpretiveConfidence: string;
  reviewStatus: string;
  wikidataId?: string;
  disputeGroup?: string;
  contentShard?: string;
  sourceId?: string;
  sourceReference?: SourceReference;
  yearDossierYears?: number[];
  nameAttestation?: HistoricalNameAttestation;
  dateLabel?: string;
  longitude?: number;
  latitude?: number;
  ohm?: {
    sourceLayer: string;
    elementId?: string;
    startDate?: string;
    endDate?: string;
    source?: string;
    sourceRef?: string;
    license?: string;
    copyright?: string;
    attribution?: string;
    changeset?: string;
    datesComplete: boolean;
  };
}
