from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

import orjson
from pydantic import HttpUrl, ValidationError

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import source_reference, verify_expected_checksum
from history_pipeline.licenses import (
    enforce_license,
    enforce_source_license,
    license_id_from_rights_uri,
)
from history_pipeline.models import (
    Confidence,
    ConfidenceGrade,
    HistoricalMapMetadata,
    RightsReference,
    RightsScope,
    TransformationStep,
)
from history_pipeline.storage import RawAsset

ADAPTER_VERSION = "1.0.0"


class IiifMapAdapter:
    """Read IIIF Presentation 3 plus a georeference annotation at build time."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        del limit
        source = context.source
        if source.rights is None or source.rights.media is None:
            raise ValueError(f"{source.id}: separate metadata and media rights are required")
        if source.rights.georeference is None:
            raise ValueError(f"{source.id}: georeference rights are required")
        if not source.version or not source.expected_checksum_sha256:
            raise ValueError(f"{source.id}: IIIF manifest version and checksum are required")
        annotation_url = source.options.get("annotation_url")
        annotation_checksum = source.options.get("annotation_checksum_sha256")
        depicted_date = source.options.get("depicted_date")
        if not isinstance(annotation_url, str) or not annotation_url.startswith("https://"):
            raise ValueError(f"{source.id}: annotation_url must be explicit HTTPS")
        if (
            not isinstance(annotation_checksum, str)
            or len(annotation_checksum) != 64
            or any(character not in "0123456789abcdef" for character in annotation_checksum)
        ):
            raise ValueError(f"{source.id}: annotation checksum is required")
        if not isinstance(depicted_date, str) or not depicted_date.strip():
            raise ValueError(f"{source.id}: depicted_date is required")

        enforce_source_license(
            source.rights.metadata.license_id,
            source.license_reviewed,
            context.pipeline.license_policy,
            source.id,
        )
        enforce_license(
            source.rights.georeference.license_id,
            context.pipeline.license_policy,
            source.id,
        )
        manifest_asset = context.downloads.fetch(
            str(source.url),
            context.raw_source_dir / "manifest.json",
        )
        verify_expected_checksum(source, manifest_asset)
        annotation_asset = context.downloads.fetch(
            annotation_url,
            context.raw_source_dir / "georeference-annotation.json",
        )
        if annotation_asset.checksum_sha256 != annotation_checksum:
            raise ValueError(
                f"Source {source.id} annotation checksum changed: expected "
                f"{annotation_checksum}, got {annotation_asset.checksum_sha256}"
            )
        manifest = self._load_object(manifest_asset, "IIIF manifest")
        annotation_document = self._load_object(
            annotation_asset, "georeference annotation"
        )
        self._validate_manifest(source.id, manifest)
        annotations = list(self._annotations(annotation_document))
        if not annotations:
            raise ValueError(f"{source.id}: no georeference annotations found")

        result = AdapterResult(raw_assets=[manifest_asset, annotation_asset])
        for index, annotation in enumerate(annotations):
            record_id = str(annotation.get("id") or index)
            try:
                result.historical_maps.append(
                    self._map_record(
                        context,
                        manifest_asset,
                        annotation_asset,
                        manifest,
                        annotation,
                        depicted_date.strip(),
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, record_id, "normalize", str(error))
                )
        return result

    @staticmethod
    def _load_object(asset: RawAsset, label: str) -> dict[str, Any]:
        with asset.path.open("rb") as handle:
            payload = orjson.loads(handle.read())
        if not isinstance(payload, dict):
            raise ValueError(f"{label} must be a JSON object")
        return payload

    @staticmethod
    def _validate_manifest(source_id: str, manifest: dict[str, Any]) -> None:
        if manifest.get("type") != "Manifest":
            raise ValueError(f"{source_id}: IIIF Presentation 3 Manifest is required")
        if not str(manifest.get("id", "")).startswith("https://"):
            raise ValueError(f"{source_id}: manifest id must be HTTPS")
        if not isinstance(manifest.get("items"), list):
            raise ValueError(f"{source_id}: manifest canvases are missing")
        if not _language_text(manifest.get("label")):
            raise ValueError(f"{source_id}: manifest label is missing")
        if not _providers(manifest):
            raise ValueError(f"{source_id}: manifest provider is missing")
        if not _required_statement(manifest):
            raise ValueError(f"{source_id}: manifest requiredStatement is missing")

    @staticmethod
    def _annotations(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
        if document.get("type") == "Annotation":
            yield document
            return
        if document.get("type") == "AnnotationPage":
            items = document.get("items")
            if not isinstance(items, list):
                raise ValueError("AnnotationPage items are missing")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("AnnotationPage item must be an object")
                yield item
            return
        raise ValueError("Expected an IIIF georeference Annotation or AnnotationPage")

    @staticmethod
    def _map_record(
        context: AdapterContext,
        manifest_asset: RawAsset,
        annotation_asset: RawAsset,
        manifest: dict[str, Any],
        annotation: dict[str, Any],
        depicted_date: str,
    ) -> HistoricalMapMetadata:
        source = context.source
        rights = source.rights
        if rights is None or rights.media is None or rights.georeference is None:
            raise ValueError("scoped source rights are missing")
        if annotation.get("motivation") != "georeferencing":
            raise ValueError("annotation motivation must be georeferencing")
        annotation_id = str(annotation.get("id", ""))
        if not annotation_id.startswith("https://"):
            raise ValueError("annotation id must be HTTPS")
        canvas_id = _target_id(annotation.get("target"))
        canvas = _canvas(manifest, canvas_id)
        body = annotation.get("body")
        if not isinstance(body, dict) or body.get("type") != "FeatureCollection":
            raise ValueError("georeference annotation body must be a FeatureCollection")
        control_points = _validate_control_points(body)
        annotation_rights_uri = annotation.get("rights")
        if annotation_rights_uri:
            annotation_license_id = license_id_from_rights_uri(
                str(annotation_rights_uri), source.id
            )
            if annotation_license_id != rights.georeference.license_id:
                raise ValueError("annotation licence differs from reviewed rights")

        image_rights_uri = _image_rights(canvas, manifest)
        image_license_id = license_id_from_rights_uri(image_rights_uri, source.id)
        if image_rights_uri is None:
            raise ValueError("image rights URI is missing")
        if image_license_id not in rights.media.allowed:
            raise ValueError(
                f"{source.id}: image licence {image_license_id} is not allowed "
                "by the source media policy"
            )
        enforce_license(image_license_id, context.pipeline.license_policy, source.id)

        manifest_id = str(manifest["id"])
        digest = hashlib.sha256(
            f"{manifest_id}\0{canvas_id}\0{annotation_id}".encode()
        ).hexdigest()[:16]
        label = _language_text(canvas.get("label")) or _language_text(manifest["label"])
        required_statement = _required_statement(manifest)
        return HistoricalMapMetadata(
            map_id=f"map:{digest}",
            manifest_id=HttpUrl(manifest_id),
            canvas_id=HttpUrl(canvas_id),
            annotation_id=HttpUrl(annotation_id),
            label=label,
            depicted_date=depicted_date,
            providers=_providers(manifest),
            required_statement=required_statement,
            metadata_rights=RightsReference(
                scope=RightsScope.METADATA,
                license_id=rights.metadata.license_id,
                attribution=rights.metadata.attribution,
                rights_uri=rights.metadata.rights_uri,
            ),
            image_rights=RightsReference(
                scope=RightsScope.MEDIA,
                license_id=image_license_id,
                attribution=required_statement,
                rights_uri=HttpUrl(image_rights_uri),
            ),
            georeference_rights=RightsReference(
                scope=RightsScope.GEOREFERENCE,
                license_id=rights.georeference.license_id,
                attribution=rights.georeference.attribution,
                rights_uri=rights.georeference.rights_uri,
            ),
            georeference_confidence=Confidence(
                grade=ConfidenceGrade.C,
                rationale=(
                    f"Published georeference with {control_points} control points; "
                    "alignment has not been independently verified by History Joice"
                ),
            ),
            known_limitations=list(source.limitations),
            source_refs=[
                source_reference(
                    source,
                    manifest_asset,
                    manifest_id,
                    url=manifest_id,
                    title=f"{source.title}: IIIF manifest",
                ),
                source_reference(
                    source,
                    annotation_asset,
                    annotation_id,
                    url=annotation_id,
                    title=f"{source.title}: georeference annotation",
                ).model_copy(
                    update={"license_id": rights.georeference.license_id}
                ),
            ],
            lineage=[
                TransformationStep(
                    operation="extract_iiif_georeference_metadata",
                    tool="history_pipeline.adapters.iiif_maps",
                    tool_version=ADAPTER_VERSION,
                    input_record_ids=[manifest_id, canvas_id, annotation_id],
                    parameters={
                        "iiif_presentation_version": "3.0",
                        "georeference_extension": "1.0",
                        "control_point_count": control_points,
                        "image_bytes_downloaded": False,
                    },
                )
            ],
        )


def _language_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for language in ("en", "none"):
        items = value.get(language)
        if isinstance(items, list) and items:
            return str(items[0]).strip()
    for items in value.values():
        if isinstance(items, list) and items:
            return str(items[0]).strip()
    return ""


def _providers(manifest: dict[str, Any]) -> list[str]:
    providers: list[str] = []
    for provider in manifest.get("provider") or []:
        if isinstance(provider, dict):
            label = _language_text(provider.get("label"))
            if label:
                providers.append(label)
    return providers


def _required_statement(manifest: dict[str, Any]) -> str:
    statement = manifest.get("requiredStatement")
    if not isinstance(statement, dict):
        return ""
    return _language_text(statement.get("value"))


def _target_id(target: Any) -> str:
    if isinstance(target, str):
        target_id = target
    elif isinstance(target, dict):
        target_id = str(target.get("id") or target.get("source") or "")
        if isinstance(target.get("source"), dict):
            target_id = str(target["source"].get("id") or "")
    else:
        target_id = ""
    if not target_id.startswith("https://"):
        raise ValueError("georeference target must identify an HTTPS canvas")
    return target_id


def _canvas(manifest: dict[str, Any], canvas_id: str) -> dict[str, Any]:
    for canvas in manifest.get("items") or []:
        if isinstance(canvas, dict) and canvas.get("id") == canvas_id:
            return canvas
    raise ValueError("georeference target canvas is absent from the manifest")


def _image_rights(canvas: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    for page in canvas.get("items") or []:
        if not isinstance(page, dict):
            continue
        for annotation in page.get("items") or []:
            if not isinstance(annotation, dict) or annotation.get("motivation") != "painting":
                continue
            body = annotation.get("body")
            if isinstance(body, dict) and body.get("rights"):
                return str(body["rights"])
    rights = canvas.get("rights") or manifest.get("rights")
    return str(rights) if rights else None


def _validate_control_points(body: dict[str, Any]) -> int:
    features = body.get("features")
    if not isinstance(features, list) or len(features) < 3:
        raise ValueError("georeference requires at least three ground control points")
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("ground control point must be an object")
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if (
            not isinstance(geometry, dict)
            or geometry.get("type") != "Point"
            or not isinstance(geometry.get("coordinates"), list)
            or len(geometry["coordinates"]) != 2
            or not isinstance(properties, dict)
            or not isinstance(properties.get("resourceCoords"), list)
            or len(properties["resourceCoords"]) != 2
        ):
            raise ValueError("invalid georeference ground control point")
    return len(features)
