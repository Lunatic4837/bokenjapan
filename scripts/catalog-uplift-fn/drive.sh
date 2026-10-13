#!/bin/bash
# usage: drive.sh pref  -> runs remaining munis in batches of 10, commit+push to staging/<pref>
set -u
PREF=$1; WT=/workspace/p1/wt-$PREF; export FN_ROOT=$WT
cd /workspace/p1/fn-uplift/scripts
ALL=$(python3 -c "import json;print(' '.join(sorted(json.load(open('../hubs/$PREF-hub-codes.json'))['hubs'])))")
DONE=$(python3 -c "import json,os;p='../out/$PREF-wave-report.json';print(' '.join(json.load(open(p))['hubs']) if os.path.exists(p) else '')")
TODO=(); for s in $ALL; do [[ " $DONE " == *" $s "* ]] || TODO+=($s); done
echo "todo ${#TODO[@]}"
i=0; while [ $i -lt ${#TODO[@]} ]; do
  B=("${TODO[@]:$i:10}"); i=$((i+10))
  ../.venv/bin/python run_pref.py $PREF "${B[@]}" || { echo FAIL; exit 1; }
  grep -q PAUSE_DISK /dev/null
  cd $WT && git add -A $PREF media && git commit -qm "$PREF: Stay+Dining uplift (${B[*]})" && git push -q origin HEAD:refs/heads/staging/$PREF && echo "pushed $(git rev-parse --short HEAD)"; cd - >/dev/null
  avail=$(df -BG --output=avail /workspace/p1 | tail -1 | tr -dc 0-9); [ "$avail" -lt 8 ] && { echo PAUSE_DISK; exit 2; }
done
echo DRIVE_DONE
