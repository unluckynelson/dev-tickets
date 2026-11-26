#!/usr/bin/env bash
# Both packages are released under one version. This fails, naming each file, if
#   python/pyproject.toml, python/src/dev_tickets/__init__.py and nuxt/package.json
# disagree, or if they do not match the version given (e.g. the tag being released).
#   scripts/check-versions.sh            # just "do they agree?"
#   scripts/check-versions.sh 1.4.2      # ...and are they 1.4.2?
#   scripts/check-versions.sh v1.4.2     # a tag works too
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

py=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$ROOT/python/pyproject.toml" | head -1)
init=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/python/src/dev_tickets/__init__.py" | head -1)
npm=$(node -p "require('$ROOT/nuxt/package.json').version")
lock=$(node -p "require('$ROOT/nuxt/package-lock.json').version")

fail=0
for pair in "python/pyproject.toml=$py" "python/src/dev_tickets/__init__.py=$init" \
            "nuxt/package.json=$npm" "nuxt/package-lock.json=$lock"; do
  file=${pair%%=*}; ver=${pair#*=}
  if [ -z "$ver" ]; then echo "✗ no version found in $file" >&2; fail=1; fi
  if [ "$ver" != "$py" ]; then echo "✗ $file says $ver, python/pyproject.toml says $py" >&2; fail=1; fi
done

if [ $# -ge 1 ]; then
  want=${1#v}
  if [ "$py" != "$want" ]; then echo "✗ packages are $py, expected $want" >&2; fail=1; fi
fi

[ $fail -eq 0 ] && echo "✓ version $py everywhere"
exit $fail
