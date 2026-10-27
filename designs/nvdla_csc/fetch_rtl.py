#!/usr/bin/env python3
"""Fetch the NVDLA nv_small RTL for NV_NVDLA_csc into designs/nvdla_csc/rtl/ (not committed).

NVDLA RTL is NOT stored in this (public) repository. This script downloads, at job time,
exactly the files the CSC block needs and checks each against a pinned SHA-256; nothing
downloaded is executed (Verilog/Verilog-header text only, read by Yosys/OpenROAD).
14 RTL files (12 CSC/vlib modules actually used + the empty NV_BLKBOX_SINK sink cell +
include/simulate_x_tick.vh) and the NVDLA LICENSE.

Source of the files (pinned):
  * ucb-bar/nvdla-wrapper @ d99ffdc79bbf9b86c6cad0c278a785d5802c8209 (Chipyard's NVDLA
    generator), path src/main/resources/vsrc/small/vmod/ = a copy of nvdla/hw
    outdir/nv_small/vmod produced by `tools/bin/tmake -build vmod` (nv_small spec).
    That repo's hw submodule pointer (8e06b1b, nvdlav1) is stale; the CSC files were checked
    token-for-token against nvdla/hw master @ 1a65f1f5b48268accaa47c95f95c2601918be095
    sources (only cpp-macro literals and the #ifdef NVDLA_WINOGRAD/BATCH_ENABLE branches that
    nv_small disables differ) - see designs/nvdla_csc/README.md.
  * LICENSE from nvdla/hw @ 1a65f1f5b48268accaa47c95f95c2601918be095
    (NVIDIA Open NVDLA License and Agreement v1.0), saved as rtl/LICENSE.NVDLA.

Usage:
  python3 -I designs/nvdla_csc/fetch_rtl.py                 # download (idempotent)
  python3 -I designs/nvdla_csc/fetch_rtl.py --from-dir <vmod> [--license <file>]
                                                             # copy from a local mirror
  python3 -I designs/nvdla_csc/fetch_rtl.py --check         # verify only, exit 1 if missing/bad
Exit codes: 0 ok, 1 missing/mismatch (with --check), 2 download/verification failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

RTL_REPO = "ucb-bar/nvdla-wrapper"
RTL_COMMIT = "d99ffdc79bbf9b86c6cad0c278a785d5802c8209"
RTL_SUBDIR = "src/main/resources/vsrc/small/vmod"
UPSTREAM_REPO = "nvdla/hw"
UPSTREAM_COMMIT = "1a65f1f5b48268accaa47c95f95c2601918be095"  # master, NVDLA_2 (nv_small spec)
RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"

# relative to vmod/ ; sha256 of the file at RTL_REPO@RTL_COMMIT
FILES = {
    "nvdla/csc/NV_NVDLA_csc.v": "71f98f32be8bf9aa98b13d2b0a5b5e18f4ae9b3d1c3cb8c48dd10827e8adc163",
    "nvdla/csc/NV_NVDLA_CSC_slcg.v": "b47ab28a127530078022ff019cc899df47c14e90bcb9e4f20b6a9c9cf57228f2",
    "nvdla/csc/NV_NVDLA_CSC_dl.v": "2280366a0b028963d08654a474412ecad835b7c5f987e055da909024b5c11de6",
    "nvdla/csc/NV_NVDLA_CSC_wl.v": "2cd1e9719f16968d489a28a1783ed7141165e9642d2c1c34355b407e9ecf4f89",
    "nvdla/csc/NV_NVDLA_CSC_WL_dec.v": "ac577eb6635a43c29816ac66775b154c113f1e4715718f297c2bd526b2732924",
    "nvdla/csc/NV_NVDLA_CSC_sg.v": "c33a2c604fda97962520e1495c2ba02c6190cec32c7397d414b56fd023182ac2",
    "nvdla/csc/NV_NVDLA_CSC_SG_wt_fifo.v": "fb8dd36cd48356062093e8d34fe35e367d11ee83c9262a9181acea947330ee1b",
    "nvdla/csc/NV_NVDLA_CSC_SG_dat_fifo.v": "5edc723eb823f6b87183f20a416046767dec88a981b3bd10e628e25cbba53113",
    "nvdla/csc/NV_NVDLA_CSC_regfile.v": "4f071a5dbfce1bf569ef70d4b9df7370d673aed78e70ae7b140ba71d0a666a1c",
    "nvdla/csc/NV_NVDLA_CSC_dual_reg.v": "0a1b4f58be50c3f30055ceedbde70755b529bdfff044ab8e896c2b165383b3fb",
    "nvdla/csc/NV_NVDLA_CSC_single_reg.v": "ea1441b7768b2acd09523d9152fea64f2d672d0c581c496fca624f935a87c803",
    "vlibs/NV_CLK_gate_power.v": "2a8c9896e74ddfb1ca1c752cbc587bdce4505a22d71377371c1e8505a53355d0",
    "vlibs/NV_BLKBOX_SINK.v": "5e848d986a8033321c882e88ff6617007d99107fbdcc676f5319acde33bbdb39",
    "include/simulate_x_tick.vh": "42bb802622b70f043051ebe99cf9c10d37f1754984600c313ce858c51d96f196",
}
LICENSE_SHA256 = "0f232029d97359752ac8a67f20e5fd6a703bb3af80f812ebff927a059a84cccb"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _ssl_contexts():
    """Default trust store first; then certifi's bundle (the toolchain image's Python may have no
    system CA path configured). Content is pinned by SHA-256 either way."""
    yield None
    try:
        import certifi

        yield ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass


def download(url: str, dst: str, tries: int = 4) -> None:
    last = None
    for i in range(tries):
        for ctx in _ssl_contexts():
            try:
                with urllib.request.urlopen(url, timeout=60, context=ctx) as r, open(dst + ".part", "wb") as f:
                    shutil.copyfileobj(r, f)
                os.replace(dst + ".part", dst)
                return
            except Exception as e:  # TLS/network hiccup: try the next trust store, then retry
                last = e
        curl = shutil.which("curl")
        if curl:
            r = subprocess.run([curl, "-fsSL", "--retry", "2", "-o", dst + ".part", url])
            if r.returncode == 0:
                os.replace(dst + ".part", dst)
                return
            last = f"curl exit {r.returncode}"
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "rtl"))
    ap.add_argument("--from-dir", default=None, help="local copy of the generated vmod/ tree (same commit)")
    ap.add_argument("--license", default=None, help="local copy of nvdla/hw LICENSE (with --from-dir)")
    ap.add_argument("--check", action="store_true", help="verify only")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    vmod = os.path.join(out, "vmod")
    targets = {os.path.join(vmod, rel): (rel, h) for rel, h in FILES.items()}
    lic = os.path.join(out, "LICENSE.NVDLA")
    targets[lic] = ("LICENSE", LICENSE_SHA256)

    bad = [p for p, (_, h) in targets.items() if not (os.path.exists(p) and sha256(p) == h)]
    if a.check or not bad:
        print(f"[fetch_rtl] {len(targets) - len(bad)}/{len(targets)} files present and verified in {out}")
        return 1 if bad else 0

    t0 = time.time()
    for p in bad:
        rel, h = targets[p]
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if a.from_dir:
            src = a.license if rel == "LICENSE" else os.path.join(a.from_dir, rel)
            if not src or not os.path.exists(src):
                print(f"[fetch_rtl] missing local source for {rel}", file=sys.stderr)
                return 2
            shutil.copyfile(src, p)
        elif rel == "LICENSE":
            download(RAW.format(repo=UPSTREAM_REPO, commit=UPSTREAM_COMMIT, path="LICENSE"), p)
        else:
            download(RAW.format(repo=RTL_REPO, commit=RTL_COMMIT, path=f"{RTL_SUBDIR}/{rel}"), p)
        got = sha256(p)
        if got != h:
            os.remove(p)
            print(f"[fetch_rtl] SHA-256 mismatch for {rel}: got {got}, want {h}", file=sys.stderr)
            return 2
    stamp = {
        "rtl_source": f"https://github.com/{RTL_REPO}/tree/{RTL_COMMIT}/{RTL_SUBDIR}",
        "upstream": f"https://github.com/{UPSTREAM_REPO}/tree/{UPSTREAM_COMMIT}",
        "license": "NVIDIA Open NVDLA License and Agreement v1.0 (LICENSE.NVDLA)",
        "files_sha256": FILES,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "local-copy" if a.from_dir else "download",
    }
    with open(os.path.join(out, "FETCHED.json"), "w") as f:
        json.dump(stamp, f, indent=1)
    print(f"[fetch_rtl] fetched+verified {len(bad)} files into {out} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
