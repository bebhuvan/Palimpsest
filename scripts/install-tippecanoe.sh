#!/usr/bin/env bash
set -euo pipefail

TIPPECANOE_VERSION="2.79.0"
TIPPECANOE_SHA256="b0fd9df49b6efc988288ea48774822c6de19eb48428017f27ee0b3b01d44f05d"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${PROJECT_ROOT}/.tools/tippecanoe-${TIPPECANOE_VERSION}"
BIN_DIR="${PROJECT_ROOT}/.tools/bin"

if [[ -x "${BIN_DIR}/tippecanoe" ]]; then
  "${BIN_DIR}/tippecanoe" --version
  exit 0
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT
ARCHIVE="${TEMP_DIR}/tippecanoe.tar.gz"

curl --fail --location --silent --show-error \
  "https://github.com/felt/tippecanoe/archive/refs/tags/${TIPPECANOE_VERSION}.tar.gz" \
  --output "${ARCHIVE}"
printf '%s  %s\n' "${TIPPECANOE_SHA256}" "${ARCHIVE}" | sha256sum --check --status
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"
tar --extract --gzip --file "${ARCHIVE}" --strip-components=1 --directory "${INSTALL_DIR}"
make --directory "${INSTALL_DIR}" -j"$(getconf _NPROCESSORS_ONLN)"

for binary in tippecanoe tippecanoe-decode tippecanoe-enumerate tippecanoe-json-tool tile-join; do
  cp "${INSTALL_DIR}/${binary}" "${BIN_DIR}/${binary}"
done

"${BIN_DIR}/tippecanoe" --version

