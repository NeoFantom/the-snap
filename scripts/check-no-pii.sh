#!/usr/bin/env bash
# check-no-pii.sh — fail if the opensource/ tree contains personal data
# leaked from the originating private project. Run before any publish
# (manual or CI). Exits 0 if clean, non-zero with a report otherwise.
#
# Each pattern below is a *known* PII token from the originating project,
# whitelisted only inside ``LICENSE`` (which holds the copyright line).
#
# To add a new pattern: append below. To suppress a known-OK hit: extend
# the WHITELIST regex.

set -u

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || exit 2

# Files/paths excluded from the scan entirely.
EXCLUDE_PATHS=(
  ":(exclude)LICENSE"
  ":(exclude)scripts/check-no-pii.sh"
)

# Lines matched by this are ignored even if a pattern hits — for the
# copyright line, intentional examples in docs, etc.
WHITELIST_RE='^[[:space:]]*Copyright \(c\) 2026 Neo'

# PII patterns. Word-boundary anchors prevent matching e.g. "neon" for
# "neo". Add patterns as you discover them in this or future runs.
PATTERNS=(
  '\bneohu\b'
  '\bquarkonium\b'
  '\bQuarkonium\b'
  '\btop-quark\b'
  '\btop_quark\b'
  '\btopquark\b'
  '\bMeo\b'
  '\btaohuayuan\b'
  '\bZZY\b'
  '\bwxid_[A-Za-z0-9]+\b'
  'ryxgen1fv3z322'
  'yangzi3418'
  'zhyu\.zoey'
  '张钰'
  '100\.77\.91\.81'
  '100\.113\.63\.64'
  '10\.10\.4\.187'
  'cloudflare-api-token'
  'C:\\\\Users\\\\neohu'
  '/mnt/c/Meo'
  '/mnt/s/Neo'
  'S:\\\\Neo'
  'C:\\\\Quarkonium Plate'
)

HITS=0
for pat in "${PATTERNS[@]}"; do
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if echo "$line" | grep -qE "$WHITELIST_RE"; then
      continue
    fi
    echo "HIT  [$pat]  $line"
    HITS=$((HITS+1))
  done < <(git -C "$ROOT" grep -nE "$pat" -- "${EXCLUDE_PATHS[@]}" 2>/dev/null \
           || grep -rnE "$pat" \
               --exclude-dir=.git --exclude-dir=node_modules \
               --exclude=LICENSE --exclude="check-no-pii.sh" \
               "$ROOT" 2>/dev/null)
done

if [ "$HITS" -eq 0 ]; then
  echo "OK: no PII patterns found in $ROOT"
  exit 0
else
  echo
  echo "FAIL: $HITS PII hit(s). Scrub before publishing."
  exit 1
fi
