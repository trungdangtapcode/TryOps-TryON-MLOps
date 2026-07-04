#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

tex_file="${1:-report/TRYOPS_MLOPS_FINAL_REPORT_VI.tex}"
out_dir="$(dirname "$tex_file")"
pdf_file="${tex_file%.tex}.pdf"
docker_image="${REPORT_TEX_IMAGE:-debian:bookworm-slim}"

if [[ ! -f "$repo_root/$tex_file" ]]; then
  echo "error: TeX file not found: $repo_root/$tex_file" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required to compile the report with this script" >&2
  exit 1
fi

docker run --rm \
  -e TEX_FILE="$tex_file" \
  -e OUT_DIR="$out_dir" \
  -v "$repo_root":/work \
  -w /work \
  "$docker_image" \
  sh -lc '
    set -e
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends \
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-pictures \
      texlive-fonts-recommended \
      texlive-lang-other \
      lmodern
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$OUT_DIR" "$TEX_FILE"
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$OUT_DIR" "$TEX_FILE"
  '

echo "Built: $repo_root/$pdf_file"
