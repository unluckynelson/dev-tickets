#!/usr/bin/env bash
# The playground: Django (dev_tickets from python/) on :8300 and the Nuxt layer's
# playground (nuxt/.playground) on :3300, which proxies the backend paths.
#   ./playground/run.sh        then open http://localhost:3300/playground/ and pick a person
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/python/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "▸ creating python/.venv"
  python3 -m venv "$ROOT/python/.venv"
  "$ROOT/python/.venv/bin/pip" install -q -e "$ROOT/python[dev,mcp]"
fi
[ -d "$ROOT/nuxt/node_modules" ] || (cd "$ROOT/nuxt" && npm install)

cd "$ROOT/playground/backend"
unset DJANGO_SETTINGS_MODULE
"$PY" manage.py migrate -v0
[ -f .seeded ] || { "$PY" manage.py seed_playground && touch .seeded; }

"$PY" manage.py runserver 8300 &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
cd "$ROOT/nuxt" && npx nuxi dev .playground --port 3300
