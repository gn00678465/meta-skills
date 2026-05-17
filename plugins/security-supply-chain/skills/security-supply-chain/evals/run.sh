#!/usr/bin/env bash
# Run the full eval suite. Each script exits non-zero on failure; this
# script chains them and prints a final status. Doesn't `set -e` so all
# three checks always run even if an earlier one fails — you want to see
# every category of problem in one pass.
#
# Usage:
#   ./evals/run.sh                  # from skills/security-supply-chain/
#   evals/run.sh                    # works either way

set -u

cd "$(dirname "$0")/.."   # cd to the skill root (parent of evals/)

PY="${PY:-python}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python3
fi

FAIL=0

echo "============================================================"
echo "  validate_examples"
echo "============================================================"
"$PY" evals/scripts/validate_examples.py || FAIL=$((FAIL+1))

echo
echo "============================================================"
echo "  check_links"
echo "============================================================"
"$PY" evals/scripts/check_links.py || FAIL=$((FAIL+1))

echo
echo "============================================================"
echo "  check_consistency"
echo "============================================================"
"$PY" evals/scripts/check_consistency.py || FAIL=$((FAIL+1))

echo
echo "============================================================"
if [ "$FAIL" -eq 0 ]; then
  echo "  ALL CHECKS PASS"
  exit 0
else
  echo "  $FAIL CHECK(S) FAILED"
  exit 1
fi
