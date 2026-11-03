#!/usr/bin/env python3
"""IO phase 2, for the record (not registered): what the 10 blind readers did in the shared session scratchpad.

The readers ran as sub-agents of one coordinator session and shared its scratchpad folder. This scans each reader's
transcript (tool calls and tool outputs) and reports: tool calls and model; every scratchpad path it named; which
paths more than one reader named; which readers listed the scratchpad root (it also holds older files of other
sessions); and whether any of the four case designs' names, or any other design directory name of the repository (except
"des"), appears as a substring in any tool output the reader saw.

usage: reader_scratch.py READER_MAP.tsv TASKS_DIR SCRATCHPAD DESIGNS_DIR OUT.json
READER_MAP.tsv: lines "<packet> <agent id>"; transcripts are TASKS_DIR/<agent id>.output (JSON lines).
"""
import json
import os
import re
import sys

RMAP, TASKS, S, DESIGNS, OUT = sys.argv[1:6]
CASE_DESIGNS = ["cic_decimator", "xtea", "usb_cdc_core", "wbqspiflash"]
designs = sorted(os.listdir(DESIGNS))
# substring match, case-insensitive (file names embed design names, e.g. "<study>_<design>_..."); "des" is skipped
# because it occurs inside ordinary words (nodes, modes)
name_pat = re.compile("(" + "|".join(re.escape(d) for d in sorted(designs, key=len, reverse=True) if d != "des") + ")",
                      re.I)
path_pat = re.compile(re.escape(S) + r"(?:/[^\s\"'\\;|&)<>`]*)?")
rep = {"readers": {}, "shared_paths": {}}
users = {}
for line in open(RMAP):
    P, A = line.split()
    calls, models, paths, root_listings, names = 0, set(), set(), [], {}
    cmds = {}
    for raw in open(os.path.join(TASKS, f"{A}.output")):
        try:
            o = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        m = o.get("message") or {}
        if not isinstance(m, dict):
            continue
        if m.get("model"):
            models.add(m["model"])
        for c in m.get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                calls += 1
                inp = c.get("input") or {}
                cmd = inp.get("command", "") if isinstance(inp, dict) else ""
                cmds[c.get("id")] = cmd
                for p in path_pat.findall(json.dumps(inp).replace("\\/", "/")):
                    rel = p[len(S):].strip("/").rstrip(".,")
                    paths.add(rel)
                    users.setdefault(rel, set()).add(P)
                for seg in re.split(r"&&|;|\n|\|", cmd or ""):
                    seg = seg.strip()
                    if re.match(r"^ls\b", seg):
                        before = cmd.split(seg)[0]
                        cds = re.findall(r"cd\s+(\S+)", before)
                        tgt = (seg.split()[-1] if len(seg.split()) > 1 and not seg.split()[-1].startswith("-")
                               else (cds[-1] if cds else ""))
                        if tgt.rstrip("/") == S:
                            root_listings.append(seg.replace(S, "$SCRATCH"))
            elif c.get("type") == "tool_result":
                for d in name_pat.findall(json.dumps(c.get("content"))):
                    names[d.lower()] = names.get(d.lower(), 0) + 1
    rep["readers"][P] = {"agent": A, "tool_calls": calls, "models": sorted(models), "scratch_paths": sorted(paths),
                         "listed_scratch_root": root_listings,
                         "case_design_names_in_tool_outputs": {k: v for k, v in names.items() if k in CASE_DESIGNS},
                         "other_design_names_in_tool_outputs": {k: v for k, v in names.items() if k not in CASE_DESIGNS}}
rep["shared_paths"] = {k or "(scratchpad root)": sorted(v) for k, v in sorted(users.items()) if len(v) > 1}
json.dump(rep, open(OUT, "w"), indent=1)
for P, r in rep["readers"].items():
    print(P, r["tool_calls"], r["models"], "root listed:", bool(r["listed_scratch_root"]),
          "case names:", r["case_design_names_in_tool_outputs"] or "none",
          "other names:", r["other_design_names_in_tool_outputs"] or "none")
print("paths named by more than one reader:", rep["shared_paths"])
