#!/usr/bin/env python3
"""Per-base arm table relative to the rerun control (same rebuilt checkpoint as the arms)."""
import json, sys, os
bases = sys.argv[1:] or ["d3-salsa20-000", "d3-des-000", "d3-y_huff-000", "d3-ocs_blitter-000", "d3-bm64-000", "d3-md5-000", "d3b-sha512-000", "d3b-ldpcenc-000"]
order = ["rerun", "uni30", "uni50", "uni70", "est050-70", "det050-70", "tgt050-70", "thr500-70", "exp100-70"]
for b in bases:
    p = f"results/{b}/hero_summary.json"
    if not os.path.exists(p):
        continue
    d = json.load(open(p)); rows = {r["tag"][len(b) + 1:] or "base": r for r in d["arms"]}
    ref = rows.get("rerun") or rows.get("base")
    V0, H0 = ref.get("signoff_violating_data_nets"), ref.get("hold_ws")
    print(f"\n{b}: reference={'rerun' if 'rerun' in rows else 'base'} V={V0} hold={H0:.3f} overshoot={ref.get('data_slew_overshoot')}  (base V={rows['base'].get('signoff_violating_data_nets')})")
    for a in order + sorted(k for k in rows if k not in order and k != "base"):
        r = rows.get(a)
        if not r or r.get("signoff_violating_data_nets") is None:
            continue
        cells = (r.get("resized") or 0) + (r.get("buffers") or 0) if r.get("resized") is not None else None
        eq = ""
        ej = f"results/{b}-{a}/equiv/result.json"
        if os.path.exists(ej):
            eq = json.load(open(ej)).get("status", "")
        V = r["signoff_violating_data_nets"]
        print(f"   {a:14s} V={V:5d} ({100*(1-V/max(1,V0)):5.1f}% removed) cells={str(cells):>5s} hold={100*(r.get('hold_ws') or 0)/H0:4.0f}% dA={(r['stdcell_area']-ref['stdcell_area'])/ref['stdcell_area']*100:+.2f}% overshoot={r.get('data_slew_overshoot')} {eq}")
