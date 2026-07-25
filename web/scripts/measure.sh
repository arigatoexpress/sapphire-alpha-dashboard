#!/usr/bin/env bash
# Re-measure every figure rendered on the marketing site.
#
# The site's whole claim is that its numbers are reproducible, so this script is
# the authority — `src/data/metrics.ts` is a transcription of its output, never
# a hand-edited guess. Run it against a CLEAN tree and update MEASURED_SHA and
# MEASURED_AT in the same commit as any value that changed.
#
#   ./web/scripts/measure.sh ~/Code/Sapphire
#
set -euo pipefail

TARGET="${1:-${SAPPHIRE_REPO:-$HOME/Code/Sapphire}}"

if [[ ! -d "$TARGET/.git" ]]; then
  echo "error: '$TARGET' is not a git repository." >&2
  echo "usage: $0 [path-to-sapphire-repo]" >&2
  exit 1
fi

cd "$TARGET"

sha="$(git rev-parse --short HEAD)"
dirty="$(git status --porcelain | wc -l | tr -d ' ')"

if [[ "$dirty" != "0" ]]; then
  echo "warning: working tree has $dirty uncommitted change(s)." >&2
  echo "         figures will not be reproducible from $sha alone." >&2
fi

# NUL-delimited so paths containing spaces cannot split an argument.
py_files()  { git ls-files -z '*.py'; }

test_funcs="$(py_files | xargs -0 grep -h '^\s*\(async \)\?def test_' | wc -l | tr -d ' ')"
routes="$(py_files | xargs -0 grep -ho '@[a-z_]*\.\(get\|post\|put\|delete\|patch\|head\|options\|websocket\)(' | wc -l | tr -d ' ')"
py_total="$(git ls-files '*.py' | wc -l | tr -d ' ')"
test_files="$(git ls-files '*.py' | grep -c '^tests/' || true)"
src_files="$(git ls-files '*.py' | grep -vc '^tests/' || true)"
contracts="$(git ls-files '*.sol' | wc -l | tr -d ' ')"

cat <<EOF

  repo            $TARGET
  commit          $sha
  measured        $(date -u +%Y-%m-%d)
  clean tree      $([[ "$dirty" == "0" ]] && echo yes || echo "NO ($dirty changed)")

  test functions  $test_funcs
  http routes     $routes
  source modules  $src_files
  test modules    $test_files
  python modules  $py_total
  contracts       $contracts

  Update web/src/data/metrics.ts with any value that moved, along with
  MEASURED_SHA ($sha) and MEASURED_AT.

EOF
