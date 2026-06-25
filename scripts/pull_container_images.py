#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _image_exists(image: str) -> tuple[bool, str | None]:
    result = _run(["docker", "image", "inspect", image])
    if result.returncode == 0:
        return True, None
    output = result.stdout.strip()
    normalized = output.lower()
    if "no such image" in normalized or "no such object" in normalized or "not found" in normalized:
        return False, None
    return False, output or "docker image inspect failed"


def _pull_image(image: str, attempts: int, delay_seconds: float) -> bool:
    for attempt in range(1, attempts + 1):
        print(f"Pulling container base image {image} (attempt {attempt}/{attempts})", flush=True)
        result = _run(["docker", "pull", image])
        if result.returncode == 0:
            print(result.stdout.rstrip())
            return True
        print(result.stdout.rstrip(), file=sys.stderr)
        if attempt < attempts:
            time.sleep(delay_seconds)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Docker images with retries, skipping cached images by default.")
    parser.add_argument("images", nargs="+")
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--delay-seconds", type=float, default=8.0)
    parser.add_argument("--refresh", action="store_true", help="Pull even when the image already exists locally.")
    args = parser.parse_args()

    attempts = max(args.attempts, 1)
    failures: list[str] = []
    for image in args.images:
        if not args.refresh:
            exists, inspect_error = _image_exists(image)
            if inspect_error:
                print(f"Docker is not available for image inspection: {inspect_error}", file=sys.stderr)
                return 1
            if exists:
                print(f"Container base image already cached: {image}")
                continue
        if not _pull_image(image, attempts, args.delay_seconds):
            failures.append(image)

    if not failures:
        return 0

    print("Unable to pull required container base images after retries:", file=sys.stderr)
    for image in failures:
        print(f"  - {image}", file=sys.stderr)
    print("Check Docker Hub/GHCR connectivity or configure a registry mirror, then rerun make app-up.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
