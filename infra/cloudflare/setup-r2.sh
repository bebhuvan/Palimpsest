#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${R2_BUCKET:-}" || -z "${R2_SNAPSHOT_BUCKET:-}" ]]; then
  echo "R2_BUCKET and R2_SNAPSHOT_BUCKET are required" >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRANGLER=(npx --yes wrangler@latest)

if ! "${WRANGLER[@]}" r2 bucket info "${R2_BUCKET}" >/dev/null 2>&1; then
  "${WRANGLER[@]}" r2 bucket create "${R2_BUCKET}" --storage-class Standard
fi
if ! "${WRANGLER[@]}" r2 bucket info "${R2_SNAPSHOT_BUCKET}" >/dev/null 2>&1; then
  "${WRANGLER[@]}" r2 bucket create "${R2_SNAPSHOT_BUCKET}" --storage-class Standard
fi

"${WRANGLER[@]}" r2 bucket cors set "${R2_BUCKET}" \
  --file "${PROJECT_ROOT}/infra/cloudflare/r2-cors.json"
"${WRANGLER[@]}" r2 bucket cors list "${R2_BUCKET}"
