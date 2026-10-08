#!/bin/bash
# Rebuild PR #12 Phase D changes from the PR head, deterministically.
set -e
cd /workspace/p1/pr12-work
git checkout -- . && git clean -fdq -- akita fukuoka miyagi oita yamaguchi
python3 /workspace/p1/phase-d/wire_photos.py
python3 /workspace/p1/phase-d/apply_line4.py | grep -v "^left sample \[\]"
python3 /workspace/p1/phase-d/fix_misc.py
