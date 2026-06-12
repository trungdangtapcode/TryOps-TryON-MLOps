from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path
from typing import Any


NATIVE_MODEL_SCAN_SCHEMA = "tryops.native_model_scan.v1"
DEFAULT_NATIVE_MODEL_SCAN_CLI = Path("artifacts/native/tryops_model_scan_cli")
PICKLE_LIKE_EXTENSIONS = {".bin", ".pt", ".pth", ".ckpt", ".pkl", ".pickle", ".joblib"}
REVIEW_REQUIRED_EXTENSIONS = {".h5", ".hdf5", ".keras", ".pb", ".onnx", ".tflite"}
SAFE_SUPPORT_EXTENSIONS = {".json", ".txt", ".md", ".model", ".vocab", ".merges", ".yaml", ".yml"}


def scan_model_artifacts(
    paths: list[str | Path],
    *,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized = [str(path) for path in paths]
    cli = Path(str(cli_path or os.environ.get("TRYOPS_NATIVE_MODEL_SCAN_CLI", DEFAULT_NATIVE_MODEL_SCAN_CLI)))
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli), *normalized],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode in {0, 2}:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_MODEL_SCAN_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_MODEL_SCAN_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "cli_path": str(cli),
            "returncode": completed.returncode,
            "passed": False,
            "safe_tensors_only": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    fallback = _python_scan_model_artifacts(normalized)
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["cli_path"] = str(cli)
    return fallback


def write_minimal_safetensors(path: str | Path) -> Path:
    """Write a tiny valid SafeTensors-shaped file for local gate evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    header = b'{"__metadata__":{"format":"tryops-demo"}}'
    output.write_bytes(struct.pack("<Q", len(header)) + header)
    return output


def _python_scan_model_artifacts(paths: list[str]) -> dict[str, Any]:
    files = []
    findings = []
    for path_text in paths:
        path = Path(path_text)
        suffix = path.suffix.lower()
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        report = {
            "path": path_text,
            "extension": suffix,
            "exists": exists,
            "size_bytes": size,
            "weight_like": suffix == ".safetensors" or suffix in PICKLE_LIKE_EXTENSIONS or suffix in REVIEW_REQUIRED_EXTENSIONS,
            "safetensors": suffix == ".safetensors",
            "header_valid": False,
            "rejected": False,
            "classification": "safe_support_file" if suffix in SAFE_SUPPORT_EXTENSIONS else "unknown_model_artifact",
            "fingerprint": "",
        }
        if not exists:
            report["rejected"] = True
            report["classification"] = "missing"
            findings.append(_finding("MODEL-FILE-MISSING", "critical", path_text, "model artifact path does not exist"))
        elif suffix == ".safetensors":
            report["header_valid"] = _valid_safetensors_header(path)
            report["classification"] = "safetensors_weight" if report["header_valid"] else "invalid_safetensors"
            report["rejected"] = not report["header_valid"]
            if report["rejected"]:
                findings.append(_finding("MODEL-SAFETENSORS-INVALID", "critical", path_text, "SafeTensors header is invalid"))
        elif suffix in PICKLE_LIKE_EXTENSIONS:
            report["rejected"] = True
            report["classification"] = "pickle_like_weight"
            findings.append(
                _finding(
                    "MODEL-PICKLE-FORMAT-BLOCKED",
                    "critical",
                    path_text,
                    "pickle-family model artifact is blocked by the SafeTensors-only policy",
                )
            )
        elif suffix in REVIEW_REQUIRED_EXTENSIONS:
            report["rejected"] = True
            report["classification"] = "active_or_graph_format_requires_review"
            findings.append(
                _finding(
                    "MODEL-ACTIVE-FORMAT-REVIEW-REQUIRED",
                    "high",
                    path_text,
                    "model serialization format requires an explicit scanner allowlist before promotion",
                )
            )
        elif suffix not in SAFE_SUPPORT_EXTENSIONS:
            report["rejected"] = True
            findings.append(
                _finding(
                    "MODEL-UNKNOWN-FORMAT",
                    "high",
                    path_text,
                    "unknown model artifact extension is rejected until allowlisted",
                )
            )
        files.append(report)

    safetensors = sum(1 for item in files if item["safetensors"] and item["header_valid"])
    unsafe = sum(1 for item in files if item["rejected"])
    passed = bool(files) and safetensors > 0 and unsafe == 0
    return {
        "schema_version": NATIVE_MODEL_SCAN_SCHEMA,
        "scanner": {"name": "tryops_model_scan", "language": "python", "version": "0.1.0"},
        "policy": "safetensors_only",
        "passed": passed,
        "safe_tensors_only": passed,
        "file_count": len(files),
        "summary": {
            "safetensors_files": safetensors,
            "unsafe_file_count": unsafe,
            "critical": sum(1 for item in findings if item["severity"] == "critical"),
            "high": sum(1 for item in findings if item["severity"] == "high"),
            "finding_count": len(findings),
        },
        "files": files,
        "findings": findings,
    }


def _valid_safetensors_header(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) < 10:
        return False
    header_size = struct.unpack("<Q", data[:8])[0]
    if header_size == 0 or header_size > len(data) - 8 or header_size > 16 * 1024 * 1024:
        return False
    header = data[8 : 8 + header_size].strip()
    return header.startswith(b"{") and header.endswith(b"}")


def _finding(finding_id: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {
        "id": finding_id,
        "severity": severity,
        "path": path,
        "message": message,
    }
