#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an OpenAI-compatible LLM /models endpoint.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", default=os.environ.get("TRYOPS_LLM_API_KEY", ""))
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/models"
    headers = {"Accept": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
            response.read(1024)
        return 0
    except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"real LLM endpoint check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
