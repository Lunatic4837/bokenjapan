#!/bin/bash
# usage: ship.sh PREF "Title" "Body"   (run on branch cursor/hub-rollout-PREF created from latest main)
set -e
PREF=$1; R=/workspace/p1/pr12-work; D=/workspace/p1/phase-d/rollout; LOG=/workspace/p1/quality/phase-f-progress.md
G="git -c user.name=Lunatic4837 -c user.email=hanas_goal@softbank.ne.jp"
cd $R
cp $D/{collect.py,pmatch.py,build_all.py,rules.py,append_noph.py,ship.sh} $D/summary-$PREF.json $D/photo-fix-$PREF.csv $D/noph-$PREF.csv $D/eat-categories-$PREF.csv scripts/phase_f/hub-rollout/
git add $PREF scripts/phase_f/hub-rollout
$G commit -qm "$2"
git -c credential.helper= -c credential.helper='!gh auth git-credential' push -q -u origin HEAD 2>&1 | grep -v '^remote:' || true
URL=$(gh pr create -R Lunatic4837/bokenjapan --base main --head $(git branch --show-current) --title "$2" --body "$3")
N=${URL##*/}
gh pr merge $N -R Lunatic4837/bokenjapan --merge
git fetch -q origin main; NEW=$(git rev-parse FETCH_HEAD); OLD=$(cat /workspace/p1/data/pages-last-published-main-sha.txt)
git diff --quiet HEAD FETCH_HEAD -- . || { echo "tree differs from merged main"; exit 3; }
git diff --name-only --diff-filter=AM $OLD $NEW | grep -v '^scripts/' > /tmp/chg-$PREF.txt
P=/workspace/p1/gh-pages-pub; cd $P
git fetch -q origin gh-pages; git merge-base --is-ancestor FETCH_HEAD HEAD
n=0; while read f; do mkdir -p $(dirname $f); cp $R/_site/$f $f; n=$((n+1)); done < /tmp/chg-$PREF.txt
git add -A; $G commit -qm "Publish slim site from main ${NEW:0:10}"
git -c credential.helper= -c credential.helper='!gh auth git-credential' push -q origin gh-pages:gh-pages
GP=$(git rev-parse HEAD); echo $NEW > /workspace/p1/data/pages-last-published-main-sha.txt
echo "- $(date +%H:%M) ${PREF^^}: PR #$N main ${NEW:0:10}, gh-pages ${GP:0:10} ($n files)" >> $LOG
echo "PR=$N MAIN=$NEW GP=$GP FILES=$n"
