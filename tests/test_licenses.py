from __future__ import annotations

import pytest
from pydantic import ValidationError

from history_pipeline.config import LicensePolicy, SourceConfig
from history_pipeline.licenses import (
    LicenseRejectedError,
    enforce_license,
    enforce_source_license,
    license_id_from_rights_uri,
)


def test_license_allowlist_accepts_configured_license() -> None:
    policy = LicensePolicy(allowed=["CC-BY-4.0"])
    enforce_license("CC-BY-4.0", policy, "source")


def test_license_allowlist_rejects_unknown_license() -> None:
    policy = LicensePolicy(allowed=["CC-BY-4.0"])
    with pytest.raises(LicenseRejectedError, match="not allowed"):
        enforce_license("LicenseRef-Unknown", policy, "source")


def test_license_allowlist_rejects_missing_license() -> None:
    policy = LicensePolicy(allowed=["CC-BY-4.0"], require_explicit_license=True)
    with pytest.raises(LicenseRejectedError, match="no explicit license"):
        enforce_license(None, policy, "source")


def test_source_license_requires_completed_review() -> None:
    policy = LicensePolicy(allowed=["CC-BY-4.0"])
    with pytest.raises(LicenseRejectedError, match="review is incomplete"):
        enforce_source_license("CC-BY-4.0", False, policy, "source")


def test_unknown_item_rights_uri_fails_closed() -> None:
    with pytest.raises(LicenseRejectedError, match="unsupported or incompatible"):
        license_id_from_rights_uri(
            "https://rightsstatements.org/vocab/InC/1.0/",
            "iiif-map",
        )


def test_iiif_source_requires_separate_media_and_georeference_rights() -> None:
    with pytest.raises(ValidationError, match="separate metadata, media"):
        SourceConfig.model_validate(
            {
                "id": "iiif-map",
                "adapter": "iiif_maps",
                "title": "Map",
                "publisher": "Archive",
                "url": "https://example.org/manifest",
                "license_id": "CC0-1.0",
                "citation": "Archive",
                "rights": {
                    "metadata": {
                        "license_id": "CC0-1.0",
                        "attribution": "Archive",
                        "review_notes": "Metadata review.",
                    }
                },
            }
        )
