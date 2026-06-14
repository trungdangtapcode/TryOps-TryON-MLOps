from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from tryops.contracts import ModelCandidate, PromotionDecision
from tryops.registry import RegistryEntry


TRUE_VALUES = {"1", "true", "yes", "on"}
FINAL_ALIASES = {"candidate", "challenger", "champion"}


def mlflow_enabled() -> bool:
    return os.getenv("TRYOPS_MLFLOW_ENABLED", "0").strip().lower() in TRUE_VALUES


def mlflow_required() -> bool:
    return os.getenv("TRYOPS_MLFLOW_REQUIRED", "0").strip().lower() in TRUE_VALUES


def tracking_uri() -> str:
    return (
        os.getenv("TRYOPS_MLFLOW_TRACKING_URI")
        or os.getenv("MLFLOW_TRACKING_URI")
        or "http://127.0.0.1:15000"
    ).strip()


def public_url() -> str:
    return os.getenv("TRYOPS_MLFLOW_PUBLIC_URL", "http://127.0.0.1:15000").strip().rstrip("/")


def artifact_bucket() -> str:
    return os.getenv("TRYOPS_ARTIFACT_BUCKET", "tryops-artifacts").strip() or "tryops-artifacts"


def log_promotion_to_mlflow(
    *,
    candidate: ModelCandidate,
    decision: PromotionDecision,
    validation_report: dict[str, Any],
    native_policy: dict[str, Any],
    run_context: dict[str, Any],
    registry_entry: RegistryEntry,
    run_dir: Path,
) -> dict[str, Any]:
    """Log promotion evidence to MLflow and create a registry version.

    The MLflow dependency is deliberately imported lazily. Local tests and offline
    promotion samples must continue to produce JSON evidence when the live server
    is not installed or not running.
    """

    if not mlflow_enabled():
        return _status("disabled", "TRYOPS_MLFLOW_ENABLED is disabled")
    try:
        mlflow, client_cls = _import_mlflow()
    except Exception as exc:  # pragma: no cover - environment dependent
        return _unavailable(exc)

    uri = tracking_uri()
    try:
        mlflow.set_tracking_uri(uri)
        experiment_name = f"tryops/{candidate.workload}/promotion"
        client = client_cls(tracking_uri=uri)
        experiment_name = _select_artifact_proxy_experiment(client, experiment_name)
        mlflow.set_experiment(experiment_name)
        model_name = registered_model_name(candidate)
        wrapper_dir = _write_model_wrapper(
            run_dir,
            candidate=candidate,
            decision=decision,
            registry_entry=registry_entry,
        )
        with mlflow.start_run(run_name=f"promotion:{candidate.candidate_id}") as active_run:
            run_info = active_run.info
            run_id = str(run_info.run_id)
            experiment_id = str(run_info.experiment_id)
            mlflow.set_tags(_run_tags(candidate, decision, registry_entry))
            mlflow.log_params(_run_params(candidate, decision, validation_report, run_context))
            for name, value in candidate.metrics.items():
                if isinstance(value, int | float):
                    mlflow.log_metric(name, float(value))
            mlflow.log_metric("data_validation_passed", 1.0 if validation_report.get("passed") else 0.0)
            mlflow.log_metric("promotion_approved", 1.0 if decision.approved else 0.0)
            for path in _promotion_artifact_paths(run_dir):
                if path.exists():
                    mlflow.log_artifact(str(path), artifact_path="evidence")
            mlflow.log_artifacts(str(wrapper_dir), artifact_path="model")
            artifact_uri = mlflow.get_artifact_uri()
            model_source_uri = mlflow.get_artifact_uri("model")

        _ensure_registered_model(client, model_name, candidate)
        version = client.create_model_version(
            name=model_name,
            source=model_source_uri,
            run_id=run_id,
            tags=_version_tags(candidate, decision, registry_entry),
        )
        version_id = str(getattr(version, "version", ""))
        if registry_entry.alias in FINAL_ALIASES:
            client.set_registered_model_alias(model_name, registry_entry.alias, version_id)
        client.set_registered_model_tag(model_name, "tryops.workload", candidate.workload)
        client.set_registered_model_tag(model_name, "tryops.source_model_name", candidate.model_name)

        return {
            "schema_version": "tryops.mlflow_registry.v1",
            "status": "ok",
            "tracking_uri": uri,
            "public_url": public_url(),
            "artifact_bucket": artifact_bucket(),
            "experiment_name": experiment_name,
            "experiment_id": experiment_id,
            "run_id": run_id,
            "run_url": mlflow_run_url(experiment_id, run_id),
            "model_name": model_name,
            "source_model_name": candidate.model_name,
            "model_version": version_id,
            "model_url": mlflow_model_version_url(model_name, version_id),
            "artifact_uri": artifact_uri,
            "model_source_uri": model_source_uri,
            "alias": registry_entry.alias,
        }
    except Exception as exc:
        return _unavailable(exc)


