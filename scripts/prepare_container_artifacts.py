#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


WRITABLE_DIRS = (
    Path("artifacts/app"),
    Path("artifacts/cache"),
    Path("artifacts/cache/tmp"),
    Path("artifacts/cache/xdg"),
    Path("artifacts/eval/gateway_benchmark"),
    Path("artifacts/hf-home"),
    Path("artifacts/hf-home/hub"),
    Path("artifacts/hf-home/xet"),
    Path("artifacts/logs"),
    Path("artifacts/otel"),
    Path("artifacts/traces"),
    Path("artifacts/runtime"),
    Path("artifacts/runtime/vton"),
    Path("artifacts/eval/full_stack"),
    Path("artifacts/eval/jobs"),
)

BIND_SOURCE_DIRS = (
    Path("artifacts/demo"),
    Path("artifacts/deployments"),
    Path("artifacts/eval"),
    Path("configs"),
    Path("configs/keycloak"),
    Path("infra/alertmanager"),
    Path("infra/grafana/dashboards"),
    Path("infra/grafana/provisioning"),
    Path("infra/loki"),
    Path("infra/otel"),
    Path("infra/prometheus"),
    Path("infra/tempo"),
    Path("reports/generated"),
    Path("src"),
    Path("web"),
)

WRITABLE_FILES = (
    Path("artifacts/logs/api_events.jsonl"),
    Path("artifacts/logs/gateway_events.jsonl"),
    Path("artifacts/logs/gateway_tls_events.jsonl"),
    Path("artifacts/traces/api_spans.jsonl"),
)


def _make_user_writable(path: Path) -> None:
    try:
        current = path.stat()
    except OSError:
        return
    if current.st_uid != os.getuid():
        return
    permissions = stat.S_IMODE(current.st_mode)
    desired = permissions | stat.S_IRUSR | stat.S_IWUSR
    if path.is_dir():
        desired |= stat.S_IXUSR
    if desired != permissions:
        path.chmod(desired)


def _probe_directory(path: Path) -> str | None:
    marker = path / f".tryops-write-check-{os.getpid()}"
    try:
        with marker.open("w", encoding="utf-8") as handle:
            handle.write("ok\n")
    except OSError as exc:
        return f"{path}: cannot create files ({exc})"
    finally:
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    return None


def _probe_directory_readable(path: Path) -> str | None:
    try:
        if not path.is_dir():
            return f"{path}: not a directory"
        next(path.iterdir(), None)
    except StopIteration:
        return None
    except OSError as exc:
        return f"{path}: cannot read directory ({exc})"
    return None


def _probe_file(path: Path) -> str | None:
    try:
        with path.open("ab"):
            pass
    except OSError as exc:
        return f"{path}: cannot append ({exc})"
    return None


def prepare_artifacts(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()

    for relative_path in WRITABLE_DIRS:
        path = root / relative_path
        try:
            path.mkdir(parents=True, exist_ok=True)
            _make_user_writable(path)
        except OSError as exc:
            errors.append(f"{relative_path}: cannot create or repair directory ({exc})")
            continue
        error = _probe_directory(path)
        if error:
            errors.append(error.replace(str(root) + os.sep, ""))

    for relative_path in BIND_SOURCE_DIRS:
        path = root / relative_path
        try:
            path.mkdir(parents=True, exist_ok=True)
            _make_user_writable(path)
        except OSError as exc:
            errors.append(f"{relative_path}: cannot create bind source directory ({exc})")
            continue
        error = _probe_directory_readable(path)
        if error:
            errors.append(error.replace(str(root) + os.sep, ""))

    for relative_path in WRITABLE_FILES:
        path = root / relative_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _make_user_writable(path.parent)
        except OSError as exc:
            errors.append(f"{relative_path.parent}: cannot create directory ({exc})")
            continue
        if path.exists():
            _make_user_writable(path)
        error = _probe_file(path)
        if error:
            errors.append(error.replace(str(root) + os.sep, ""))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare bind-mounted artifact directories for local containers.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    args = parser.parse_args()

    errors = prepare_artifacts(args.root)
    if not errors:
        return 0

    uid = os.environ.get("TRYOPS_CONTAINER_UID", str(os.getuid()))
    gid = os.environ.get("TRYOPS_CONTAINER_GID", str(os.getgid()))
    print(
        "Container artifact paths are not writable by the UID/GID used for app containers "
        f"({uid}:{gid}).",
        file=sys.stderr,
    )
    print("Fix the listed host/NAS paths or run the stack with a writable TRYOPS_CONTAINER_UID/GID:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
