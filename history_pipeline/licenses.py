from __future__ import annotations

from history_pipeline.config import LicensePolicy


class LicenseRejectedError(ValueError):
    pass


RIGHTS_URI_LICENSES = {
    "http://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
    "http://creativecommons.org/publicdomain/mark/1.0/": "PDM-1.0",
    "https://creativecommons.org/publicdomain/mark/1.0/": "PDM-1.0",
    "http://creativecommons.org/licenses/by/3.0/": "CC-BY-3.0",
    "https://creativecommons.org/licenses/by/3.0/": "CC-BY-3.0",
    "http://creativecommons.org/licenses/by/4.0/": "CC-BY-4.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC-BY-4.0",
    "http://creativecommons.org/licenses/by-sa/4.0/": "CC-BY-SA-4.0",
    "https://creativecommons.org/licenses/by-sa/4.0/": "CC-BY-SA-4.0",
    "http://creativecommons.org/licenses/by-nc/4.0/": "CC-BY-NC-4.0",
    "https://creativecommons.org/licenses/by-nc/4.0/": "CC-BY-NC-4.0",
    "http://opendatacommons.org/licenses/by/1.0/": "ODC-By-1.0",
    "https://opendatacommons.org/licenses/by/1.0/": "ODC-By-1.0",
}


def license_id_from_rights_uri(rights_uri: str | None, source_id: str) -> str:
    if not rights_uri:
        raise LicenseRejectedError(f"{source_id}: item has no explicit rights URI")
    license_id = RIGHTS_URI_LICENSES.get(rights_uri)
    if license_id is None:
        raise LicenseRejectedError(
            f"{source_id}: unsupported or incompatible rights URI {rights_uri}"
        )
    return license_id


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
