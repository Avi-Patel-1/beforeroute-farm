#!/usr/bin/env python3
"""Split packed results not yet on the Mac into device_commit_files batches (<= 90 MB each).
Usage: sync_batches.py --have mac_results.txt --out-prefix /scratch/sync_
"""
import argparse, glob, json, os
ap = argparse.ArgumentParser(); ap.add_argument("--have", required=True); ap.add_argument("--out-prefix", required=True)
ap.add_argument("--packed", default="/mnt/user-data/outputs/beforeroute/results")
ap.add_argument("--dest", default="/Users/avipatel/Documents/ChatGPT/BusinessChallenge/beforeroute/results")
a = ap.parse_args()
have = set(open(a.have).read().split())
files = sorted(f for f in glob.glob(os.path.join(a.packed, "*.tar.gz")) if os.path.basename(f)[:-7] not in have)
batches, cur, size = [], [], 0
for f in files:
    s = os.path.getsize(f)
    if cur and (size + s > 90e6 or len(cur) >= 45):
        batches.append(cur); cur, size = [], 0
    cur.append({"stagedPath": f, "devicePath": os.path.join(a.dest, os.path.basename(f))}); size += s
if cur: batches.append(cur)
for i, b in enumerate(batches):
    p = f"{a.out_prefix}{i}.json"; json.dump(b, open(p, "w"))
    print(p, len(b), "files", round(sum(os.path.getsize(x["stagedPath"]) for x in b) / 1e6, 1), "MB")
print(len(files), "files to sync")
