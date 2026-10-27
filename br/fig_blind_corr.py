#!/usr/bin/env python3
"""Dumbbell chart: per design, share of signoff slew/cap violators that the post-GR estimate calls safe (estimate below
the limit), with the open flow's default wire RC (hollow) and with correlated per-layer R and C from placement on
(filled); right margin: violators at signoff without post-GR repair, default -> correlated.
Data: agents/analysis/residual_cf.json (br/residual_cf.py). Usage: fig_blind_corr.py [--name blind_corr] [--width 7.6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SHORT = {"d1-aes_cipher-000": "AES", "d3-bm64-000": "BM64", "d3-des-000": "DES", "d3-md5-000": "MD5",
         "d3-ocs_blitter-000": "ocs_blitter", "d3-salsa20-000": "salsa20", "d3-y_huff-000": "y_huff",
         "d5-blabla-000": "BlaBla", "d5-chacha-000": "ChaCha", "d5-point_add-000": "point_add",
         "d3b-sha512-000": "SHA-512", "d1-picorv32-016": "PicoRV32"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="blind_corr")
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--width", type=float, default=7.6)
    ap.add_argument("--rowh", type=float, default=0.34)
    ap.add_argument("--fs", type=int, default=0)
    a = ap.parse_args()
    d = json.load(open(os.path.join(F.ROOT, "agents", "analysis", "residual_cf.json")))
    rows = [(b, v["default"], v["ORFS RC"]) for b, v in d.items() if v.get("default") and v.get("ORFS RC")]
    rows.sort(key=lambda r: r[2]["blind"])
    F.setup_style()
    F.FS = F.FS + a.fs
    n = len(rows)
    fig = plt.figure(figsize=(a.width, a.rowh * n + 1.6))
    ax = fig.add_axes([0.2, 0.25, 0.56, 0.64])
    for i, (b, dft, cor) in enumerate(rows):
        x0, x1 = 100 * dft["blind"], 100 * cor["blind"]
        ax.plot([x1, x0], [i, i], color=F.AXIS, lw=2, zorder=1, solid_capstyle="round")
        ax.scatter([x0], [i], s=70, facecolors=F.SURFACE, edgecolors=F.GREY, linewidths=1.8, zorder=3)
        ax.scatter([x1], [i], s=70, color=F.INK, zorder=4)
        ax.text(103, i, f"{dft['V']:,} → {cor['V']:,}", va="center", ha="left", fontsize=F.FS - 3, color=F.INK2,
                clip_on=False)
    ax.set_yticks(range(n))
    ax.set_yticklabels([SHORT.get(b, b) for b, _, _ in rows], fontsize=F.FS - 2, color=F.INK)
    ax.set_xlim(-2, 101)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=F.FS - 3)
    ax.set_xlabel("signoff violators the post-GR estimate calls safe", fontsize=F.FS - 2, color=F.INK2)
    ax.grid(axis="x", color=F.GRID, lw=0.8)
    ax.grid(axis="y", visible=False)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(F.AXIS)
    ax.tick_params(axis="y", length=0)
    ax.text(103, n - 0.3, "violators\n(no post-GR repair)", va="bottom", ha="left", fontsize=F.FS - 4, color=F.MUTED,
            clip_on=False)
    # legend
    lx = fig.add_axes([0.2, 0.0, 0.56, 0.07])
    lx.axis("off")
    lx.scatter([0.02], [0.5], s=60, facecolors=F.SURFACE, edgecolors=F.GREY, linewidths=1.8)
    lx.text(0.05, 0.5, "default wire RC (LEF)", va="center", fontsize=F.FS - 3, color=F.INK2)
    lx.scatter([0.52], [0.5], s=60, color=F.INK)
    lx.text(0.55, 0.5, "correlated per-layer R and C", va="center", fontsize=F.FS - 3, color=F.INK2)
    lx.set_xlim(0, 1)
    lx.set_ylim(0, 1)
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, f"{a.name}.png")
    fig.savefig(out, dpi=200, facecolor=F.SURFACE)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
