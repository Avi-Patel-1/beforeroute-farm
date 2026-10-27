#!/usr/bin/env bash
# Round 4 dispatcher (idempotent): when the held-out model exists, commit it and dispatch the arms.
cd "$(dirname "$0")/.."
STATE=results/.r4_dispatched; touch $STATE
push() { for i in 1 2 3 4 5; do git push -q origin main && return 0; git pull -q --rebase origin main; sleep 3; done; return 1; }
end=$(( $(date +%s) + 5400 ))
while [ $(date +%s) -lt $end ]; do
  for pair in sha512:d3b-sha512-000 ldpcenc:d3b-ldpcenc-000; do
    d=${pair%%:*}; b=${pair#*:}
    grep -qx "$d" $STATE && continue
    m=models/model_holdout_${d}_v4.txt
    [ -f "$m" ] || continue
    git add "$m" models/reg_holdout_${d}_v4.txt farm/lists/$b farm/advance.py 2>/dev/null
    git commit -qm "Round 4: held-out model for $d; signoff-loop pass-1 list for $b

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG"; push
    if gh workflow run hero.yml -R Avi-Patel-1/beforeroute-farm --ref main -f base_tag=$b -f 'arms=["rerun","uni50","uni70","det050-70","tgt050-70","thr500-70","exp100-70","lst-sgl1-70"]' -f model=$m >/dev/null; then
      echo "$d" >> $STATE; echo "$b lst-sgl1-70" >> results/.advance_dispatched; echo "$(date +%H:%M) dispatched Round 4 arms on $b"
    fi
  done
  [ $(wc -l < $STATE) -ge 2 ] && break
  sleep 45
done
echo "$(date +%H:%M) dispatch_r4 exit"
