#!/usr/bin/env python3
"""Experiment E (Addendum 42) leak test: every blind packet must pass before it is handed to a reader.

For each packet <packets>/<pid>/<rung>/:
  (0) allowlist: every file must match an allowed packet path, and MANIFEST.json must list exactly the files present
      with matching SHA-256;
  every file (each .gz decompressed) is then checked for
  (1) any design/family name of the record (substring, case-insensitive; short names as whole tokens);
  (2) run tags (ers-/erk-/smoke- tags, the source's record tag, tag-like strings x..-<design>-NNN);
  (3) file paths (/work/, /home/, results/, designs/, /runs/);
  (4) outcome-file names (chain.json, chains.json, E_RESULT, score.json, packet_key, labels.csv, pairs.csv);
  (5) every original (pre-pseudonym) name of the packet's own design that is not a generic tool name (word parts of
      >= 4 characters, from <private>/names/<pid>.json), as whole tokens.
Self-test first, every time: a copy of one packet gets planted leaks (the design name and an original port name inside
a gzipped per-net dump, a /work/ path inside a gzipped STA report, and an unlisted extra file); the test must report
all of them, else it exits 2 without passing anything. Exit 1 on any leak in a real packet.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

DESIGNS = ["zipdiv", "cic_decimator", "decimator", "wbqspiflash", "qspiflash", "picorv32", "picorv", "xtea", "usb_cdc",
           "cdc_core", "ocs_blitter", "blitter", "clip16", "aes_cipher", "y_huff", "blabla", "chacha", "salsa20",
           "sha512", "ldpcenc", "point_add", "crc_pipe"]
TOKENS = {"spm", "md5", "bm64", "apu", "ppu", "des", "APU", "PPU", "MD5", "SPM", "BM64", "DES"}
PATHS = ["/work/", "/home/", "results/", "designs/", "/runs/", "librelane/designs"]
OUTCOME = ["chain.json", "chains.json", "e_result", "score.json", "packet_key", "labels.csv", "pairs.csv", "smoke-ers"]
TAGLIKE = re.compile(r"\b(x[0-9a-z]{1,4}-[a-z0-9_]+-\d{3}|er[sk]-[a-z0-9_]+-\d\d)\b", re.I)
GENERIC = re.compile(r"^(_\d+_|net\d+|n\d+|clknet_.*|clkbuf_.*|clkload\d+|hold\d+|input\d+|output\d+|fanout\d+|wire\d+|"
                     r"max_cap\d+|max_length\d+|load_slew\d+|rebuffer\d+|split\d+|place\d+|ANTENNA_.*|FILLER_.*|TAP_.*|"
                     r"PHY_EDGE_ROW_.*|PHY_.*|clone\d+|delaybuf\d+)$")
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ALLOWED_WORDS = set("""clock reset data mode done busy valid ready start enable input output clk rst state count
counter addr address write read wdata rdata error load shift carry sum diff result value index active idle stall
flush vpwr vgnd vccd1 vssd1 vdd vss""".split())
ALLOWED_PATHS = [re.compile(p) for p in (
    r"^MANIFEST\.json$", r"^contract\.json$", r"^metrics\.json$", r"^reports/summary\.txt$",
    r"^reports/checks/(min|nom|max)_(tt_025C_1v80|ss_100C_1v60|ff_n40C_1v95)\.checks\.rpt$",
    r"^nets/(postgrt|signoff)\.jsonl\.gz$", r"^nets/connectivity\.json\.gz$", r"^nets/drv\.json$",
    r"^layout/final\.def\.gz$", r"^layout/final\.nl\.v\.gz$", r"^layout/final\.sdc$",
    r"^layout/spef/(min|nom|max)\.spef\.gz$",
    r"^sta/postpnr/((min|nom|max)_(tt_025C_1v80|ss_100C_1v60|ff_n40C_1v95)/)?[a-z_.]+\.rpt\.gz$",
    r"^sta/postgrt/[a-z_.]+\.rpt\.gz$")]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def forbidden_tokens(names):
    out = set()
    for n in names:
        c = n.replace("\\", "")
        if GENERIC.match(c) or c in ("top", "clk"):
            continue
        for w in WORD.findall(c):
            if len(w) >= 4 and not GENERIC.match(w) and w.lower() not in ALLOWED_WORDS and not w.isdigit():
                out.add(w)
    return out


def scan(pdir, info, ftok):
    hits = []
    files = {}
    for dp, _, fs in os.walk(pdir):
        for f in fs:
            p = os.path.join(dp, f)
            files[os.path.relpath(p, pdir)] = p
    for rel in sorted(files):
        if not any(r.match(rel) for r in ALLOWED_PATHS):
            hits.append((rel, "not-allowlisted"))
    try:
        man = json.load(open(os.path.join(pdir, "MANIFEST.json")))["files"]
        listed = set(man)
        present = set(files) - {"MANIFEST.json"}
        for rel in sorted(present ^ listed):
            hits.append((rel, "manifest-mismatch"))
        for rel in sorted(present & listed):
            if man[rel]["sha256"] != sha(files[rel]):
                hits.append((rel, "manifest-hash"))
    except Exception as e:
        hits.append(("MANIFEST.json", f"unreadable {e}"))
    for rel, p in sorted(files.items()):
        try:
            t = gzip.open(p, "rt", errors="replace").read() if p.endswith(".gz") else open(p, errors="replace").read()
        except Exception as e:
            hits.append((rel, f"unreadable {e}"))
            continue
        low = t.lower()
        for d in DESIGNS:
            if d in low:
                hits.append((rel, "design:" + d))
        toks = set(WORD.findall(t))
        for d in sorted(TOKENS & toks):
            hits.append((rel, "design-token:" + d))
        for s in PATHS + OUTCOME + [info["record_tag"].lower(), info["source"].lower()]:
            if s.lower() in low:
                hits.append((rel, "string:" + s))
        for mt in TAGLIKE.findall(t):
            hits.append((rel, "tag:" + str(mt)))
        for w in sorted(toks & ftok)[:5]:
            hits.append((rel, "name:" + w))
    return hits


def self_test(pdir, info, ftok):
    """Plant leaks in a copy of a real packet; every planted kind must be reported."""
    tmp = tempfile.mkdtemp(prefix="e_leak_selftest_")
    try:
        cp = os.path.join(tmp, "p")
        shutil.copytree(pdir, cp)
        port = sorted(ftok)[0] if ftok else "planted_port_name"
        ftok = set(ftok) | {port}
        dump = os.path.join(cp, "nets", "postgrt.jsonl.gz")
        txt = gzip.open(dump, "rt").read() + json.dumps({"net": port, "note": info["design"]}) + "\n"
        with gzip.open(dump, "wt") as f:
            f.write(txt)
        sta = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(cp, "sta")) for f in fs)
        if sta:
            t = gzip.open(sta[0], "rt").read() + "\nread /work/designs/top/src/top.v\n"
            with gzip.open(sta[0], "wt") as f:
                f.write(t)
        open(os.path.join(cp, "notes.txt"), "w").write("x\n")
        hits = scan(cp, info, ftok)
        kinds = {h[1].split(":")[0] for h in hits}
        need = {"name", "design", "not-allowlisted", "manifest-hash", "manifest-mismatch"} | ({"string"} if sta else set())
        missing = need - kinds
        print(f"[leak] self-test on a copy of {os.path.basename(os.path.dirname(pdir))}: planted leaks "
              f"{'all caught' if not missing else 'MISSED ' + str(sorted(missing))} ({len(hits)} hits)", flush=True)
        return not missing
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("packets")
    ap.add_argument("--private", required=True)
    ap.add_argument("--only", default=None, help="comma list of packet ids (default: all in the key)")
    a = ap.parse_args()
    key = json.load(open(os.path.join(a.private, "packet_key.json")))["packets"]
    pids = [p for p in sorted(os.listdir(a.packets)) if os.path.isdir(os.path.join(a.packets, p)) and p in key]
    if not pids:
        print("[leak] no packets")
        return 1
    mains = [p for p in pids if key[p]["kind"] == "main" and os.path.isdir(os.path.join(a.packets, p, "rung2"))]
    st = min(mains, key=lambda p: sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in
                                      os.walk(os.path.join(a.packets, p, "rung2")) for f in fs))
    ft = forbidden_tokens(json.load(open(os.path.join(a.private, "names", st + ".json"))))
    if not self_test(os.path.join(a.packets, st, "rung2"), key[st], ft):
        print("[leak] SELF-TEST FAILED: the test cannot be trusted; nothing passes")
        return 2
    if a.only:
        pids = [p for p in pids if p in a.only.split(",")]
    bad = n = 0
    for pid in pids:
        info = key[pid]
        ftok = forbidden_tokens(json.load(open(os.path.join(a.private, "names", pid + ".json"))))
        for rung in sorted(os.listdir(os.path.join(a.packets, pid))):
            pdir = os.path.join(a.packets, pid, rung)
            if not os.path.isdir(pdir):
                continue
            hits = scan(pdir, info, ftok)
            n += 1
            if hits:
                bad += 1
                print(f"LEAK {pid}/{rung} ({info['kind']}): {len(hits)} hits, e.g. {hits[:6]}", flush=True)
            else:
                print(f"ok   {pid}/{rung} ({info['kind']}): {len(ftok)} original names checked", flush=True)
    print(f"[leak] {n} packet views, {bad} with leaks")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
