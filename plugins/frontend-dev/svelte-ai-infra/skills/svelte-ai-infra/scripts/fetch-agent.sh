#!/usr/bin/env bash
# Usage: ./fetch-agent.sh <url> <out-path> [fallback-path]
# 嘗試從 <url> 下載到 <out-path>。若下載失敗且提供 <fallback-path>，
# 則改為從 fallback-path 複製。
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 <url> <out-path> [fallback-path]" >&2
  exit 1
fi

url="$1"
out="$2"
fallback="${3:-}"

mkdir -p "$(dirname "$out")"
tmp="$(mktemp)"

if curl -fsSL "$url" -o "$tmp"; then
  mv "$tmp" "$out"
  echo "[fetched] $out ($(wc -l < "$out") lines) ← $url"
elif [ -n "$fallback" ] && [ -f "$fallback" ]; then
  rm -f "$tmp"
  cp "$fallback" "$out"
  echo "[FALLBACK] $out ($(wc -l < "$out") lines) ← $fallback" >&2
  echo "[FALLBACK] reason: fetch failed for $url — using bundled initial version" >&2
else
  rm -f "$tmp"
  echo "[FAILED] $url and no usable fallback" >&2
  exit 1
fi
