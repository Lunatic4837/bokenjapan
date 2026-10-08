#!/bin/bash
# Rebuild PR #12 Phase D changes from the PR head, deterministically.
set -e
cd "$(git rev-parse --show-toplevel)"
git checkout -- . && git clean -fdq -- akita fukuoka miyagi oita yamaguchi
python3 scripts/phase_d/wire_photos.py
python3 scripts/phase_d/apply_line4.py | { grep -v "^left sample \[\]" || true; }
python3 scripts/phase_d/fix_misc.py
python3 scripts/phase_d/names/apply_en2.py
python3 scripts/phase_d/compact.py
