#!/usr/bin/env python3
"""Iterations to slew/cap closure (Addendum 2), one small panel per base: signal slew/cap violators left after each
route + extract + nine-corner signoff pass, for the signoff-guided loop (pass 1 = the baseline signoff, then repair
exactly the nets that failed and re-run) and for BeforeRoute (pass 1 = the model's top-5% repair, then the same
clean-up loop on what is left). A pass still running is drawn hollow at the last known count.
Same dark style as br/figs_v2.py. Data: br/iterations.py (computed here).

Usage: python3 br/fig_iterations.py --out figures/v2 [--bases d3-des-000,...] [--name iterations]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

LABEL = {"d3-des-000": "DES", "d3-y_huff-000": "y_huff", "d3-ocs_blitter-000": "ocs_blitter", "d3-bm64-000": "BM64",
         "d3-md5-000": "MD5", "d3-salsa20-000": "salsa20", "d3b-sha512-000": "SHA-512", "d3b-ldpcenc-000": "LDPC",
         "d1-picorv32-006": "PicoRV32-006", "d1-picorv32-016": "PicoRV32-016", "d1-aes_cipher-000": "AES"}
R3 = "d3-des-000,d3-y_huff-000,d3-ocs_blitter-000,d3-bm64-000,d3-md5-000,d3-salsa20-000"


def passes_to_close(seq):
    """number of route+signoff passes until 0 left (None if not closed yet); seq passes are 1-based here."""
    for i, p in enumerate(seq, 1):
        if p.get("V") == 0:
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--bases", default=R3)
    ap.add_argument("--name", default="iterations")
    a = ap.parse_args()
    F.setup_style()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as t:
        tmp = t.name
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "iterations.py"),
                    "--bases", a.bases, "--json", tmp], check=True, capture_output=True)
    data = json.load(open(tmp))
    n = len(data)
    fig = plt.figure(figsize=(12.1, 3.6))
    left, right, gap = 0.055, 0.01, 0.012
    w = (1 - left - right - gap * (n - 1)) / n
    nums = {}
    floor = 0.6
    ytop = 2.2 * max([p["V"] for o in data for k in ("loop", "beforeroute") for p in o[k] if "V" in p] + [10])
    for i, o in enumerate(data):
        ax = fig.add_axes([left + i * (w + gap), 0.20, w, 0.56])
        top = 1
        for key, col, mk, lab in (("loop", F.LOOP, "o", "fix what failed"), ("beforeroute", F.GREEN, "*", "BeforeRoute")):
            seq = o[key]
            xs, ys, pend = [], [], []
            for j, p in enumerate(seq, 1):
                if "V" in p:
                    xs.append(j)
                    ys.append(max(p["V"], floor))
                    top = max(top, p["V"])
                elif p.get("status") == "pending":  # stalled / not dispatched = the chain ended; nothing to draw
                    pend.append((j, p["status"]))
            ax.plot(xs, ys, "-", color=col, lw=2.2 if key == "beforeroute" else 1.6, zorder=3)
            ax.plot(xs, ys, mk, color=col, ms=13 if mk == "*" else 7, zorder=4, mec=F.SURFACE if mk == "o" else col)
            for x, st in pend:  # a running pass: hollow marker at the last known count (its outcome is unknown)
                yv = ys[-1] if ys else floor
                ax.plot([x], [yv], mk, mfc=F.SURFACE, mec=col, ms=13 if mk == "*" else 7, mew=1.5, zorder=4)
                if xs:
                    ax.plot([xs[-1], x], [ys[-1], yv], ":", color=col, lw=1.2, zorder=2)
            done = passes_to_close(seq)
            nums.setdefault(o["base"], {})[key] = {"passes_to_close": done, "seq": [(p["arm"], p.get("V"), p.get("cells")) for p in seq]}
        ax.set_yscale("symlog", linthresh=1)
        ax.set_ylim(floor * 0.8, ytop)
        ax.set_xlim(0.5, 5.5)
        ax.set_xticks([1, 2, 3, 4, 5])
        yt = [floor] + [v for v in (1, 10, 100, 1000) if v <= ytop]
        ax.set_yticks(yt)
        ax.set_yticklabels((["0"] + [f"{v:,}" for v in yt[1:]]) if i == 0 else [])
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        lb, ll = nums[o["base"]]["beforeroute"]["passes_to_close"], nums[o["base"]]["loop"]["passes_to_close"]
        s_b = f"{lb}" if lb else f"> {len([p for p in o['beforeroute'] if 'V' in p])}"
        s_l = f"{ll}" if ll else f"> {len([p for p in o['loop'] if 'V' in p])}"
        ax.set_title(f"{LABEL.get(o['base'], o['base'])}", fontsize=F.FS, color=F.INK, pad=24, loc="left")
        ax.text(0.0, 1.02, f"{s_b} vs {s_l} passes", transform=ax.transAxes, ha="left", va="bottom",
                fontsize=F.FS, color=F.INK2)
        ax.axhline(floor, color=F.AXIS, lw=0.8, zorder=1)
    fig.text(0.055, 0.985, "Route + signoff passes until no slew/cap violator is left", fontsize=F.FS + 2, fontweight="semibold",
             color=F.INK, va="top")
    fig.text(0.055, 0.075, "pass (hollow = running)", fontsize=F.FS - 1, color=F.INK2, va="top")
    fig.text(0.004, 0.48, "violators left", fontsize=F.FS - 1, color=F.INK2, rotation=90, va="center")
    F.key_row(fig, [("*", F.GREEN, 13, "BeforeRoute (top 5%, then clean-up)", None, True),
                    ("o", F.LOOP, 7, "fix what failed (pass 1 = baseline)", None, True)], 0.36, 0.04)
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    os.unlink(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
