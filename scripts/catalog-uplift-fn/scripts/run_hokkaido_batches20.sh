#!/bin/bash
set -euo pipefail
cd /workspace/p1/data/catalog-uplift/scripts
REPO=/workspace/p1/bokenjapan-cutover
BATCH=20
mapfile -t ALL < <(python3 - <<'PY'
import json
from pathlib import Path
hubs=json.load(open('/workspace/p1/data/catalog-uplift/hubs/hokkaido-hub-codes.json'))['hubs']
root=Path('/workspace/p1/bokenjapan-cutover/hokkaido')
for slug,h in sorted(hubs.items()):
  if h.get('skip') or h.get('nt'):
    continue
  html=(root/slug/'index.html').read_text(encoding='utf-8',errors='replace')
  if '<h2>Dining</h2>' not in html:
    print(slug)
PY
)
echo "remaining ${#ALL[@]}"
i=0
batch_n=11
while [ $i -lt ${#ALL[@]} ]; do
  python3 - <<'PY'
import os,sys
st=os.statvfs('/workspace/p1')
avail=(st.f_bavail*st.f_frsize)/1024**3
print(f'DISK {avail:.2f} GiB')
if avail < 8.0:
  print('PAUSE_DISK_UNDER_8GiB'); sys.exit(2)
PY
  chunk=("${ALL[@]:i:BATCH}")
  echo "=== BATCH $batch_n (${#chunk[@]}): ${chunk[*]} ==="
  python3 run_hokkaido_capped.py "${chunk[@]}"
  cd "$REPO"
  git add hokkaido media
  if ! git diff --cached --quiet; then
    git commit -m "Hokkaido wave${batch_n}: Stay+Dining uplift (${#chunk[@]} munis)."
    git -c credential.helper='!gh auth git-credential' push origin staging/aomori-hokkaido
  fi
  cd /workspace/p1/data/catalog-uplift/scripts
  i=$((i+BATCH))
  batch_n=$((batch_n+1))
done
echo ALL_WAVES_DONE
