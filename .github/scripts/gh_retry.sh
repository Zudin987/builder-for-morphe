#!/usr/bin/env bash

# Retry transient GitHub CLI/API failures without leaking partial stdout from
# failed attempts into command substitutions or JSON parsing. Permanent client
# errors are returned immediately instead of being retried like 5xx/rate limits.
gh_retry() {
  local attempt=1 max_attempts=8 delay=3 rc out err
  out="$(mktemp)"
  err="$(mktemp)"

  while true; do
    : >"$out"
    : >"$err"

    if gh "$@" >"$out" 2>"$err"; then
      cat "$out"
      [[ ! -s "$err" ]] || cat "$err" >&2
      rm -f "$out" "$err"
      return 0
    else
      rc=$?
    fi

    [[ ! -s "$err" ]] || cat "$err" >&2

    # 403/408/409/425/429 can be transient (rate limiting, lock/conflict,
    # timeout). Most other explicit 4xx responses are permanent for this call.
    if grep -Eq 'HTTP (400|401|402|404|405|406|407|410|411|412|413|414|415|416|417|418|421|422|423|424|426|428|431|451)' "$err"; then
      rm -f "$out" "$err"
      echo "GitHub API returned a non-retryable client error" >&2
      return "$rc"
    fi

    if (( attempt >= max_attempts )); then
      rm -f "$out" "$err"
      echo "GitHub API still failing after ${attempt} attempts" >&2
      return "$rc"
    fi

    echo "GitHub API temporary failure; retry ${attempt}/${max_attempts} in ${delay}s" >&2
    sleep "$delay"
    attempt=$((attempt + 1))
    if (( delay < 24 )); then
      delay=$((delay * 2))
    fi
  done
}
