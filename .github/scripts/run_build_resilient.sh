#!/usr/bin/env bash

# Run one app build with a small retry for transient stock-APK source failures.
# In unattended CI, a stock APK that is temporarily unavailable should not make
# the entire daily pipeline red; the version watcher will try it again later.
set -uo pipefail

app="${1:?app id required}"
arch="${2:-}"
soft_stock_failure="${TOLERATE_STOCK_UNAVAILABLE:-false}"
max_attempts="${BUILD_ATTEMPTS:-2}"
delay="${BUILD_RETRY_DELAY:-20}"

args=("$app")
if [[ -n "$arch" ]]; then
  args+=("$arch")
fi

is_stock_source_failure() {
  local log="$1"
  grep -Eq \
    "Stock APK not found|No matching variant found for arch|Failed to fetch '.*' from '.*' \(version=.*arch=.*\)|src/scrapers/(github|apkmirror|uptodown)\.py" \
    "$log"
}

attempt=1
while true; do
  log="$(mktemp)"
  echo "Build attempt ${attempt}/${max_attempts}: ${app}${arch:+ ($arch)}"

  set +e
  uv run main.py "${args[@]}" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  set -e

  if (( rc == 0 )); then
    rm -f "$log"
    exit 0
  fi

  if is_stock_source_failure "$log"; then
    if (( attempt < max_attempts )); then
      echo "::warning title=Stock APK source unavailable::${app} could not obtain a compatible stock APK; retrying in ${delay}s."
      rm -f "$log"
      sleep "$delay"
      attempt=$((attempt + 1))
      continue
    fi

    if [[ "$soft_stock_failure" == "true" ]]; then
      echo "::warning title=App skipped temporarily::${app} could not obtain a compatible stock APK after ${max_attempts} attempts. Other apps will continue and unattended CI will try this app again on a later run."
      rm -f "$log"
      exit 0
    fi
  fi

  echo "Build failed for ${app}; this does not look like a stock-APK availability problem." >&2
  rm -f "$log"
  exit "$rc"
done
