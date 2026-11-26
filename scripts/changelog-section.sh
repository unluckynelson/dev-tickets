#!/usr/bin/env bash
# Print one version's section of CHANGELOG.md (without its heading): the release notes.
#   scripts/changelog-section.sh 1.4.2
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
want=${1#v}
awk -v v="$want" '
  /^## \[/ { if (found) exit; if (index($0, "## [" v "]") == 1) { found = 1; next } }
  found { print }
' "$ROOT/CHANGELOG.md" | sed -e '/./,$!d' | sed -e ':a' -e '/^\n*$/{$d;N;ba' -e '}'
