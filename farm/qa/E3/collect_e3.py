#!/usr/bin/env python3
"""Fetch an E3 run's artifact (analyze.yml on qa-e3-md5) and keep only the small files: the mode's JSON summary,
sby logs/status of each formal run, and simulator logs. Usage: collect_e3.py <run_id> <dest_dir>"""
import io
import json
import os
import subprocess
import sys
import zipfile

REPO = "Avi-Patel-1/beforeroute-farm"
KEEP_EXT = (".json", ".sby", ".sv", ".txt", ".log", ".yw")
KEEP_MAX = 2_000_000


def main():
    run_id, dest = sys.argv[1], sys.argv[2]
    os.makedirs(dest, exist_ok=True)
    arts = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/actions/runs/{run_id}/artifacts"]))["artifacts"]
    meta = {"run_id": run_id, "artifacts": []}
    for a in arts:
        data = subprocess.check_output(["gh", "api", f"repos/{REPO}/actions/artifacts/{a['id']}/zip"])
        z = zipfile.ZipFile(io.BytesIO(data))
        kept = []
        for info in z.infolist():
            n = info.filename
            if info.is_dir() or "obj_dir" in n or "/model/" in n or n.endswith((".vvp", ".v", ".smt2", ".il", ".aig", ".vcd")):
                continue
            if n.endswith(KEEP_EXT) and info.file_size <= KEEP_MAX:
                path = os.path.join(dest, a["name"], n)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "wb").write(z.read(n))
                kept.append(n)
        meta["artifacts"].append({"name": a["name"], "id": a["id"], "zip_bytes": len(data), "kept": len(kept),
                                  "created_at": a["created_at"]})
    json.dump(meta, open(os.path.join(dest, "_collect.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
