#!/usr/bin/env bash

# Run one app build with a small retry for transient stock-APK source failures.
# In unattended CI, a stock APK that is temporarily unavailable should not make
# the entire daily pipeline red; the version watcher will try it again later.
set -euo pipefail

app="${1:?app id required}"
arch="${2:-}"
soft_stock_failure="${TOLERATE_STOCK_UNAVAILABLE:-false}"
max_attempts="${BUILD_ATTEMPTS:-2}"
delay="${BUILD_RETRY_DELAY:-20}"
# Keep in sync with BuildExit.STOCK_UNAVAILABLE in src/core/builder.py.
stock_unavailable=75
label="${app}${arch:+ ($arch)}"

args=("$app")
if [[ -n "$arch" ]]; then
  args+=("$arch")
fi

attempt=1
while true; do
  echo "Build attempt ${attempt}/${max_attempts}: ${label}"
  rc=0
  uv run main.py "${args[@]}" 2>&1 || rc=$?

  if (( rc == 0 )); then
    exit 0
  fi

  if (( rc == stock_unavailable )); then
    if (( attempt < max_attempts )); then
      echo "::warning title=Stock APK source unavailable::${label} could not obtain a compatible stock APK; retrying in ${delay}s."
      sleep "$delay"
      attempt=$((attempt + 1))
      continue
    fi

    if [[ "$soft_stock_failure" == "true" ]]; then
      echo "::warning title=App skipped temporarily::${label} could not obtain a compatible stock APK after ${max_attempts} attempts. Unattended CI will retry on a later run."
      exit 0
    fi
  fi

  echo "Build failed for ${label} (exit status ${rc})." >&2
  exit "$rc"
done
