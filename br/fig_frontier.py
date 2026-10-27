#!/usr/bin/env python3
"""Small multiples, one panel per design: signal violators left (symlog) against cells changed, for the corrected stock
repair at 0/10/20/30% margin (the calibrated frontier, joined) and the policies of Addendum 19: BeforeRoute's masked list
(thr500-30cr), the boosted list (bst500-30-10r), the calibrated estimate's equal-size list (rqn-30r) and its own threshold
list (rqt900-30r). With --cf: the correlated-flow bases of Addendum 22 (stock uni0/10/20/30; thr500-30c, bst500-30-10,
rqc-30). Designs whose frontier has not landed are drawn with what exists.
Usage: fig_frontier.py [--cf] [--name frontier14] [--cols 5] [--width 12.1]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import criteria_a19 as C  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT = {"frontier": ("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"),
           "pts": [("thr500-30cr", "BeforeRoute (masked list, 30%)", "^", "model", True),
                   ("bst500-30-10r", "boosted list (list 30%, rest 10%)", "D", "model", False),
                   ("rqn-30r", "calibrated estimate, equal-size list", "s", "grey", True),
                   ("rqt900-30r", "calibrated estimate ≥ 0.9 list", "o", "stock", False)],
           "bases": C.BASES}
CF = {"frontier": ("uni0", "uni10", "uni20", "uni30"),
      "pts": [("thr500-30c", "learned list (masked, 30%)", "^", "model", True),
              ("bst500-30-10", "boosted learned list", "D", "model", False),
              ("rqc-30", "correlated estimate, equal-size list", "s", "grey", True)],
      "bases": C.CF_BASES}
SHORT = {"bm64": "BM64", "des": "DES", "md5": "MD5", "ocs_blitter": "ocs_blitter", "salsa20": "salsa20", "y_huff": "y_huff",
         "ldpcenc": "LDPC", "sha512": "SHA-512", "blabla": "BlaBla", "chacha": "ChaCha", "point_add": "point_add",
         "picorv32": "PicoRV32", "aes_cipher": "AES"}


def label(base):
    fam, rest = base.split("-", 1)
    d, n = rest.rsplit("-", 1)
    name = SHORT.get(d, d)
    return f"{name}-{n}" if d == "picorv32" else name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cf", action="store_true")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--width", type=float, default=12.1)
    ap.add_argument("--fs", type=int, default=-3)
    ap.add_argument("--bases", nargs="*", default=None, help="subset of bases (default: all of the experiment)")
    ap.add_argument("--rowh", type=float, default=2.15)
    a = ap.parse_args()
    spec = dict(CF if a.cf else DEFAULT)
    if a.bases:
        spec["bases"] = a.bases
    name = a.name or ("frontier_cf" if a.cf else "frontier14")
    C.RESULTS = os.path.join(F.ROOT, "results")
    F.setup_style()
    F.FS = F.FS + a.fs
    col = {"model": F.GREEN, "stock": F.BLUE, "grey": F.GREY}
    bases = spec["bases"]
    rows = (len(bases) + a.cols - 1) // a.cols
    fig, axes = plt.subplots(rows, a.cols, figsize=(a.width, a.rowh * rows + 0.9), squeeze=False)
    for i, b in enumerate(bases):
        ax = axes[i // a.cols][i % a.cols]
        fr = []
        for fa in spec["frontier"]:
            r, c = C.arm(b, fa), C.cells(b, fa)
            if r is not None and c is not None:
                fr.append((c, r["V"], fa))
        if fr:
            fr.sort()
            ax.plot([x for x, _, _ in fr], [y for _, y, _ in fr], color=F.BLUE, lw=1.6, marker="o", ms=4, zorder=2)
            for x, y, fa in fr:
                ax.annotate(fa.split("-")[-1].replace("uni", "") + "%", (x, y), textcoords="offset points", xytext=(3, 3),
                            fontsize=F.FS - 3, color=F.BLUE)
        for armname, _, mk, ck, filled in spec["pts"]:
            r, c = C.arm(b, armname), C.cells(b, armname)
            if r is None or c is None:
                continue
            kw = dict(color=col[ck]) if filled else dict(facecolors=F.SURFACE, edgecolors=col[ck], linewidths=1.6)
            ax.scatter([c], [r["V"]], marker=mk, s=46, zorder=4, **kw)
        ax.set_yscale("symlog", linthresh=1)
        ax.set_ylim(-0.3, None)
        ax.set_title(label(b), fontsize=F.FS - 1, loc="left")
        ax.tick_params(labelsize=F.FS - 3)
        ax.grid(color=F.GRID, lw=0.6)
    for j in range(len(bases), rows * a.cols):
        axes[j // a.cols][j % a.cols].axis("off")
    fig.supxlabel("cells changed by the repair (buffers inserted + cells resized)", fontsize=F.FS - 1, color=F.INK2,
                  y=(0.095 if a.width >= 10 else 0.2) * (6.0 / max(fig.get_size_inches()[1], 1)))
    fig.supylabel("signal violators left (symlog)", fontsize=F.FS - 1, color=F.INK2)
    handles = [plt.Line2D([], [], color=F.BLUE, marker="o", lw=1.6, ms=4,
                          label=("stock repair, correlated RC, 0–30% margin" if a.cf else "stock repair, corrected wire cap, 0–30% margin"))]
    for armname, lab, mk, ck, filled in spec["pts"]:
        if filled:
            handles.append(plt.Line2D([], [], color=col[ck], marker=mk, lw=0, ms=6, label=lab))
        else:
            handles.append(plt.Line2D([], [], color=col[ck], marker=mk, lw=0, ms=6, markerfacecolor=F.SURFACE, label=lab))
    ncol = 3 if a.width >= 10 else 2
    fig.legend(handles=handles, loc="lower center", ncol=ncol, fontsize=F.FS - 2, frameon=False, bbox_to_anchor=(0.5, 0.0))
    nrow_leg = (len(handles) + ncol - 1) // ncol
    bottom = (0.11 if ncol == 3 else 0.13 + 0.035 * nrow_leg) * (6.0 / max(fig.get_size_inches()[1], 1))
    fig.tight_layout(rect=(0.02, min(bottom, 0.3), 1, 1))
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, f"{name}.png")
    fig.savefig(out, dpi=200, facecolor=F.SURFACE)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
