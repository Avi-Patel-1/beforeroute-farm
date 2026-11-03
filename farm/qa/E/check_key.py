#!/usr/bin/env python3
"""Experiment E (Addendum 42): consistency of the PRIVATE packet key with the committed packet set, run before the lock
and before scoring (Codex's audit of make_packets --controls-only, which re-loads and extends an existing key).
Prints counts and verdicts only, never the pid -> source mapping.

  check_key.py --private <reading>/private --packets <reading>/packets --index <reading>/packets_index.json [--json OUT]
Checks:
  1. source list: the main entries' sources are exactly the 35 of the committed farm/qa/E/sources.json, and each main
     entry's design, record_tag, T0 and has_second_point equal that file's;
  2. main pseudonyms: every main pid = "R" + sha256(salt + "main" + source)[:6] with the salt in packet_salt.txt, and its
     packing salt = salt + pid;
  3. controls: exactly 6 renaming and 6 shuffled-view entries; their sources are the first 6 main pseudonyms in sorted
     order (the registered rule); each links (main_packet) to the main pid of its own source; pids, salts and the
     shuffle seed re-derive from the salt as make_packets.py writes them;
  4. no stale or extra entries: the key has exactly 35 + 6 + 6 = 47 entries, one packet folder per entry and one entry
     per packet folder, packets_index.json agrees, and names/<pid>.json exists for each entry (extra name maps listed);
  5. packet hashes: every packet view's MANIFEST.json matches the committed farm/qa/E/packets_manifest.sha256 (82 views).
Exit 1 on any failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def h6(s):
    return "R" + hashlib.sha256(s.encode()).hexdigest()[:6]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", required=True)
    ap.add_argument("--packets", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    key = json.load(open(os.path.join(a.private, "packet_key.json")))["packets"]
    salt = open(os.path.join(a.private, "packet_salt.txt")).read().strip()
    src = {s["source"]: s for s in json.load(open(os.path.join(HERE, "sources.json")))["sources"]}
    checks = {}

    mains = {p: v for p, v in key.items() if v.get("kind") == "main"}
    ren = {p: v for p, v in key.items() if v.get("kind") == "rename"}
    shu = {p: v for p, v in key.items() if v.get("kind") == "shuffle"}
    other = {p: v for p, v in key.items() if v.get("kind") not in ("main", "rename", "shuffle")}
    msrc = sorted(v["source"] for v in mains.values())
    checks["1_main_sources_equal_sources_json"] = msrc == sorted(src) and len(msrc) == len(set(msrc)) == 35
    checks["1_main_fields_equal_sources_json"] = all(
        v["source"] in src and v["design"] == src[v["source"]]["design"]
        and v["record_tag"] == src[v["source"]]["record_tag"] and float(v["T0"]) == float(src[v["source"]]["T0"])
        and bool(v["has_second_point"]) == bool(src[v["source"]].get("second_point")) and v.get("main_packet") is None
        for v in mains.values())
    checks["2_main_pids_rederive"] = all(p == h6(salt + "main" + v["source"]) for p, v in mains.items())
    checks["2_main_salts"] = all(v["salt"] == salt + p and v.get("shuffle_seed") is None for p, v in mains.items())
    main_of = {v["source"]: p for p, v in mains.items()}
    first6 = sorted(main_of.items(), key=lambda kv: kv[1])[:6]
    want_src = sorted(s for s, _ in first6)
    checks["3_six_of_each_control"] = len(ren) == 6 and len(shu) == 6
    checks["3_controls_are_first_6_sorted_main_pids"] = (sorted(v["source"] for v in ren.values()) == want_src
                                                         and sorted(v["source"] for v in shu.values()) == want_src)
    checks["3_main_packet_links"] = all(v.get("main_packet") == main_of.get(v["source"]) for v in list(ren.values()) + list(shu.values()))
    checks["3_rename_pids_salts"] = all(p == h6(salt + "rename" + v["source"]) and v["salt"] == salt + "rename" + p
                                        and v.get("shuffle_seed") is None for p, v in ren.items())
    checks["3_shuffle_pids_salts_seeds"] = all(
        p == h6(salt + "shuffle" + v["source"]) and v["salt"] == salt + "shuffle" + p
        and v.get("shuffle_seed") == int(hashlib.sha256((salt + "seed" + v["source"]).encode()).hexdigest()[:8], 16)
        for p, v in shu.items())
    checks["3_control_fields_copy_their_source"] = all(
        v["design"] == src[v["source"]]["design"] and v["record_tag"] == src[v["source"]]["record_tag"]
        for v in list(ren.values()) + list(shu.values()))
    dirs = sorted(d for d in os.listdir(a.packets) if os.path.isdir(os.path.join(a.packets, d)))
    checks["4_no_unknown_kinds"] = not other
    checks["4_exactly_47_entries"] = len(key) == 47
    checks["4_one_folder_per_entry_and_back"] = sorted(key) == dirs
    idx = json.load(open(a.index))
    checks["4_packets_index_agrees"] = (sorted(idx["main"]) == sorted(mains) and sorted(idx["rung2_rename"]) == sorted(ren)
                                        and sorted(idx["rung2_shuffle"]) == sorted(shu))
    rungs_ok = all(os.path.isdir(os.path.join(a.packets, p, "rung1")) == (v["kind"] == "main")
                   and os.path.isdir(os.path.join(a.packets, p, "rung2")) for p, v in key.items())
    checks["4_views_per_kind"] = rungs_ok
    names = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(a.private, "names")) if f.endswith(".json")}
    checks["4_name_map_per_entry"] = set(key) <= names
    extra_names = sorted(names - set(key))
    man = {}
    for line in open(os.path.join(HERE, "packets_manifest.sha256")):
        s = line.split()
        if len(s) == 2:
            man[s[1]] = s[0]
    want_views = {f"{p}/rung{r}/MANIFEST.json" for p, v in key.items() for r in ((1, 2) if v["kind"] == "main" else (2,))}
    checks["5_manifest_lists_exactly_the_key_views"] = set(man) == want_views
    checks["5_every_view_matches_committed_hash"] = all(
        os.path.exists(os.path.join(a.packets, rel)) and sha(os.path.join(a.packets, rel)) == h for rel, h in man.items())
    ok = all(checks.values())
    out = {"ok": ok, "checks": checks, "counts": {"main": len(mains), "rename": len(ren), "shuffle": len(shu),
                                                  "views_in_manifest": len(man), "extra_name_maps": len(extra_names)},
           "packet_key_sha256": sha(os.path.join(a.private, "packet_key.json")),
           "sources_json_sha256": sha(os.path.join(HERE, "sources.json")),
           "packets_manifest_sha256": sha(os.path.join(HERE, "packets_manifest.sha256"))}
    for k, v in checks.items():
        print(("ok   " if v else "FAIL ") + k)
    print(f"[key] {'CONSISTENT' if ok else 'INCONSISTENT'}: {out['counts']}" +
          (f"; name maps without a key entry: {len(extra_names)}" if extra_names else ""))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