def log_deployment_package_to_mlflow(
    *,
    promotion_run_dir: Path,
    deployment_package_dir: Path,
) -> dict[str, Any]:
    registry_path = promotion_run_dir / "mlflow_registry.json"
    if not registry_path.exists() or not mlflow_enabled():
        return _status("skipped", "promotion run has no MLflow registry metadata")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _unavailable(exc)
    run_id = str(registry.get("run_id") or "")
    if not run_id:
        return _status("skipped", "promotion run has no MLflow run_id")
    try:
        mlflow, _client_cls = _import_mlflow()
        mlflow.set_tracking_uri(tracking_uri())
        with mlflow.start_run(run_id=run_id):
            for filename in ("deployment_manifest.json", "rollback_plan.json", "release_notes.md"):
                path = deployment_package_dir / filename
                if path.exists():
                    mlflow.log_artifact(str(path), artifact_path="deployment")
        return {"schema_version": "tryops.mlflow_deployment_log.v1", "status": "ok", "run_id": run_id}
    except Exception as exc:
        return _unavailable(exc)


def mlflow_status() -> dict[str, Any]:
    if not mlflow_enabled():
        return _status("disabled", "TRYOPS_MLFLOW_ENABLED is disabled")
    try:
        _mlflow, client_cls = _import_mlflow()
        client = client_cls(tracking_uri=tracking_uri())
        experiments = client.search_experiments(max_results=1)
        return {
            "schema_version": "tryops.mlflow_status.v1",
            "status": "ok",
            "tracking_uri": tracking_uri(),
            "public_url": public_url(),
            "artifact_bucket": artifact_bucket(),
            "experiment_probe_count": len(experiments),
        }
    except Exception as exc:
        return _unavailable(exc)


def sync_mlflow_registry_to_db(conn: Any) -> dict[str, Any]:
    from tryops import db

    status = mlflow_status()
    if status.get("status") != "ok":
        return {
            "schema_version": "tryops.mlflow_sync.v1",
            "status": "unavailable",
            "synced": 0,
            "mlflow": status,
        }
    _mlflow, client_cls = _import_mlflow()
    client = client_cls(tracking_uri=tracking_uri())
    synced = 0
    for version in client.search_model_versions(""):
        record = _model_version_to_record(client, version)
        db.upsert_model(conn, record)
        synced += 1
    return {
        "schema_version": "tryops.mlflow_sync.v1",
        "status": "ok",
        "synced": synced,
        "tracking_uri": tracking_uri(),
        "public_url": public_url(),
    }


def list_mlflow_artifacts(run_id: str, path: str = "") -> dict[str, Any]:
    _mlflow, client_cls = _import_mlflow()
    client = client_cls(tracking_uri=tracking_uri())
    artifacts = []
    for artifact in client.list_artifacts(run_id, path or None):
        artifact_path = str(getattr(artifact, "path", ""))
        artifacts.append(
            {
                "path": artifact_path,
                "is_dir": bool(getattr(artifact, "is_dir", False)),
                "file_size": getattr(artifact, "file_size", None),
                "download_url": (
                    f"/api/mlflow/artifacts/{quote(run_id)}/file?path={quote(artifact_path)}"
                    if artifact_path and not bool(getattr(artifact, "is_dir", False))
                    else None
                ),
            }
        )
    return {
        "schema_version": "tryops.mlflow_artifacts.v1",
        "status": "ok",
        "run_id": run_id,
        "path": path,
        "data": artifacts,
    }


