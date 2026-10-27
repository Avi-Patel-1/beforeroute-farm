#!/usr/bin/env python3
"""Real-layout panels from routed DEFs: placed cells (faint), routed wires of chosen nets, and cells a repair inserted.

Typical use (one row of panels, same design, same checkpoint):
  fig_layout.py --panel "No repair:results/d3-des-000-rerun" --panel "Uniform 70%:results/d3-des-000-uni70" ...
                [--baseline results/d3-des-000-rerun] --out figures/v2 --name layout_des
Each panel directory must hold final.def.gz (routed DEF, kept by br/arms.py) and labels.json (signoff labels).
Drawn per panel: every placed standard cell as a faint dot; the routed wires of the nets that still violate max-slew/cap
at signoff (signal nets) in red; cells that exist in the panel but not in the baseline (inserted by the repair) in the
panel's colour; optional --flags <json list of nets> drawn in green on the baseline panel (the model's list).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

FILL_RE = re.compile(r"(FILLER|fill|decap|tap|PHY_EDGE|TAP_|WELLTAP|ANTENNA|diode)", re.I)


def parse_def(path, want_nets=None):
    """-> dict(dbu, die, cells={name: (macro, x, y)}, wires={net: [((x0,y0),(x1,y1)), ...]}) (coordinates in um).
    Only nets in want_nets get their routing parsed (None = none)."""
    op = gzip.open if path.endswith(".gz") else open
    dbu, die, cells, wires = 1000.0, None, {}, {}
    sec, cur, last = None, None, None
    with op(path, "rt") as f:
        for line in f:
            s = line.strip()
            if s.startswith("UNITS DISTANCE MICRONS"):
                dbu = float(s.split()[3])
            elif s.startswith("DIEAREA"):
                nums = [float(v) for v in re.findall(r"-?\d+", s)]
                die = (nums[0] / dbu, nums[1] / dbu, nums[2] / dbu, nums[3] / dbu)
            elif s.startswith("COMPONENTS "):
                sec = "C"
            elif s.startswith("END COMPONENTS"):
                sec = None
            elif s.startswith("NETS "):
                sec = "N"
            elif s.startswith("END NETS"):
                sec = None
            elif sec == "C" and s.startswith("- "):
                t = s.split()
                m = re.search(r"\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)", s)
                if m:
                    cells[t[1]] = (t[2], int(m.group(1)) / dbu, int(m.group(2)) / dbu)
            elif sec == "N":
                if s.startswith("- "):
                    name = s.split()[1]
                    cur = name if (want_nets is not None and name in want_nets) else None
                    last = None
                    if cur:
                        wires.setdefault(cur, [])
                if cur and ("ROUTED" in s or s.startswith("NEW") or s.startswith("(")):
                    if "ROUTED" in s or s.startswith("NEW"):
                        last = None
                    for mm in re.finditer(r"\( (\*|-?\d+) (\*|-?\d+)(?: -?\d+)? \)", s):
                        x = last[0] if (mm.group(1) == "*" and last) else (int(mm.group(1)) / dbu if mm.group(1) != "*" else None)
                        y = last[1] if (mm.group(2) == "*" and last) else (int(mm.group(2)) / dbu if mm.group(2) != "*" else None)
                        if x is None or y is None:
                            continue
                        if last is not None and (x, y) != last:
                            wires[cur].append((last, (x, y)))
                        last = (x, y)
                if s.endswith(";"):
                    cur = None
    return {"dbu": dbu, "die": die, "cells": cells, "wires": wires}


def violators(run_dir):
    lab = json.load(open(os.path.join(run_dir, "labels.json")))
    return {r["net"] for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", action="append", required=True, help="'Title:run_dir[:colour]'")
    ap.add_argument("--baseline", default=None, help="run dir whose cells count as 'already there' (default: first panel)")
    ap.add_argument("--flags", default=None, help="JSON list of nets (the model's list) drawn in green on the first panel")
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="layout")
    ap.add_argument("--width", type=float, default=12.1)
    ap.add_argument("--title", default="")
    ap.add_argument("--note", default="", help="one line under the panels")
    a = ap.parse_args()
    F.setup_style()
    panels = []
    for p in a.panel:
        parts = p.split(":")
        title, d = parts[0], parts[1]
        col = parts[2] if len(parts) > 2 else F.GREEN
        panels.append((title, d, col))
    base_dir = a.baseline or panels[0][1]
    base = parse_def(os.path.join(base_dir, "final.def.gz"), want_nets=None)
    base_cells = set(base["cells"])
    flags = set(json.load(open(a.flags))) if a.flags else set()
    n = len(panels)
    x0, y0, x1, y1 = base["die"]
    aspect = (y1 - y0) / (x1 - x0)
    pw = (a.width - 0.2) / n
    extra = 0.45 if a.note else 0.0
    fig = plt.figure(figsize=(a.width, pw * aspect + 0.9 + extra))
    nums = {}
    for i, (title, d, col) in enumerate(panels):
        V = violators(d)
        want = V | (flags if i == 0 else set())
        L = parse_def(os.path.join(d, "final.def.gz"), want_nets=want)
        H = pw * aspect + 0.9 + extra
        ax = fig.add_axes([0.01 + i * (0.98 / n), (0.02 * (pw * aspect + 0.9) + extra) / H, 0.98 / n - 0.01, (pw * aspect) / H * 0.97])
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#0b0b0b", ec=F.AXIS, lw=0.8, zorder=0))
        real = {k: v for k, v in L["cells"].items() if not FILL_RE.search(k) and not FILL_RE.search(v[0])}
        xy = np.array([(v[1], v[2]) for v in real.values()]) if real else np.zeros((0, 2))
        ax.scatter(xy[:, 0], xy[:, 1], s=1.2, c="#3d3d3d", lw=0, zorder=1)
        new = [v for k, v in real.items() if k not in base_cells]
        if new:
            nx = np.array([(v[1], v[2]) for v in new])
            ax.scatter(nx[:, 0], nx[:, 1], s=7, c=col, lw=0, zorder=3)
        if i == 0 and flags:
            segs = [s for net in flags for s in L["wires"].get(net, [])]
            ax.add_collection(LineCollection(segs, colors=F.GREEN, linewidths=0.5, alpha=0.8, zorder=2))
        segs = [s for net in V for s in L["wires"].get(net, [])]
        ax.add_collection(LineCollection(segs, colors=F.CRIT, linewidths=0.9, zorder=4))
        ax.set_title(f"{title}\n{len(V)} violating nets" + (f" · {len(new):,} cells inserted" if i > 0 else ""),
                     fontsize=F.FS - 1, color=F.INK, loc="left", pad=4)
        nums[title] = {"violators": len(V), "inserted_cells": len(new), "cells": len(real), "dir": d}
    if a.title:
        fig.suptitle(a.title, fontsize=F.FS + 1, color=F.INK, x=0.01, ha="left")
    if a.note:
        fig.text(0.01, 0.1 * extra / (pw * aspect + 0.9 + extra), a.note, fontsize=F.FS - 2, color=F.MUTED, ha="left", va="bottom")
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
