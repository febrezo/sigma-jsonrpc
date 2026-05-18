from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.engine import SigmaEngine
from app.errors import SigmaEngineException, SigmaInputException


class InputSigmaIndicator(BaseModel):
    type: str
    spec_version: str | None = None
    id: str
    name: str | None = None
    description: str | None = None
    pattern_type: str
    pattern: str
    confidence: int | None = None
    valid_from: str | None = None
    created: str | None = None
    modified: str | None = None
    labels: list[str] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "indicator":
            raise ValueError("only_indicator_object_supported")
        return value

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, value: str) -> str:
        if value != "sigma":
            raise ValueError("pattern_type_must_be_sigma")
        return value

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        stripped = (value or "").strip()
        if not stripped:
            raise ValueError("pattern_required")
        return stripped


class TranslateSigmaBundleRequest(BaseModel):
    indicator: InputSigmaIndicator
    targets: list[str]
    pipelines: dict[str, str] | None = None
    without_pipeline: bool = True
    include_source: bool = True
    upstream_objects: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("target_required")
        return value


@dataclass
class SigmaBundleConversion:
    target: str
    indicator: dict[str, Any]
    relationship: dict[str, Any]
    success: bool
    error: str | None = None


def new_stix_id(object_type: str) -> str:
    return f"{object_type}--{uuid.uuid4()}"


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_input_sigma_indicator_for_bundle(
    indicator: InputSigmaIndicator,
) -> dict[str, Any]:
    now = _now_str()
    obj = {
        "type": "indicator",
        "spec_version": indicator.spec_version or "2.1",
        "id": indicator.id,
        "created": indicator.created or now,
        "modified": indicator.modified or now,
        "name": indicator.name or "",
        "description": indicator.description or "",
        "pattern_type": "sigma",
        "pattern": indicator.pattern,
        "valid_from": indicator.valid_from or now,
        "labels": ["sigma-jsonrpc", "source", "sigma"],
    }
    if indicator.confidence is not None:
        obj["confidence"] = indicator.confidence
    return obj


def format_derived_sigma_indicator_description(
    source_description: str | None,
) -> str:
    base = source_description or "Sigma rule"
    return (
        f"{base}\n\nSTIX Indicator automatically generated from the source Sigma rule."
    )


def evaluate_sigma_bundle_conversions(
    engine: SigmaEngine,
    source_indicator: dict[str, Any],
    targets: list[str],
    pipelines: dict[str, str] | None,
    without_pipeline: bool,
) -> list[SigmaBundleConversion]:
    now = _now_str()
    source_confidence = source_indicator.get("confidence", 70)
    source_name = source_indicator.get("name", "Sigma rule")
    source_description = source_indicator.get("description", "")
    source_id = source_indicator["id"]

    conversions: list[SigmaBundleConversion] = []
    for target in targets:
        pipeline = (pipelines or {}).get(target)
        effective_without_pipeline = without_pipeline if pipeline is None else False
        try:
            result = engine.convert_rule(
                rule_text=source_indicator["pattern"],
                target=target,
                pipeline=pipeline,
                without_pipeline=effective_without_pipeline,
            )
        except (SigmaInputException, SigmaEngineException) as exc:
            conversions.append(
                SigmaBundleConversion(
                    target=target,
                    indicator={},
                    relationship={},
                    success=False,
                    error=str(exc),
                )
            )
            continue

        query = result.get("query", "")
        if not query:
            conversions.append(
                SigmaBundleConversion(
                    target=target,
                    indicator={},
                    relationship={},
                    success=False,
                    error=f"empty conversion result for target '{target}'",
                )
            )
            continue

        derived_id = new_stix_id("indicator")
        derived_name = f"{source_name} [{target}]"
        derived_description = format_derived_sigma_indicator_description(
            source_description
        )
        derived_labels = ["sigma-jsonrpc", "auto-generated", target]
        derived_indicator = {
            "type": "indicator",
            "spec_version": "2.1",
            "id": derived_id,
            "created": now,
            "modified": now,
            "name": derived_name,
            "description": derived_description,
            "pattern_type": target,
            "pattern": query,
            "valid_from": now,
            "confidence": source_confidence,
            "labels": derived_labels,
            "x_sigma_jsonrpc_target": target,
            "x_sigma_jsonrpc_pipeline": pipeline,
            "x_sigma_jsonrpc_without_pipeline": effective_without_pipeline,
            "x_sigma_jsonrpc_source_indicator": source_id,
            "x_sigma_jsonrpc_engine": "sigma-cli",
        }

        relationship_id = new_stix_id("relationship")
        relationship = {
            "type": "relationship",
            "spec_version": "2.1",
            "id": relationship_id,
            "created": now,
            "modified": now,
            "relationship_type": "derived-from",
            "source_ref": derived_id,
            "target_ref": source_id,
            "confidence": source_confidence,
        }

        conversions.append(
            SigmaBundleConversion(
                target=target,
                indicator=derived_indicator,
                relationship=relationship,
                success=True,
            )
        )

    return conversions


def build_sigma_translation_bundle(
    source_indicator: dict[str, Any],
    conversions: list[SigmaBundleConversion],
    include_source: bool,
    upstream_objects: list[dict[str, Any]],
) -> dict[str, Any]:
    bundle_id = new_stix_id("bundle")
    objects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if include_source:
        sid = source_indicator["id"]
        seen_ids.add(sid)
        objects.append(source_indicator)

    for upstream in upstream_objects:
        uid = upstream.get("id")
        if uid and uid not in seen_ids:
            seen_ids.add(uid)
            objects.append(upstream)

    successful_conversions = [c for c in conversions if c.success]
    failed_conversions = [c for c in conversions if not c.success]

    for conv in successful_conversions:
        ind = conv.indicator
        iid = ind.get("id")
        if iid and iid not in seen_ids:
            seen_ids.add(iid)
            objects.append(ind)

        rel = conv.relationship
        rid = rel.get("id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            objects.append(rel)

    bundle: dict[str, Any] = {
        "type": "bundle",
        "spec_version": "2.1",
        "id": bundle_id,
        "objects": objects,
    }

    if failed_conversions:
        bundle["x_sigma_jsonrpc_conversion_errors"] = [
            {"target": c.target, "error": c.error} for c in failed_conversions
        ]

    if conversions and not successful_conversions:
        bundle["status"] = "error"
        bundle["comments"] = ["No conversion results for the provided Sigma indicator"]
        bundle["objects"] = []

    return bundle


def translate_sigma_bundle(
    engine: SigmaEngine,
    indicator: InputSigmaIndicator,
    targets: list[str],
    pipelines: dict[str, str] | None = None,
    without_pipeline: bool = True,
    include_source: bool = True,
    upstream_objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_indicator = normalize_input_sigma_indicator_for_bundle(indicator)

    conversions = evaluate_sigma_bundle_conversions(
        engine=engine,
        source_indicator=source_indicator,
        targets=targets,
        pipelines=pipelines,
        without_pipeline=without_pipeline,
    )

    return build_sigma_translation_bundle(
        source_indicator=source_indicator,
        conversions=conversions,
        include_source=include_source,
        upstream_objects=upstream_objects or [],
    )
