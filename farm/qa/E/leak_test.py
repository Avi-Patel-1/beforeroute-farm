#!/usr/bin/env python3
"""Experiment E (Addendum 42) leak test: every blind packet must pass before it is handed to a reader.

For each packet directory <packets>/<pid>/<rung>/ (and any other tree given), every file (gzip decompressed) is checked
for: (1) any design/family name of the record (substring, case-insensitive); (2) run tags (ers-/erk-/smoke- and the
record tag of the source) and tag-like strings of the record (x[0-9a-z]{1,4}-<design>-NNN); (3) file paths (/work/,
/home/, results/, designs/, runs/); (4) outcome-file names (chain.json, chains.json, E_RESULT, score.json,
packet_key, labels.csv, pairs.csv); (5) every original (pre-pseudonym) name of the packet's own design that is not a
generic tool name (word parts of >= 4 characters, from <private>/names/<pid>.json), as whole tokens.
Exit 1 on any hit. Prints a one-line receipt per packet.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys

DESIGNS = ["zipdiv", "cic_decimator", "decimator", "wbqspiflash", "qspiflash", "picorv32", "picorv", "xtea", "usb_cdc",
           "cdc_core", "ocs_blitter", "blitter", "md5", "clip16", "aes_cipher", "y_huff", "blabla", "bm64", "chacha",
           "salsa20", "sha512", "ldpcenc", "point_add", "spm", "crc_pipe"]
# names that can occur legitimately as substrings of tool/library text in some files are checked as tokens instead
TOKEN_ONLY = {"spm", "md5", "bm64", "apu", "ppu", "des", "blabla"}
EXTRA_TOKENS = {"APU", "PPU", "des"}
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


def texts(root):
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                if f.endswith(".gz"):
                    yield p, gzip.open(p, "rt", errors="replace").read()
                else:
                    yield p, open(p, errors="replace").read()
            except Exception as e:
                yield p, f"<<unreadable {e}>>"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("packets")
    ap.add_argument("--private", required=True)
    a = ap.parse_args()
    key = json.load(open(os.path.join(a.private, "packet_key.json")))["packets"]
    bad = 0
    n = 0
    for pid in sorted(os.listdir(a.packets)):
        pdir = os.path.join(a.packets, pid)
        if not os.path.isdir(pdir) or pid not in key:
            continue
        info = key[pid]
        names = json.load(open(os.path.join(a.private, "names", pid + ".json")))
        ftok = forbidden_tokens(names)
        hits = []
        for p, t in texts(pdir):
            low = t.lower()
            for d in DESIGNS:
                if d in TOKEN_ONLY:
                    continue
                if d in low:
                    hits.append((p, "design:" + d))
            toks = set(WORD.findall(t))
            for d in TOKEN_ONLY | EXTRA_TOKENS:
                if d in toks or d.upper() in toks:
                    hits.append((p, "design-token:" + d))
            for s in PATHS + OUTCOME + [info["record_tag"].lower(), info["source"].lower()]:
                if s.lower() in low:
                    hits.append((p, "string:" + s))
            for mt in TAGLIKE.findall(t):
                hits.append((p, "tag:" + mt))
            inter = toks & ftok
            for w in sorted(inter)[:5]:
                hits.append((p, "name:" + w))
        n += 1
        if hits:
            bad += 1
            print(f"LEAK {pid} ({info['kind']}): {len(hits)} hits, e.g. {hits[:6]}")
        else:
            print(f"ok   {pid} ({info['kind']}): {sum(1 for _ in texts(pdir))} files, {len(ftok)} original names checked")
    print(f"[leak] {n} packets, {bad} with leaks")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
