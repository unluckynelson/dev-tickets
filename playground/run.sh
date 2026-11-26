#!/usr/bin/env bash
# The playground: Django (dev_tickets from python/) on :8300 and the Nuxt layer's
# playground (nuxt/.playground) on :3300, which proxies the backend paths.
#   ./playground/run.sh            then open http://localhost:3300/playground/ and pick a person
#
# The Django on :8300 is a hub. With --client a second install runs beside it as a
# client of that hub, as a staging server would: Django on :8301 with its own
# database and Nuxt on :3301. Its people (Priya, and a Maya who shares the hub
# Maya's address) file tickets that land on the hub's board, marked "from client-demo".
#   ./playground/run.sh --client   then also open http://localhost:3301/playground/
#
# With --open, the second install's mode is not set in its settings at all: open
# http://localhost:3302/playground/, then the board's Settings → Connection, and make
# it a client of the hub there with a key made in the hub's own Settings.
#   ./playground/run.sh --open
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/python/.venv/bin/python"
CLIENT=0
OPEN=0
case "${1:-}" in
  "") ;;
  --client) CLIENT=1 ;;
  --open) OPEN=1 ;;
  *) echo "usage: $0 [--client | --open]" >&2; exit 2 ;;
esac

if [ ! -x "$PY" ]; then
  echo "▸ creating python/.venv"
  python3 -m venv "$ROOT/python/.venv"
  "$ROOT/python/.venv/bin/pip" install -q -e "$ROOT/python[dev,mcp]"
fi
[ -d "$ROOT/nuxt/node_modules" ] || (cd "$ROOT/nuxt" && npm install)

cd "$ROOT/playground/backend"
unset DJANGO_SETTINGS_MODULE
export DEV_TICKETS_MODE=hub
"$PY" manage.py migrate -v0
[ -f .seeded ] || { "$PY" manage.py seed_playground && touch .seeded; }

# On exit, stop everything this script started: the whole process group, since
# runserver's reloader and npx each leave a child behind their own pid.
cleanup() { trap - EXIT INT TERM; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

"$PY" manage.py runserver 8300 &

if [ "$CLIENT" = 1 ]; then
  # The client's key: made once on the hub and kept in .client-key (gitignored). A
  # hub database that was reset has no such client any more, so it is made again.
  if "$PY" manage.py devtickets_client list | grep -q "^client-demo"$'\t'; then
    [ -s .client-key ] || "$PY" manage.py devtickets_client rotate client-demo | tail -1 > .client-key
  else
    "$PY" manage.py devtickets_client add client-demo --source client-demo | tail -1 > .client-key
  fi
  chmod 600 .client-key
  DEV_TICKETS_HUB_KEY="$(cat .client-key)"
  export DEV_TICKETS_HUB_KEY
  (
    export DEV_TICKETS_MODE=client
    "$PY" manage.py migrate -v0
    "$PY" manage.py seed_playground_client
    exec "$PY" manage.py runserver 8301
  ) &
  (cd "$ROOT/nuxt" && PLAYGROUND_BACKEND_PORT=8301 exec npx nuxi dev .playground --port 3301) &
fi

if [ "$OPEN" = 1 ]; then
  (
    export DEV_TICKETS_MODE=open
    "$PY" manage.py migrate -v0
    "$PY" manage.py seed_playground_client
    exec "$PY" manage.py runserver 8302
  ) &
  (cd "$ROOT/nuxt" && PLAYGROUND_BACKEND_PORT=8302 exec npx nuxi dev .playground --port 3302) &
fi
(cd "$ROOT/nuxt" && exec npx nuxi dev .playground --port 3300) &
# `wait`, not a foreground command: bash runs the trap only once a foreground
# command ends, but interrupts a wait at once.
wait