def download_mlflow_artifact(run_id: str, path: str) -> Path:
    if not path.strip():
        raise ValueError("artifact path is required")
    _mlflow, client_cls = _import_mlflow()
    client = client_cls(tracking_uri=tracking_uri())
    return Path(client.download_artifacts(run_id, path))


def registered_model_name(candidate: ModelCandidate) -> str:
    model_name = ".".join(
        part.strip().replace("/", ".")
        for part in ("tryops", candidate.workload, candidate.model_name)
        if part.strip()
    )
    return model_name or candidate.model_name


def mlflow_run_url(experiment_id: str, run_id: str) -> str:
    return f"{public_url()}/#/experiments/{quote(str(experiment_id))}/runs/{quote(str(run_id))}"


def mlflow_model_version_url(model_name: str, version: str) -> str:
    return f"{public_url()}/#/models/{quote(str(model_name), safe='')}/versions/{quote(str(version))}"


def _import_mlflow() -> tuple[Any, Any]:
    import mlflow
    from mlflow.tracking import MlflowClient

    return mlflow, MlflowClient


def _status(status: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "tryops.mlflow_registry.v1",
        "status": status,
        "message": message,
        "tracking_uri": tracking_uri(),
        "public_url": public_url(),
        "artifact_bucket": artifact_bucket(),
    }


def _unavailable(exc: Exception) -> dict[str, Any]:
    if mlflow_required():
        raise RuntimeError(f"MLflow integration failed: {exc}") from exc
    return {
        "schema_version": "tryops.mlflow_registry.v1",
        "status": "unavailable",
        "message": str(exc),
        "tracking_uri": tracking_uri(),
        "public_url": public_url(),
        "artifact_bucket": artifact_bucket(),
    }


def _run_tags(
    candidate: ModelCandidate,
    decision: PromotionDecision,
    registry_entry: RegistryEntry,
) -> dict[str, str]:
    tags = dict(registry_entry.tags)
    tags.update(
        {
            "tryops.candidate_id": candidate.candidate_id,
            "tryops.workload": candidate.workload,
            "tryops.model_name": candidate.model_name,
            "tryops.model_version": candidate.model_version,
            "tryops.alias": registry_entry.alias,
            "tryops.decision": "approved" if decision.approved else "rejected",
        }
    )
    return {key: str(value) for key, value in tags.items() if value is not None}


def _version_tags(
    candidate: ModelCandidate,
    decision: PromotionDecision,
    registry_entry: RegistryEntry,
) -> dict[str, str]:
    return _run_tags(candidate, decision, registry_entry)


def _run_params(
    candidate: ModelCandidate,
    decision: PromotionDecision,
    validation_report: dict[str, Any],
    run_context: dict[str, Any],
) -> dict[str, str]:
    params = {
        "candidate_id": candidate.candidate_id,
        "workload": candidate.workload,
        "source_model_name": candidate.model_name,
        "source_model_version": candidate.model_version,
        "target_stage": decision.target_stage,
        "risk_status": candidate.risk_status,
        "signed": str(candidate.signed).lower(),
        "dataset_version": str(candidate.metadata.get("dataset_version", "")),
        "pipeline_run_id": str(candidate.metadata.get("pipeline_run_id", "")),
        "data_validation_passed": str(bool(validation_report.get("passed"))).lower(),
        "run_context_id": str(run_context.get("run_id", "")),
        "trace_id": str(run_context.get("trace_id", "")),
    }
    return {key: value[:500] for key, value in params.items()}


def _promotion_artifact_paths(run_dir: Path) -> list[Path]:
    return [
        run_dir / "promotion_decision.json",
        run_dir / "policy_candidate.json",
        run_dir / "data_validation.json",
        run_dir / "lineage.json",
        run_dir / "openlineage_run_event.json",
        run_dir / "openlineage_validation.json",
        run_dir / "native_policy_decision.json",
        run_dir / "run_context.json",
        run_dir / "registry_entry.json",
        run_dir / "model_card.md",
        run_dir / "data_card.md",
    ]


def _select_artifact_proxy_experiment(client: Any, experiment_name: str) -> str:
    existing = client.get_experiment_by_name(experiment_name)
    if existing is None:
        return experiment_name
    artifact_location = str(getattr(existing, "artifact_location", "") or "")
    if artifact_location.startswith("s3://"):
        return f"{experiment_name}-proxied"
    return experiment_name


