#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


DEFAULT_SECRET = "tryops-local-github-webhook"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a signed GitHub-style promotion PR webhook.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = build_pull_request_payload(manifest)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    delivery_id = f"tryops-github-delivery-{uuid4()}"
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sign_payload(body=body, secret=args.secret),
    }
    response = post_json(args.url, body=body, headers=headers)
    passed = response["status_code"] == 202 and bool(response.get("json", {}).get("accepted"))
    report = {
        "schema_version": "tryops.signed_pr_promotion_report.v1",
        "passed": passed,
        "url": args.url,
        "delivery_id": delivery_id,
        "event": "pull_request.closed",
        "candidate_id": payload["tryops_promotion"]["candidate_id"],
        "package_id": payload["tryops_promotion"]["package_id"],
        "pull_request": payload["number"],
        "signature": {
            "algorithm": "hmac-sha256",
            "header": "X-Hub-Signature-256",
            "format": "sha256=<hex>",
            "verified_by": "native-go-tryops-controller",
        },
        "request": payload,
        "response": response,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 2


def build_pull_request_payload(manifest: dict) -> dict:
    package_id = str(manifest.get("package_id"))
    candidate_id = str(manifest.get("candidate_id"))
    checks = manifest.get("checks", {})
    lineage = manifest.get("lineage", {})
    provenance = lineage.get("provenance", {}) if isinstance(lineage, dict) else {}
    workload = manifest.get("model", {}).get("workload", "vton")
    target_stage = manifest.get("model", {}).get("alias", "champion")
    pr_number = 2000 + int(hashlib.sha256(package_id.encode("utf-8")).hexdigest()[:4], 16) % 5000
    head_sha = hashlib.sha256((package_id + ":head").encode("utf-8")).hexdigest()[:40]
    merge_sha = hashlib.sha256((package_id + ":merge").encode("utf-8")).hexdigest()[:40]
    return {
        "action": "closed",
        "number": pr_number,
        "repository": {
            "full_name": "tryops/tryops-gitops",
            "default_branch": "main",
        },
        "sender": {
            "login": "tryops-local-ci",
            "type": "Bot",
        },
        "pull_request": {
            "number": pr_number,
            "html_url": f"https://github.com/tryops/tryops-gitops/pull/{pr_number}",
            "title": f"Promote {candidate_id} to {target_stage}",
            "body": "TryOps promotion PR generated from policy-gated deployment evidence.",
            "merged": True,
            "merge_commit_sha": merge_sha,
            "base": {
                "ref": "main",
            },
            "head": {
                "sha": head_sha,
                "ref": f"promote/{candidate_id}",
            },
            "labels": [
                {"name": "tryops/promotion"},
                {"name": f"release/{manifest.get('profile', 'production-demo')}"},
            ],
        },
        "tryops_changed_files": [
            f"clusters/{manifest.get('profile', 'production-demo')}/{candidate_id}/deployment_manifest.json",
            f"clusters/{manifest.get('profile', 'production-demo')}/{candidate_id}/gitops/application.yaml",
            f"clusters/{manifest.get('profile', 'production-demo')}/{candidate_id}/gitops/rollout.yaml",
            f"clusters/{manifest.get('profile', 'production-demo')}/{candidate_id}/gitops/services.yaml",
        ],
        "tryops_promotion": {
            "candidate_id": candidate_id,
            "package_id": package_id,
            "profile": manifest.get("profile"),
            "workload": workload,
            "target_stage": target_stage,
            "approval_count": 2,
            "code_owner_approved": True,
            "commit_signature_verified": bool(provenance.get("verified") or manifest.get("model", {}).get("signed")),
            "status_checks_passed": True,
            "promotion_approved": bool(checks.get("promotion_approved")),
            "native_policy_matches_python": bool(checks.get("native_policy_matches_python")),
            "openlineage_validation_passed": bool(checks.get("openlineage_validation_passed")),
            "gitops_validation_passed": bool(checks.get("gitops_validation_passed")),
            "model_provenance_verified": bool(provenance.get("verified") or manifest.get("artifact_uris", {}).get("model_provenance")),
            "deployment_manifest_changed": True,
            "gitops_manifests_changed": bool(checks.get("gitops_manifests_present")),
        },
        "sent_at_unix": int(time.time()),
    }


def sign_payload(*, body: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return "sha256=" + signature


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
