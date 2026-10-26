#!/usr/bin/env bash
# Poll the farm for finished jobs every 9 minutes for ~110 minutes (re-armed by cycle.sh).
cd "$(dirname "$0")/.."
end=$(( $(date +%s) + 6600 ))
while [ $(date +%s) -lt $end ]; do
  python3 farm/collect.py --repo Avi-Patel-1/beforeroute-farm --results results 2>&1 | tail -1
  echo "$(date +%H:%M) collected=$(ls -d results/d*/ 2>/dev/null | wc -l)"
  sleep 540
done
