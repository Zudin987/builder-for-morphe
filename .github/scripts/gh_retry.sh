#!/usr/bin/env bash

# Retry transient GitHub CLI/API failures without leaking partial stdout from
# failed attempts into command substitutions or JSON parsing.
gh_retry() {
  local attempt=1 max_attempts=8 delay=3 rc tmp
  tmp="$(mktemp)"

  while true; do
    : >"$tmp"
    if gh "$@" >"$tmp"; then
      cat "$tmp"
      rm -f "$tmp"
      return 0
    else
      rc=$?
    fi

    if (( attempt >= max_attempts )); then
      rm -f "$tmp"
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
