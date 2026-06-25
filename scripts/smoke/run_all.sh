#!/usr/bin/env bash
# Run all smoke tests in sequence.  Stop on first failure.
# Usage: bash scripts/smoke/run_all.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -f "$ROOT/.env" ]; then
    set -o allexport
    source "$ROOT/.env"
    set +o allexport
fi

echo "══════════════════════════════════════"
echo " Auteur smoke tests"
echo "══════════════════════════════════════"

echo ""
echo "1/3  Qwen chat completion"
echo "──────────────────────────────────────"
python "$SCRIPT_DIR/smoke_qwen.py"

echo ""
echo "2/3  Wan image generation"
echo "──────────────────────────────────────"
python "$SCRIPT_DIR/smoke_image.py"

echo ""
echo "3/3  Wan i2v task creation + poll"
echo "──────────────────────────────────────"
python "$SCRIPT_DIR/smoke_i2v.py"

echo ""
echo "══════════════════════════════════════"
echo " All smoke tests passed"
echo "══════════════════════════════════════"
