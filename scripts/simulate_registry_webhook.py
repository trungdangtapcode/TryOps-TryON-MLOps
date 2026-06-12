#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


DEFAULT_SECRET = "tryops-local-webhook"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a signed MLflow-style registry webhook.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = build_webhook_payload(manifest)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    delivery_id = f"tryops-delivery-{uuid4()}"
    timestamp = str(int(time.time()))
    signature = sign_payload(
        body=body,
        secret=args.secret,
        delivery_id=delivery_id,
        timestamp=timestamp,
    )
    headers = {
        "Content-Type": "application/json",
        "X-MLflow-Signature": signature,
        "X-MLflow-Delivery-ID": delivery_id,
        "X-MLflow-Timestamp": timestamp,
    }
    response = post_json(args.url, body=body, headers=headers)
    native_policy = response.get("json", {}).get("native_policy")
    native_policy_ok = True
    if payload["data"].get("policy_candidate"):
        native_policy_ok = bool(
            isinstance(native_policy, dict)
            and native_policy.get("available")
            and native_policy.get("decision", {}).get("approved")
        )
    passed = (
        response["status_code"] == 202
        and bool(response.get("json", {}).get("accepted"))
        and native_policy_ok
    )
    report = {
        "schema_version": "tryops.registry_webhook_report.v1",
        "passed": passed,
        "url": args.url,
        "delivery_id": delivery_id,
        "event": f"{payload['entity']}.{payload['action']}",
        "candidate_id": payload["data"]["candidate_id"],
        "package_id": payload["data"]["package_id"],
        "signature": {
            "algorithm": "hmac-sha256",
            "header": "X-MLflow-Signature",
            "format": "v1,<base64>",
            "verified_by": "native-go-tryops-controller",
        },
        "native_policy": native_policy,
        "request": payload,
        "response": response,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 2


def build_webhook_payload(manifest: dict) -> dict:
    registry = manifest.get("registry_entry", {})
    checks = manifest.get("checks", {})
    return {
        "entity": "model_version_alias",
        "action": "created",
        "timestamp": manifest.get("created_at"),
        "workspace": "tryops-local",
        "data": {
            "name": manifest.get("model", {}).get("name", registry.get("name", "unknown-model")),
            "alias": manifest.get("model", {}).get("alias", registry.get("alias", "champion")),
            "version": str(manifest.get("model", {}).get("version", registry.get("version", "0"))),
            "source": f"models:/{manifest.get('candidate_id', 'unknown')}",
            "run_id": manifest.get("source_run_context", {}).get("run_id"),
            "candidate_id": manifest.get("candidate_id"),
            "package_id": manifest.get("package_id"),
            "profile": manifest.get("profile"),
            "workload": manifest.get("model", {}).get("workload"),
            "deployment_manifest": str(Path("artifacts/deployments") / str(manifest.get("package_id")) / "deployment_manifest.json"),
            "gitops_path": manifest.get("gitops", {}).get("path"),
            "policy_candidate": manifest.get("policy_candidate", {}),
            "tags": {
                "candidate_id": manifest.get("candidate_id"),
                "package_id": manifest.get("package_id"),
                "profile": manifest.get("profile"),
                "workload": manifest.get("model", {}).get("workload"),
            },
            "checks": {
                "promotion_approved": bool(checks.get("promotion_approved")),
                "native_policy_matches_python": bool(checks.get("native_policy_matches_python")),
                "openlineage_validation_passed": bool(checks.get("openlineage_validation_passed")),
                "gitops_validation_passed": bool(checks.get("gitops_validation_passed")),
            },
        },
    }


def sign_payload(*, body: bytes, secret: str, delivery_id: str, timestamp: str) -> str:
    signed_content = b".".join([delivery_id.encode("utf-8"), timestamp.encode("utf-8"), body])
    signature = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).digest()
    return "v1," + base64.b64encode(signature).decode("ascii")


def post_json(url: str, *, body: bytes, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8")
            return {
                "status_code": response.status,
                "body": text,
                "json": _loads_json(text),
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        return {
            "status_code": exc.code,
            "body": text,
            "json": _loads_json(text),
        }


def _loads_json(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