def _write_model_wrapper(
    run_dir: Path,
    *,
    candidate: ModelCandidate,
    decision: PromotionDecision,
    registry_entry: RegistryEntry,
) -> Path:
    wrapper_dir = run_dir / "mlflow_model_wrapper"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": "tryops.mlflow_model_wrapper.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "candidate": candidate.to_dict(),
        "promotion_decision": decision.to_dict(),
        "registry_entry": registry_entry.to_dict(),
        "artifact_policy": "metadata-wrapper-no-large-weight-copy",
    }
    (wrapper_dir / "model_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    (wrapper_dir / "MLmodel").write_text(
        "\n".join(
            [
                "artifact_path: model",
                "flavors:",
                "  tryops_external:",
                f"    workload: {candidate.workload}",
                f"    source_model_name: {candidate.model_name}",
                f"    source_model_version: {candidate.model_version}",
                f"    candidate_id: {candidate.candidate_id}",
                "    artifact_policy: metadata-wrapper-no-large-weight-copy",
                f"utc_time_created: {datetime.now(UTC).isoformat()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return wrapper_dir


def _ensure_registered_model(client: Any, model_name: str, candidate: ModelCandidate) -> None:
    try:
        try:
            client.create_registered_model(
                model_name,
                tags={
                    "tryops.workload": candidate.workload,
                    "tryops.source_model_name": candidate.model_name,
                },
            )
        except TypeError:
            client.create_registered_model(model_name)
    except Exception as exc:
        if "already exists" not in str(exc).lower() and "resource_already_exists" not in str(exc).lower():
            raise


def _model_version_to_record(client: Any, version: Any) -> dict[str, Any]:
    tags = dict(getattr(version, "tags", {}) or {})
    run_id = str(getattr(version, "run_id", "") or "")
    metrics: dict[str, Any] = {}
    experiment_id = ""
    if run_id:
        try:
            run = client.get_run(run_id)
            metrics = dict(run.data.metrics)
            experiment_id = str(run.info.experiment_id)
        except Exception:
            metrics = {}
    aliases = set(getattr(version, "aliases", []) or [])
    stage = _stage_from_aliases(aliases, tags)
    model_name = str(getattr(version, "name", ""))
    version_id = str(getattr(version, "version", ""))
    created_at = _timestamp_to_iso(getattr(version, "creation_timestamp", None))
    return {
        "id": f"mlflow:{model_name}:{version_id}",
        "name": tags.get("tryops.model_name") or tags.get("tryops.source_model_name") or model_name,
        "workload": tags.get("tryops.workload") or "unknown",
        "stage": stage,
        "version": tags.get("tryops.model_version") or version_id,
        "signed": 1 if tags.get("signed") == "true" else 0,
        "approved": 1 if tags.get("decision") == "approved" or tags.get("tryops.decision") == "approved" else 0,
        "metrics": metrics,
        "created_at": created_at,
        "mlflow_tracking_uri": tracking_uri(),
        "mlflow_run_id": run_id,
        "mlflow_experiment_id": experiment_id,
        "mlflow_model_name": model_name,
        "mlflow_model_version": version_id,
        "mlflow_artifact_uri": str(getattr(version, "source", "") or ""),
        "mlflow_model_uri": f"models:/{model_name}/{version_id}",
        "mlflow_run_url": mlflow_run_url(experiment_id, run_id) if experiment_id and run_id else None,
        "mlflow_model_url": mlflow_model_version_url(model_name, version_id),
        "artifact_backend": "minio",
    }


def _stage_from_aliases(aliases: set[str], tags: dict[str, str]) -> str:
    for alias in ("champion", "challenger", "candidate"):
        if alias in aliases:
            return alias
    alias = tags.get("tryops.alias") or tags.get("target_stage") or "candidate"
    if alias in {"candidate", "challenger", "champion", "rejected", "archived"}:
        return alias
    return "candidate"


def _timestamp_to_iso(value: Any) -> str:
    try:
        timestamp = int(value) / 1000
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    except Exception:
        return datetime.now(UTC).isoformat()
