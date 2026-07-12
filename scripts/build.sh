#!/usr/bin/env bash
set -euo pipefail

format="${1:-pdf}"
exec python3 "$(dirname "$0")/book.py" --root "$(dirname "$0")/.." build "$format"
