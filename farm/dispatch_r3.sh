#!/usr/bin/env bash
# Round 3 dispatcher (idempotent; state in results/.r3_dispatched): when a held-out v4 model exists ->
# conformal thresholds -> commit model+thresholds -> dispatch tgt050-70, thr500-70, thr<lambda>-70 arms.
cd "$(dirname "$0")/.."
declare -A BASE=( [salsa20]=d3-salsa20-000 [des]=d3-des-000 [y_huff]=d3-y_huff-000 [ocs_blitter]=d3-ocs_blitter-000 [bm64]=d3-bm64-000 [md5]=d3-md5-000 )
declare -A DNAME=( [salsa20]=salsa20 [des]=des [y_huff]=y_huff [ocs_blitter]=ocs_blitter [bm64]=BM64 [md5]=md5 )
STATE=results/.r3_dispatched; touch $STATE
push() { for i in 1 2 3 4 5; do git push -q origin main && return 0; git pull -q --rebase origin main; sleep 3; done; return 1; }
end=$(( $(date +%s) + ${1:-9000} ))
while [ $(date +%s) -lt $end ]; do
  for d in salsa20 des y_huff ocs_blitter bm64 md5; do
    grep -qx "$d" $STATE && continue
    m=models/model_holdout_${d}_v4.txt
    [ -f "$m" ] || continue
    python3 br/conformal.py --model $m --exclude-design ${DNAME[$d]} --alpha 0.10 --out models/conformal/${d}_run_alpha10.json > /dev/null 2>&1
    python3 br/conformal.py --model $m --exclude-design ${DNAME[$d]} --alpha 0.20 --balance-designs --out models/conformal/${d}_design_alpha20.json > /dev/null 2>&1
    L1=$(python3 -c "import json;print(int(round(json.load(open('models/conformal/${d}_run_alpha10.json'))['lambda']*1000)))" 2>/dev/null || echo 500)
    L2=$(python3 -c "import json;print(int(round(json.load(open('models/conformal/${d}_design_alpha20.json'))['lambda']*1000)))" 2>/dev/null || echo 500)
    git add "$m" models/reg_holdout_${d}_v4.txt models/conformal 2>/dev/null
    git commit -qm "Round 3: held-out model + conformal thresholds for $d (run a=0.10: $L1, design a=0.20: $L2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG" && push
    ARMS="\"tgt050-70\",\"thr500-70\""
    [ "$L1" != "500" ] && ARMS="$ARMS,\"thr$(printf %03d $L1)-70\""
    [ "$L2" != "$L1" ] && [ "$L2" != "500" ] && ARMS="$ARMS,\"thr$(printf %03d $L2)-70\""
    if gh workflow run hero.yml -R Avi-Patel-1/beforeroute-farm --ref main -f base_tag=${BASE[$d]} -f "arms=[$ARMS]" -f model=$m >/dev/null; then
      echo "$d" >> $STATE; echo "$(date +%H:%M) $d: lambda run/a10=$L1 design/a20=$L2 -> dispatched [$ARMS] on ${BASE[$d]}"
    fi
  done
  [ $(wc -l < $STATE) -ge 6 ] && break
  sleep 60
done
echo "$(date +%H:%M) dispatch_r3 exit ($(wc -l < $STATE)/6 done)"
