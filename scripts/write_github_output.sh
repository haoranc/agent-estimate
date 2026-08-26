#!/usr/bin/env bash
set -euo pipefail

name="${1:?usage: write_github_output.sh <name>}"
if ! [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
  printf 'invalid GitHub output name: %s\n' "$name" >&2
  exit 2
fi

value="$(cat)"

while :; do
  delimiter="agent_estimate_$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
  if ! printf '%s\n' "$value" | grep -Fqx -- "$delimiter"; then
    break
  fi
done

{
  printf '%s<<%s\n' "$name" "$delimiter"
  printf '%s\n' "$value"
  printf '%s\n' "$delimiter"
} >> "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
