from __future__ import annotations

from history_pipeline.config import LicensePolicy


class LicenseRejectedError(ValueError):
    pass


def enforce_license(license_id: str | None, policy: LicensePolicy, source_id: str) -> None:
    if not license_id:
        if policy.require_explicit_license:
            raise LicenseRejectedError(f"{source_id}: source has no explicit license")
        return
    if license_id in policy.denied:
        raise LicenseRejectedError(f"{source_id}: {license_id} is explicitly denied")
    if license_id not in policy.allowed:
        raise LicenseRejectedError(
            f"{source_id}: {license_id} is not allowed by the {policy.mode} policy"
        )


def enforce_source_license(
    license_id: str,
    license_reviewed: bool,
    policy: LicensePolicy,
    source_id: str,
) -> None:
    enforce_license(license_id, policy, source_id)
    if not license_reviewed:
        raise LicenseRejectedError(
            f"{source_id}: dataset and downstream licence review is incomplete"
        )
