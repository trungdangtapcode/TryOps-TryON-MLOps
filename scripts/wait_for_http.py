#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request


def wait_for_url(url: str, timeout_seconds: float, request_timeout_seconds: float, label: str) -> int:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=request_timeout_seconds) as response:
                response.read(256)
                if 200 <= response.status < 300:
                    print(f"{label} ready: {url}")
                    return 0
                last_error = f"HTTP {response.status}"
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = str(exc)
        time.sleep(2)

    print(f"{label} did not become ready at {url}: {last_error}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for an HTTP endpoint to return a 2xx response.")
    parser.add_argument("url")
    parser.add_argument("--label", default="service")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=2.0)
    args = parser.parse_args()

    return wait_for_url(args.url, args.timeout_seconds, args.request_timeout_seconds, args.label)


if __name__ == "__main__":
    raise SystemExit(main())
