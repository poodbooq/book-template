#!/usr/bin/env bash
set -euo pipefail

readonly TEMPLATE="poodbooq/book-template"

usage() {
  printf 'Usage: %s REPOSITORY\n' "${0##*/}" >&2
}

if (( $# != 1 )) || [[ -z "$1" ]]; then
  usage
  exit 64
fi

if ! command -v gh >/dev/null 2>&1; then
  printf 'GitHub CLI (gh) is required: https://cli.github.com/\n' >&2
  exit 127
fi

if ! gh auth status >/dev/null 2>&1; then
  printf 'Authenticate GitHub CLI first: gh auth login\n' >&2
  exit 1
fi

gh repo create "$1" --private --template "$TEMPLATE" --clone
