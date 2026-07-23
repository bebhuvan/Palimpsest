from __future__ import annotations

import pytest

from history_pipeline.config import LicensePolicy
from history_pipeline.licenses import (
    LicenseRejectedError,
    enforce_license,
    enforce_source_license,
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
