from __future__ import annotations

from pathlib import Path

from history_pipeline.models import HistoricalFeature
from history_pipeline.tiles import build_pmtiles


def test_tile_builder_emits_valid_pmtiles_and_keeps_string_id_as_property(
    tmp_path: Path, historical_feature: HistoricalFeature
) -> None:
    executable = tmp_path / "tippecanoe"
    executable.write_text(
        """#!/bin/sh
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ]; then
    shift
    printf 'PMTiles\\003payload' > "$1"
    exit 0
  fi
  shift
done
exit 1
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    artifacts = build_pmtiles(
        [historical_feature],
        tmp_path / "output",
        tmp_path / "work",
        str(executable),
    )

    assert artifacts[0].path == "tiles/ancient.pmtiles"
    sequence = (tmp_path / "work" / "ancient.geojsonseq").read_text()
    assert '\"feature_id\":\"test-source:polity:-100:100:abcdef\"' in sequence
    assert '\"primary_entity_id\":\"wikidata:Q1\"' in sequence
    assert '\"source_record_id\":\"record-1\"' in sequence
    assert '\"source_title\":\"Test source\"' in sequence
    assert '\"source_url\":\"https://example.org/record-1\"' in sequence
    assert '\"content_shard\":' in sequence
    assert '\"themes\":[\"power\"]' in sequence
    assert '\"tippecanoe\":{\"minzoom\":0}' in sequence
    assert '\"id\":\"test-source:polity:-100:100:abcdef\"' not in sequence

    labels = (tmp_path / "work" / "ancient-labels.geojsonseq").read_text()
    assert '\"name\":\"Example polity\"' in labels
    assert '\"temporal_basis\":\"feature_interval\"' in labels
    assert '\"source_id\":\"test-source\"' in labels
    assert '\"themes\":[\"power\"]' in labels
    assert '\"geometry\":{\"type\":\"Point\"' in labels
