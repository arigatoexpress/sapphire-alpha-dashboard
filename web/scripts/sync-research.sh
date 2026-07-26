#!/usr/bin/env bash
# Copy opted-in research from the Knowledge vault into the published corpus.
#
# The vault mixes rigorous analysis with GPU-generated notes that hallucinate
# (the night-shift connection files invent tickers and events). Publishing that
# corpus wholesale would be indistinguishable from making things up, so this
# script is deliberately opt-in: a file ships ONLY if its YAML frontmatter
# contains `publish: true`. Everything else is ignored, forever, by default.
#
#   ./web/scripts/sync-research.sh            # sync
#   ./web/scripts/sync-research.sh --dry-run  # show what would move
#
# Output lands in web/content/research/ and is committed, so what the site
# serves is reviewable in git rather than assembled at deploy time.
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$REPO_ROOT/web/content/research"
SOURCES=("$HOME/Knowledge" "$HOME/ops-state")

mkdir -p "$DEST"

found=0
copied=0
warned=0

for source in "${SOURCES[@]}"; do
  [[ -d "$source" ]] || continue

  # -print0 / read -d '' so paths containing spaces survive intact.
  while IFS= read -r -d '' file; do
    # Frontmatter only: a `publish: true` buried in prose must not opt a file in.
    frontmatter="$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} {print}' "$file")"
    grep -qE '^publish:[[:space:]]*true[[:space:]]*$' <<<"$frontmatter" || continue

    found=$((found + 1))
    name="$(basename "$file")"

    # Advisory leak scan. Positions and exact figures are operator-only, so flag
    # anything that looks like one — the human decides, this never blocks.
    if grep -qE '0x[a-fA-F0-9]{40}|\$[0-9][0-9,.]*(K|M|B)?\b|mNAV' "$file"; then
      echo "  ! $name — contains an address or exact figure; confirm it is meant to be public." >&2
      warned=$((warned + 1))
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
      echo "  would copy  $name"
    else
      cp "$file" "$DEST/$name"
      echo "  copied      $name"
      copied=$((copied + 1))
    fi
  done < <(find "$source" -name '*.md' -type f -print0 2>/dev/null)
done

echo
if [[ "$found" == "0" ]]; then
  cat <<'EOF'
  No research is opted in yet.

  To publish a report, add `publish: true` to its YAML frontmatter:

      ---
      title: Evidence packet with a written falsifier
      description: One-line summary shown on the research index.
      date: 2026-07-25
      publish: true
      ---

  Nothing publishes without that flag. Current positions and exact figures are
  operator-only — publish the framework and the retrospective, not the book.
EOF
else
  echo "  $found opted in, $copied copied, $warned flagged for review."
fi
