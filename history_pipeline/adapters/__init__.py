from history_pipeline.adapters.cliopatria import CliopatriaAdapter
from history_pipeline.adapters.curated import CuratedSourceAdapter
from history_pipeline.adapters.geojson import GeoJsonAdapter
from history_pipeline.adapters.iiif_maps import IiifMapAdapter
from history_pipeline.adapters.linked_places import LinkedPlacesAdapter
from history_pipeline.adapters.open_context import OpenContextAdapter
from history_pipeline.adapters.owid import OwidAdapter
from history_pipeline.adapters.periodo import PeriodoAdapter
from history_pipeline.adapters.pleiades import PleiadesAdapter
from history_pipeline.adapters.reconciliation import AuthorityReconciliationAdapter

__all__ = [
    "AuthorityReconciliationAdapter",
    "CliopatriaAdapter",
    "CuratedSourceAdapter",
    "GeoJsonAdapter",
    "IiifMapAdapter",
    "LinkedPlacesAdapter",
    "OpenContextAdapter",
    "OwidAdapter",
    "PeriodoAdapter",
    "PleiadesAdapter",
]
