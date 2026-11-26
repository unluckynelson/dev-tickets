#!/usr/bin/env bash
# Cut a release of both packages under one version. Local and reversible: it commits
# and tags, and pushing is left to you, because the push is what publishes.
#
#   scripts/release.sh 1.5.0             # checks, bumps, changelog, commit, tag v1.5.0
#   scripts/release.sh 1.5.0 --dry-run   # everything it would check and change; writes nothing
#   scripts/release.sh 1.5.0 --skip-checks
#   git push --follow-tags               # CI builds, publishes to PyPI and npm, makes the GitHub release
#
# What it does, in order, stopping at the first problem:
#   1. refuses unless the tree is clean, you are on main, main matches origin, the version is
#      semver and newer than the current one, the tag is free, and CHANGELOG.md has notes
#      under [Unreleased] (an empty release note is how a release ships unexplained);
#   2. runs the same checks as CI: pytest + ruff, eslint + typecheck;
#   3. writes the version into python/pyproject.toml, dev_tickets/__init__.py,
#      nuxt/package.json and its lock, and moves the [Unreleased] notes under the version;
#   4. commits "Release vX.Y.Z" and makes an annotated tag.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[ $# -ge 1 ] || usage
VERSION=${1#v}
DRY=0
CHECKS=1
for arg in "${@:2}"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --skip-checks) CHECKS=0 ;;
    *) usage ;;
  esac
done
TAG="v$VERSION"
die() { echo "✗ $*" >&2; exit 1; }
step() { echo "▸ $*"; }

# --- 1. preconditions -----------------------------------------------------------------
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]] \
  || die "'$VERSION' is not a version like 1.4.2 or 1.5.0-rc.1"

[ -z "$(git status --porcelain)" ] || die "the working tree has changes; commit or stash them first"
branch=$(git branch --show-current)
[ "$branch" = "main" ] || die "releases are cut from main (you are on '$branch')"
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] \
  || die "main is not the same as origin/main; pull or push first"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"

scripts/check-versions.sh >/dev/null || die "the packages disagree about their version (run scripts/check-versions.sh)"
CURRENT=$(sed -n 's/^version = "\(.*\)"$/\1/p' python/pyproject.toml | head -1)
newer=$(printf '%s\n%s\n' "$CURRENT" "$VERSION" | sort -V | tail -1)
[ "$VERSION" != "$CURRENT" ] && [ "$newer" = "$VERSION" ] \
  || die "$VERSION is not newer than the current $CURRENT"

notes=$(awk '/^## \[Unreleased\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md | grep -v '^[[:space:]]*$' || true)
[ -n "$notes" ] || die "CHANGELOG.md has nothing under [Unreleased]; write the release notes first"

echo "Releasing $CURRENT → $VERSION"
echo "$notes" | sed 's/^/    /'

# --- 2. the same checks as CI ---------------------------------------------------------
if [ $CHECKS -eq 1 ]; then
  step "python: pytest + ruff"
  [ -x python/.venv/bin/python ] || die "python/.venv is missing (see README → Development)"
  (cd python && .venv/bin/pytest -q && .venv/bin/ruff check .) >/dev/null \
    || die "python checks failed (run them in python/ to see why)"
  step "nuxt: eslint + typecheck"
  (cd nuxt && npx eslint . && npx nuxi typecheck .playground) >/dev/null \
    || die "nuxt checks failed (run npm run lint / npm run typecheck in nuxt/)"
fi

if [ $DRY -eq 1 ]; then
  echo "✓ dry run: all checks pass; nothing was changed"
  exit 0
fi

# --- 3. bump and changelog ------------------------------------------------------------
step "writing $VERSION into both packages"
sed -i.bak "s/^version = \".*\"$/version = \"$VERSION\"/" python/pyproject.toml
sed -i.bak "s/^__version__ = \".*\"$/__version__ = \"$VERSION\"/" python/src/dev_tickets/__init__.py
rm -f python/pyproject.toml.bak python/src/dev_tickets/__init__.py.bak
(cd nuxt && npm version "$VERSION" --no-git-tag-version --allow-same-version >/dev/null)
scripts/check-versions.sh "$VERSION" >/dev/null || die "the bump did not land everywhere"

step "moving the [Unreleased] notes under [$VERSION]"
today=$(date -u +%Y-%m-%d)
awk -v v="$VERSION" -v d="$today" '
  /^## \[Unreleased\]/ { print; print ""; print "## [" v "] - " d; next }
  { print }
' CHANGELOG.md > CHANGELOG.md.new && mv CHANGELOG.md.new CHANGELOG.md

# --- 4. commit and tag ----------------------------------------------------------------
step "commit and tag $TAG"
git add python/pyproject.toml python/src/dev_tickets/__init__.py \
        nuxt/package.json nuxt/package-lock.json CHANGELOG.md
git commit -q -m "Release $TAG"
git tag -a "$TAG" -m "$TAG"$'\n\n'"$notes"

echo "✓ $TAG is ready. Publish it with:"
echo "    git push --follow-tags"
