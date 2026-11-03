#!/usr/bin/env python3
"""IO1: blind reader packets, the nearest-side script arm, pin file -> plan translation, and the leak test.

  packet.py build  --captures DIR [--pins PINS]   DIR/<case>/ holds the artifact of job io-cap-<case>
  packet.py script [--pins PINS]                  nearest-side script arm -> PRIVATE/script/<pseudonym>/pins.txt
  packet.py plans  --arm script|claude [--pins PINS] [--allow-missing]
                                                  validate every PINS/claude/<pseudonym>/pins.txt (claude) or
                                                  PRIVATE/script/<pseudonym>/pins.txt (script), write
                                                  farm/qa/IO/plans/<case>-<arm>.json and farm/qa/IO/arms/<arm>/
  packet.py leak   [--pins PINS]                  leak test over PINS/packets (exit 1 on any hit)
PINS defaults to /home/claude/ideas/overnight/pins (packets/ = reader input, claude/ = reader output); PRIVATE
(--private, default /home/claude/qa/io-private: salt, case <-> pseudonym index, name maps, the script arm's answers)
is outside it and never shown to a reader. Pre-registration: docs/qa_week/IO_PREREG.md.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import inspect
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import iolib  # noqa: E402

PINS = "/home/claude/ideas/overnight/pins"          # packets/ (reader input) and claude/ (reader output)
PRIVATE = "/home/claude/qa/io-private"              # salt, index, name maps, script answers: never shown to a reader
BUF_RX = re.compile(r"__(buf|clkbuf|clkdlybuf\w*|dlygate\w*|dlymetal\w*|dlybuf\w*)_\d+$")
CRIT_FRAC = 0.10       # script arm: critical = group worst slack within 10% of T0 of the worst port group
CRIT_MAX = 4           # script arm: at most the 4 most critical groups move
BUF_DEPTH = 8          # script arm: look through at most 8 buffers from a port to its logic


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def jload(p):
    return json.load(gzip.open(p) if p.endswith(".gz") else open(p))


def unesc(s):
    return s.replace("\\", "")


# ------------------------------------------------------------------------------------------------ private state
def private(pdir):
    d = pdir
    os.makedirs(os.path.join(d, "maps"), exist_ok=True)
    sp = os.path.join(d, "salt.txt")
    if not os.path.exists(sp):
        open(sp, "w").write(secrets.token_hex(16) + "\n")
    return d, open(sp).read().strip()


def load_cases():
    return {c["case"]: c for c in json.load(open(os.path.join(HERE, "cases.json")))["cases"]}


# ------------------------------------------------------------------------------------------------ capture input
def unraw(obj):
    """A path report that the capture stored as text (any warning lines before the JSON) is parsed here."""
    if isinstance(obj, dict) and set(obj) == {"raw"}:
        s = obj["raw"]
        return json.loads(s[s.index("{"):])
    if isinstance(obj, dict):
        return {k: unraw(v) for k, v in obj.items()}
    return obj


def read_capture(capdir, case):
    runs = sorted(glob.glob(os.path.join(capdir, f"io-cap-{case}-r0")))
    if not runs:
        raise SystemExit(f"no capture run for {case} under {capdir}")
    r = runs[0]
    cap = {"dir": r, "metrics": jload(os.path.join(r, "metrics.json")),
           "ports": jload(os.path.join(r, "capture", "ports.json.gz")),
           "paths": unraw(jload(os.path.join(r, "capture", "paths.json.gz"))),
           "def": gzip.open(os.path.join(r, "capture", "final.def.gz"), "rt").read(),
           "nets_postgrt": [json.loads(x) for x in gzip.open(os.path.join(r, "nets.jsonl.gz"), "rt")],
           "nets_signoff": [json.loads(x) for x in gzip.open(os.path.join(r, "nets_signoff.jsonl.gz"), "rt")],
           "resolved": jload(os.path.join(r, "resolved.json"))}
    return cap


def def_names(text):
    """All component, net and pin names in a DEF (unescaped)."""
    comps, nets, pins, sec = set(), set(), set(), None
    for line in text.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] in ("COMPONENTS", "PINS", "NETS", "SPECIALNETS") and len(t) >= 2:
            sec = t[0]
            continue
        if t[0] == "END":
            sec = None
            continue
        if t[0] == "-" and len(t) > 1:
            {"COMPONENTS": comps, "PINS": pins, "NETS": nets, "SPECIALNETS": nets}.get(sec, set()).add(unesc(t[1]))
            if sec == "PINS" and "NET" in t:
                nets.add(unesc(t[t.index("NET") + 1]))
    return comps, nets, pins


# ------------------------------------------------------------------------------------------------ pseudonyms
class Mapper:
    """Stable pseudonyms within one case: ports keep their bus structure (G07[3]); the clock port is CLK and reset
    ports RST/RST1..; instances i<k>, nets n<k> in salted-hash order; a port's own net takes the port's pseudonym."""

    KEEP_NETS = {"VPWR", "VGND"}

    def __init__(self, salt, case, design, clock_port, ports, comps, nets):
        self.design, self.clock = design, clock_port
        groups = iolib.group_ports({n: {"dir": p["dir"]} for n, p in ports.items()}, clock_port)
        self.groups = groups
        data = sorted([g for g in groups if not groups[g]["fixed"]], key=lambda g: sha(f"{salt}|{case}|g|{g}"))
        resets = sorted([g for g in groups if groups[g]["role"] == "reset"])
        self.gmap = {g: f"G{i:02d}" for i, g in enumerate(data, 1)}
        for i, g in enumerate(resets, 1):
            self.gmap[g] = "RST" if len(resets) == 1 else f"RST{i}"
        for g in groups:
            if groups[g]["role"] == "clock":
                self.gmap[g] = "CLK"
        self.pmap = {}
        for n in ports:
            base, idx = iolib.base_and_index(n)
            self.pmap[n] = self.gmap[base] + ("" if idx is None else f"[{idx}]")
        self.imap = {n: f"i{k}" for k, n in enumerate(sorted(comps, key=lambda n: sha(f"{salt}|{case}|i|{n}")), 1)}
        port_nets = {p.get("net"): self.pmap[n] for n, p in ports.items() if p.get("net")}
        other = sorted([n for n in nets if n not in port_nets and n not in self.KEEP_NETS],
                       key=lambda n: sha(f"{salt}|{case}|n|{n}"))
        self.nmap = {n: f"n{k}" for k, n in enumerate(other, 1)}
        self.nmap.update(port_nets)
        self.real = set(self.pmap) | set(groups) | set(self.imap) | set(self.nmap) | {design}
        self.real -= {"CLK", "RST", "VPWR", "VGND"}

    def port(self, n):
        n = unesc(n)
        return n if n in self.KEEP_NETS else self.pmap[n]

    def inst(self, n):
        return self.imap[unesc(n)]

    def net(self, n):
        n = unesc(n)
        return n if n in self.KEEP_NETS else self.nmap[n]

    def pinref(self, s):
        s = unesc(s)
        if s in self.pmap:
            return self.pmap[s]
        if "/" in s:
            i, p = s.rsplit("/", 1)
            if i in self.imap:
                return f"{self.imap[i]}/{p}"
        raise KeyError(s)

    def to_dict(self):
        return {"design": self.design, "clock": self.clock, "groups": self.gmap, "ports": self.pmap,
                "insts": self.imap, "nets": self.nmap}


# ------------------------------------------------------------------------------------------------ rewriting
def rewrite_def(text, M):
    out, sec = [], None
    for line in text.splitlines():
        t = line.split()
        if t and t[0] == "DESIGN":
            out.append("DESIGN blk ;")
            continue
        if t and t[0] in ("COMPONENTS", "PINS", "NETS", "SPECIALNETS") and len(t) >= 2:
            sec = t[0]
        elif t and t[0] == "END":
            sec = None
        elif t and sec:
            if t[0] == "-" and len(t) > 1:
                if sec == "COMPONENTS":
                    t[1] = M.inst(t[1])
                elif sec == "PINS":
                    t[1] = M.port(t[1])
                    if "NET" in t:
                        k = t.index("NET") + 1
                        t[k] = M.net(t[k])
                else:
                    t[1] = M.net(t[1])
            if sec in ("NETS", "SPECIALNETS"):
                for k in range(len(t) - 3):
                    if t[k] == "(" and t[k + 3] == ")":
                        if t[k + 1] == "PIN":
                            t[k + 2] = M.port(t[k + 2])
                        elif t[k + 1] != "*" and unesc(t[k + 1]) in M.imap:
                            t[k + 1] = M.inst(t[k + 1])
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + " ".join(t))
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def rewrite_net_row(r, M):
    r = dict(r)
    r["net"] = M.net(r["net"])
    if r.get("driver_inst"):
        r["driver_inst"] = M.inst(r["driver_inst"])
    if r.get("driver_kind") == "port" and r.get("driver_pin"):
        r["driver_pin"] = M.port(r["driver_pin"])
    r["load_keys"] = [("PORT:" + M.port(k[5:])) if k.startswith("PORT:") else M.pinref(k) for k in r.get("load_keys", [])]
    return r


def rewrite_ports(pj, M):
    fl = dict(pj["floor"])
    fl["design"], fl["clock_port"] = "blk", "CLK"
    fl.pop("slack_api_error", None)
    ports = {}
    for n, p in pj["ports"].items():
        q = dict(p)
        q["net"] = M.net(p["net"]) if p.get("net") else None
        q["cells"] = [dict(c, inst=M.inst(c["inst"])) for c in p.get("cells", [])]
        ports[M.port(n)] = q
    return {"floor": fl, "ports": dict(sorted(ports.items()))}


def rewrite_paths(obj, M):
    if isinstance(obj, list):
        return [rewrite_paths(x, M) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k == "verilog_src":
            continue
        if k in ("from_input", "to_output") and isinstance(v, dict):
            out[k] = {M.port(pk): rewrite_paths(pv, M) for pk, pv in v.items()}
        elif k in ("startpoint", "endpoint", "pin") and isinstance(v, str) and v:
            out[k] = M.pinref(v)
        elif k == "instance" and isinstance(v, str) and v:
            out[k] = M.inst(v)
        elif k == "net" and isinstance(v, str) and v:
            out[k] = M.net(v)
        elif k == "cell" and v == M.design:
            out[k] = "blk"
        elif k in ("source_clock", "target_clock", "path_group") and v == M.clock:
            out[k] = "CLK"
        else:
            out[k] = rewrite_paths(v, M)
    return out


# ------------------------------------------------------------------------------------------------ floor and menu
def floor_of(ports_pseudo):
    fl = ports_pseudo["floor"]
    floor = {"dbu": fl["dbu"], "die": fl["die"], "tracks": fl["tracks"], "layers": fl["layers"],
             "pins": {n: {"edge": p["edge"], "pos": p["pos"]} for n, p in ports_pseudo["ports"].items()}}
    return floor


def group_table(ports_pseudo):
    g = iolib.group_ports({n: {"dir": p["dir"]} for n, p in ports_pseudo["ports"].items()}, "CLK")
    return g


def build_menu(ports_pseudo, T0):
    floor = floor_of(ports_pseudo)
    P = ports_pseudo["ports"]
    G = group_table(ports_pseudo)
    occ = {e: [p["pos"] for p in floor["pins"].values() if p["edge"] == e] for e in iolib.EDGES}
    segs = {}
    for e in iolib.EDGES:
        for k in iolib.SEGMENTS:
            a, b = iolib.segment_range(floor, e, k)
            free = [s for s in iolib.free_slots(floor, e, occ[e]) if a <= s < b]
            segs[f"{e}{k}"] = {"edge": e, "from_um": round(a / floor["dbu"], 3), "to_um": round(b / floor["dbu"], 3),
                               "centre_um": round((a + b) / 2 / floor["dbu"], 3), "free_slots_now": len(free)}
    groups, fixed = [], []
    for name in sorted(G):
        g = G[name]
        pins = g["pins"]
        sl = [P[p]["slack_ns"] for p in pins if P[p].get("slack_ns") is not None and P[p].get("cells")]
        edges = {}
        for p in pins:
            edges[P[p]["edge"]] = edges.get(P[p]["edge"], 0) + 1
        rec = {"group": name, "dir": g["dir"], "bits": len(pins), "pins": pins,
               "connected_bits": sum(1 for p in pins if P[p].get("cells")),
               "worst_setup_slack_ns": round(min(sl), 4) if sl else None, "stock_edges": edges}
        if g["fixed"]:
            rec["role"] = g["role"]
            fixed.append(rec)
            continue
        rec["legal_if_only_move"] = [o for o in iolib.OPTIONS[1:]
                                     if iolib.place_groups(floor, [{"group": name, "pins": pins, "option": o}])["ok"]]
        groups.append(rec)
    return {"T0_ns": T0, "options": list(iolib.OPTIONS), "segments": segs,
            "lattice_slots_per_edge": {e: len(iolib.lattice(floor, e)) for e in iolib.EDGES},
            "free_slots_per_edge_now": {e: len(iolib.free_slots(floor, e, occ[e])) for e in iolib.EDGES},
            "pitch_tracks": iolib.PITCH_TRACKS, "corner_margin_um": iolib.CORNER_MARGIN_UM,
            "fixed_groups": fixed, "groups": groups}


VALIDATOR_HEAD = '''#!/usr/bin/env python3
"""Validate a pin file for this packet and print where every moved pin would land.
Usage: python3 validate_pins.py pins.txt      (reads floor.json and menu.json next to this script)
Exit 0 and "OK" when the file is valid and every listed group fits; otherwise the reasons and exit 1."""
import json, math, os, re, sys

'''
VALIDATOR_MAIN = '''

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    floor = json.load(open(os.path.join(here, "floor.json")))
    menu = json.load(open(os.path.join(here, "menu.json")))
    groups = {g["group"]: g for g in menu["groups"]}
    fixed = {g["group"] for g in menu["fixed_groups"]}
    moves, errors = parse_pin_file(open(sys.argv[1]).read())
    plan = []
    for g, o in moves:
        if g in fixed:
            errors.append(f"{g} is fixed (clock/reset) and cannot be listed")
        elif g not in groups:
            errors.append(f"unknown group {g}")
        else:
            plan.append({"group": g, "pins": groups[g]["pins"], "option": o})
    if not errors:
        res = place_groups(floor, plan)
        if not res["ok"]:
            errors.append(res["error"])
    if errors:
        print("INVALID:")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    dbu = floor["dbu"]
    for mv in plan:
        if mv["option"] == "KEEP":
            continue
        ps = [res["placed"][p]["pos"] / dbu for p in mv["pins"]]
        print(f"{mv['group']:>5} -> {mv['option']}: {len(ps)} pins on edge {mv['option'][0]} from {min(ps):.2f} to "
              f"{max(ps):.2f} um along the edge")
    print("OK")


if __name__ == "__main__":
    main()
'''


def validator_source():
    parts = ["EDGES = " + repr(iolib.EDGES), "SEGMENTS = " + repr(iolib.SEGMENTS), "OPTIONS = " + repr(iolib.OPTIONS),
             "PITCH_TRACKS = " + repr(iolib.PITCH_TRACKS), "CORNER_MARGIN_UM = " + repr(iolib.CORNER_MARGIN_UM), ""]
    for fn in (iolib.edge_span, iolib.lattice, iolib.free_slots, iolib.segment_range, iolib.place_groups, iolib._place,
               iolib.parse_pin_file):
        parts.append(inspect.getsource(fn))
    return VALIDATOR_HEAD + "\n\n".join(parts) + VALIDATOR_MAIN


# ------------------------------------------------------------------------------------------------ README
README = """# Pin-placement packet {P}

One routed implementation of a synchronous digital block ("blk") in the open SkyWater sky130 130 nm process
(standard cells sky130_fd_sc_hd), built by LibreLane 3.0.16 / OpenROAD. Every port, instance and net carries a
pseudonym. Do not try to identify the design; it does not matter for the task.

## Your task
Choose where some groups of the block's I/O pins should sit on the die boundary so that the block reaches a faster
**verified** clock. Write one pin file (format below). You get exactly one selection, and you will not see any
result.

## How your pin file is judged (identical for every competing method)
The block is rebuilt from the same RTL with exactly the flow settings of this run. The only change: right after
the tool places the I/O pins, the groups you list are moved to the die-edge segment you name; every other pin stays
where the tool put it. Cell placement, clock tree and routing then run as usual. Your file is applied at every
build below.
1. Build at T0 = {T0} ns (the target of the run in this packet). Claimed clock C = T0 - worst setup slack.
2. Rebuild at C rounded up to 0.05 ns. While a rebuild passes, rebuild at its own claim rounded up to 0.05 ns.
   If the first rebuild fails, step back once, to the larger of its own claim rounded up and that clock + 0.05 ns.
   At most 4 rebuilds; a failure after the step-back (or after a pass) ends the sequence.
3. A build passes when setup and hold slack are >= 0 at all nine corners, the router reports 0 DRC errors, and the
   count of max-slew plus max-capacitance violation pins is at most {BAR}.
4. Score: the smallest clock period that passed. Lower is better.
Your pins are compared with the tool's own pins and with a simple rule, each judged this way. Each build's pin
positions are recomputed on that build's floorplan by the same rule as validate_pins.py; a group that no longer fits
there keeps the tool's pins in that build.

## The contract (fixed; the same for every option)
- Every data input has an input delay, and every output an output delay, of 20% of the clock period, relative to the
  clock. Inputs are driven by sky130_fd_sc_hd__inv_2/Y; outputs drive 33.442 fF. So only wire and cells inside the
  block change with pin positions; anything outside the block is not modeled.
- Clock uncertainty 0.25 ns; clock transition 0.15 ns; timing derate 5%; max transition 0.75 ns; max capacitance
  0.2 pF; max fanout 10. Corners: {{min, nom, max}} extracted RC x {{tt 25C 1.80V, ss 100C 1.60V, ff -40C 1.95V}}.
- The tool's own pins come from OpenROAD's pin placer (matching mode): each pin goes to a free slot near the cells it
  connects to in a preliminary placement made without pins; then all cells are placed again with the pins fixed.
- The tool buffers every input and output port (the first/last cell on a port net is usually such a buffer).
- Fixed and never moved: CLK (the clock port) and any RST port. Bus order is fixed: a moved group is placed as one
  run of pins in ascending bit order along the edge (left to right on N/S, bottom to top on E/W). Pins sit on the
  edge's own layer (met2 on N/S, met3 on E/W), on every second routing track, at least {MARGIN} um from a corner.

## Files (all units as stated; coordinates in database units of 1/1000 um unless the name ends in _um)
- contract.json: the run's settings, T0, the corner list, the pass bar.
- menu.json: the movable groups (bits, direction, current edges, worst setup slack at T0, the options that fit if
  that group were the only one moved), the fixed groups, the 12 edge segments with coordinates and free slots now.
- floor.json: die, track grids and every pin's current edge and position (what validate_pins.py uses).
- run/metrics.json: the run's own metrics (LibreLane names; worst slacks in ns, per corner and overall).
- run/ports.json: every port: direction, net, pin shape, edge, position, worst setup slack over the nine corners
  (ns), and the instance pins on its net with coordinates.
- run/paths.json.gz: OpenSTA `report_checks -format json` (worst over the nine corners; times in s, x/y in m):
  "top" = the worst setup paths (one per endpoint), "from_input" = worst path from each input port,
  "to_output" = worst path to each output port.
- run/nets_postgrt.jsonl.gz and run/nets_signoff.jsonl.gz: one row per signal net (driver, loads, coordinates,
  half-perimeter, global-route length by layer, capacitance, slews and limits) at the post-global-route estimate
  and at signoff (extracted parasitics).
- run/layout.def.gz: the final placed and routed DEF.
- validate_pins.py: checks a pin file and prints where each moved pin would land.

## Output: exactly one file
Write `{OUT}/pins.txt`:
```
# lines starting with # are ignored
G07 W2
G03 N1
```
One line per group you move: `<group> <option>`, option one of N1 N2 N3 E1 E2 E3 S1 S2 S3 W1 W2 W3 (edge, then the
third of that edge, numbered from the low coordinate: 1 = left/bottom). Unlisted groups keep the tool's pins.
Line order is placement priority: a group is placed at the free slots nearest its segment's centre after the groups
above it; the pins of every listed group are freed first, so listed groups can trade places. A single line `ABSTAIN`
keeps everything (allowed). Run `python3 validate_pins.py pins.txt`; it must print OK.

Optionally also write `{OUT}/rationale.md` (at most 300 words, not scored): for each move, which nets or paths you
expect to gain, the expected direction of their delay change, and your confidence (0 to 1).

Use only the files in this folder. No network, no other files.
"""


# ------------------------------------------------------------------------------------------------ build
def cmd_build(a):
    pins = a.pins
    pdir, salt = private(a.private)
    cases = load_cases()
    index = {}
    for case, c in sorted(cases.items()):
        cap = read_capture(os.path.join(a.captures, case), case)
        P = f"p{sha(salt + '|case|' + case)[:6]}"
        index[case] = P
        comps, nets, _ = def_names(cap["def"])
        for rows in (cap["nets_postgrt"], cap["nets_signoff"]):
            nets |= {r["net"] for r in rows}
        M = Mapper(salt, case, cap["ports"]["floor"]["design"], cap["ports"]["floor"]["clock_port"],
                   cap["ports"]["ports"], comps, nets)
        out = os.path.join(pins, "packets", P)
        os.makedirs(os.path.join(out, "run"), exist_ok=True)
        ports_p = rewrite_ports(cap["ports"], M)
        json.dump(ports_p, open(os.path.join(out, "run", "ports.json"), "w"), indent=0)
        with gzip.open(os.path.join(out, "run", "paths.json.gz"), "wt") as f:
            json.dump(rewrite_paths(cap["paths"], M), f)
        for key, fn in (("nets_postgrt", "nets_postgrt.jsonl.gz"), ("nets_signoff", "nets_signoff.jsonl.gz")):
            with gzip.open(os.path.join(out, "run", fn), "wt") as f:
                for r in cap[key]:
                    f.write(json.dumps(rewrite_net_row(r, M)) + "\n")
        with gzip.open(os.path.join(out, "run", "layout.def.gz"), "wt") as f:
            f.write(rewrite_def(cap["def"], M))
        m = {k: v for k, v in cap["metrics"].items()}
        json.dump(m, open(os.path.join(out, "run", "metrics.json"), "w"), indent=1)
        T0 = c["T0"]
        menu = build_menu(ports_p, T0)
        json.dump(menu, open(os.path.join(out, "menu.json"), "w"), indent=1)
        json.dump(floor_of(ports_p), open(os.path.join(out, "floor.json"), "w"))
        settings = {k: v for k, v in c["overrides"].items() if k != "CLOCK_PERIOD"}
        contract = {"T0_ns": T0, "claimed_clock_at_T0_ns": round(T0 - m["timing__setup__ws"], 4),
                    "io_delay_pct_of_clock": 20, "input_driving_cell": "sky130_fd_sc_hd__inv_2/Y",
                    "output_load_fF": 33.442, "clock_uncertainty_ns": 0.25, "clock_transition_ns": 0.15,
                    "timing_derate_pct": 5, "max_transition_ns": 0.75, "max_capacitance_pF": 0.2, "max_fanout": 10,
                    "corners": cap["ports"]["floor"]["corners"], "pass_bar_slew_plus_cap_violation_pins": c["drv_ref"],
                    "rebuild_grid_ns": 0.05, "max_rebuilds": 4, "flow": "LibreLane 3.0.16 Classic, sky130A, sky130_fd_sc_hd",
                    "flow_settings_other_than_clock": settings}
        json.dump(contract, open(os.path.join(out, "contract.json"), "w"), indent=1)
        open(os.path.join(out, "validate_pins.py"), "w").write(validator_source())
        open(os.path.join(out, "README.md"), "w").write(README.format(
            P=P, T0=T0, BAR=c["drv_ref"], MARGIN=iolib.CORNER_MARGIN_UM, OUT=os.path.join(pins, "claude", P)))
        json.dump({"case": case, "pseudonym": P, "salt_sha256": sha(salt), **M.to_dict()},
                  open(os.path.join(pdir, "maps", f"{case}.json"), "w"))
        print(f"[packet] {case} -> {P}: {len(menu['groups'])} movable groups, {len(menu['fixed_groups'])} fixed, "
              f"free slots now {menu['free_slots_per_edge_now']}")
    json.dump(index, open(os.path.join(pdir, "index.json"), "w"), indent=1)


# ------------------------------------------------------------------------------------------------ script arm
def def_components(def_text):
    pos, sec = {}, None
    for line in def_text.splitlines():
        t = line.split()
        if t and t[0] == "COMPONENTS":
            sec = "C"
            continue
        if t and t[0] == "END" and len(t) > 1 and t[1] == "COMPONENTS":
            break
        if sec == "C" and t and t[0] == "-" and "(" in t:
            k = t.index("(")
            pos[t[1]] = (t[2], int(t[k + 1]), int(t[k + 2]))
    return pos


def logic_sinks(port, pdata, nets, by_driver, by_load, comp):
    """Instance positions of the logic a port connects to, looking through up to BUF_DEPTH buffers."""
    pts = []
    if pdata["dir"] == "INPUT":
        frontier = [r for r in nets if r.get("driver_kind") == "port" and r.get("driver_pin") == port]
        for _ in range(BUF_DEPTH + 1):
            nxt = []
            for r in frontier:
                for k in r.get("load_keys", []):
                    if k.startswith("PORT:"):
                        continue
                    inst = k.rsplit("/", 1)[0]
                    master = comp.get(inst, (None,))[0]
                    if master and BUF_RX.search(master) and inst in by_driver:
                        nxt.append(by_driver[inst])
                    elif inst in comp:
                        pts.append(comp[inst][1:])
            frontier = nxt
            if not frontier:
                break
    else:
        r = by_load.get("PORT:" + port)
        for _ in range(BUF_DEPTH + 1):
            if r is None or r.get("driver_kind") != "inst":
                break
            inst = r["driver_inst"]
            master = comp.get(inst, (None,))[0]
            if master and BUF_RX.search(master):
                r = by_load.get(f"{inst}/A")
                continue
            if inst in comp:
                pts.append(comp[inst][1:])
            break
    return pts


def nearest_side_plan(packet_dir):
    """Avi's hand baseline (written by Claude, Avi asleep): move each critical port group to the die edge nearest the
    logic it connects to, in the third of that edge facing the logic. Critical: the group's worst setup slack at T0 is
    within CRIT_FRAC*T0 of the worst port group's; at most CRIT_MAX groups, most critical first. Logic: the cells on
    the group's port nets, looked through port buffers (stock run's per-net dump, signoff view; cell positions from
    the DEF). If the group does not fit on that edge, the next nearest edge; if none, it stays."""
    menu = json.load(open(os.path.join(packet_dir, "menu.json")))
    floor = json.load(open(os.path.join(packet_dir, "floor.json")))
    ports = json.load(open(os.path.join(packet_dir, "run", "ports.json")))["ports"]
    nets = [json.loads(x) for x in gzip.open(os.path.join(packet_dir, "run", "nets_signoff.jsonl.gz"), "rt")]
    comp = def_components(gzip.open(os.path.join(packet_dir, "run", "layout.def.gz"), "rt").read())
    by_driver = {r["driver_inst"]: r for r in nets if r.get("driver_kind") == "inst"}
    by_load = {}
    for r in nets:
        for k in r.get("load_keys", []):
            by_load.setdefault(k, r)
    T0 = menu["T0_ns"]
    gs = [g for g in menu["groups"] if g["worst_setup_slack_ns"] is not None]
    if not gs:
        return [], {"reason": "no group has a timing path"}
    worst = min(g["worst_setup_slack_ns"] for g in gs)
    crit = sorted([g for g in gs if g["worst_setup_slack_ns"] <= worst + CRIT_FRAC * T0],
                  key=lambda g: (g["worst_setup_slack_ns"], g["group"]))[:CRIT_MAX]
    die = floor["die"]
    plan, notes = [], []
    for g in crit:
        pts = []
        for p in g["pins"]:
            pts += logic_sinks(p, ports[p], nets, by_driver, by_load, comp)
        if not pts:
            notes.append({"group": g["group"], "kept": "no logic found"})
            continue
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        dist = {"N": die[3] - cy, "E": die[2] - cx, "S": cy - die[1], "W": cx - die[0]}
        chosen = None
        for e in sorted(iolib.EDGES, key=lambda e: (dist[e], iolib.EDGES.index(e))):
            lo, hi = iolib.edge_span(floor, e)
            proj = cx if e in ("N", "S") else cy
            k = min(3, max(1, int((proj - lo) / ((hi - lo) / 3.0)) + 1))
            trial = plan + [{"group": g["group"], "pins": g["pins"], "option": f"{e}{k}"}]
            if iolib.place_groups(floor, trial)["ok"]:
                chosen = f"{e}{k}"
                plan = trial
                break
        notes.append({"group": g["group"], "slack_ns": g["worst_setup_slack_ns"], "logic_cells": len(pts),
                      "centroid_um": [round(cx / floor["dbu"], 2), round(cy / floor["dbu"], 2)],
                      "edge_distance_um": {e: round(v / floor["dbu"], 2) for e, v in dist.items()}, "option": chosen})
    return plan, {"critical": [g["group"] for g in crit], "worst_slack_ns": worst, "notes": notes}


def cmd_script(a):
    index = json.load(open(os.path.join(a.private, "index.json")))
    for case, P in sorted(index.items(), key=lambda kv: kv[1]):
        plan, info = nearest_side_plan(os.path.join(a.pins, "packets", P))
        d = os.path.join(a.private, "script", P)
        os.makedirs(d, exist_ok=True)
        lines = ["# nearest-side script arm (IO1): critical port groups to the die edge nearest their logic"]
        lines += [f"{m['group']} {m['option']}" for m in plan] or ["ABSTAIN"]
        open(os.path.join(d, "pins.txt"), "w").write("\n".join(lines) + "\n")
        json.dump(info, open(os.path.join(d, "script_notes.json"), "w"), indent=1)
        print(f"[script] {P}: {[(m['group'], m['option']) for m in plan]} critical {info.get('critical')}")


# ------------------------------------------------------------------------------------------------ plans
def cmd_plans(a):
    index = json.load(open(os.path.join(a.private, "index.json")))
    adir = os.path.join(HERE, "arms", a.arm)
    src_root = os.path.join(a.pins, "claude") if a.arm == "claude" else os.path.join(a.private, "script")
    os.makedirs(adir, exist_ok=True)
    os.makedirs(os.path.join(HERE, "plans"), exist_ok=True)
    hashes, bad = [], 0
    for case, P in sorted(index.items()):
        src = os.path.join(src_root, P, "pins.txt")
        if not os.path.exists(src):
            print(f"[plans] {case} {P}: no pins.txt")
            bad += 0 if a.allow_missing else 1
            continue
        text = open(src).read()
        mp = json.load(open(os.path.join(a.private, "maps", f"{case}.json")))
        inv = {v: k for k, v in mp["groups"].items()}
        menu = json.load(open(os.path.join(a.pins, "packets", P, "menu.json")))
        floor = json.load(open(os.path.join(a.pins, "packets", P, "floor.json")))
        groups = {g["group"]: g for g in menu["groups"]}
        moves, errors = iolib.parse_pin_file(text)
        pplan = []
        for g, o in moves:
            if g not in groups:
                errors.append(f"unknown or fixed group {g}")
            else:
                pplan.append({"group": g, "pins": groups[g]["pins"], "option": o})
        if not errors:
            res = iolib.place_groups(floor, pplan)
            if not res["ok"]:
                errors.append(res["error"])
        if errors:
            print(f"[plans] {case} {P}: INVALID {errors}")
            bad += 1
            continue
        real = []
        for mv in pplan:
            if mv["option"] == "KEEP":
                continue
            base = inv[mv["group"]]
            rp = {v: k for k, v in mp["ports"].items()}
            real.append({"group": base, "pseudonym": mv["group"], "pins": [rp[p] for p in mv["pins"]],
                         "option": mv["option"]})
        plan = {"version": 1, "case": case, "arm": a.arm, "pseudonym": P,
                "pin_file_sha256": hashlib.sha256(text.encode()).hexdigest(), "moves": real}
        pp = os.path.join(HERE, "plans", f"{case}-{a.arm}.json")
        json.dump(plan, open(pp, "w"), indent=1)
        open(os.path.join(adir, f"{P}.pins.txt"), "w").write(text)
        rat = os.path.join(src_root, P, "rationale.md")
        if os.path.exists(rat):
            open(os.path.join(adir, f"{P}.rationale.md"), "w").write(open(rat).read())
        hashes.append(f"{hashlib.sha256(text.encode()).hexdigest()}  {P}.pins.txt  ({case})")
        print(f"[plans] {case} {P}: {len(real)} moved groups -> {os.path.relpath(pp, REPO)}")
    open(os.path.join(adir, "SHA256SUMS"), "w").write("\n".join(hashes) + "\n")
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------ leak test
def forbidden_strings(cases):
    names = set()
    for d in os.listdir(os.path.join(REPO, "designs")):
        names.add(d)
        for cfg in glob.glob(os.path.join(REPO, "designs", d, "config*.json")):
            try:
                names.add(json.load(open(cfg)).get("DESIGN_NAME") or d)
            except Exception:  # noqa: BLE001
                pass
    mods = set()
    for c in cases.values():
        for f in glob.glob(os.path.join(REPO, c["design_dir"], "src", "*.v")):
            mods |= set(re.findall(r"\bmodule\s+([A-Za-z_]\w*)", open(f, errors="ignore").read()))
    tags = set()
    for c in cases.values():
        tags |= {c["winner_tag"], c["record_chain"]["T1_tag"], c["record_chain"]["kept_tag"], f"io-cap-{c['case']}"}
    pointers = {"beforeroute", "qa-io-pins", "farm/qa", "IO_PREREG", "prereg", "github", "/home/claude/eda", "/work/",
                "designs/", "runs/", "record_chain", "T1_tag", "kept_tag", "Tlast", "chain.json", "_RESULT",
                "smoke-io", "io-cap", "winner_tag", "E2_"}
    return {n for n in names | mods if len(n) >= 3}, tags, pointers


GENERIC = {"clock", "clk", "reset", "rst", "mode", "rate", "enable"}
NAME_KEYED = {"ports", "from_input", "to_output", "groups_by_name"}


def json_strings(obj, out, names_keyed):
    """Every string value in a JSON document, plus the keys of the maps keyed by object names."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if names_keyed:
                out.add(k)
            json_strings(v, out, k in NAME_KEYED)
    elif isinstance(obj, list):
        for v in obj:
            json_strings(v, out, False)
    elif isinstance(obj, str):
        out.add(obj)


def cmd_leak(a):
    cases = load_cases()
    names, tags, pointers = forbidden_strings(cases)
    index = json.load(open(os.path.join(a.private, "index.json")))
    maps = {case: json.load(open(os.path.join(a.private, "maps", f"{case}.json"))) for case in index}
    real_ports = set()
    for mp in maps.values():
        real_ports |= {iolib.base_and_index(p)[0] for p in mp["ports"]}
    distinctive = {n for n in real_ports if n.lower() not in GENERIC and len(n) >= 3}
    word = re.compile(r"[A-Za-z_][A-Za-z0-9_\[\]$.]*")
    hits, nfiles = [], 0
    for case, P in sorted(index.items()):
        mp = maps[case]
        real_tokens = (set(mp["ports"]) | set(mp["groups"]) | set(mp["insts"]) | set(mp["nets"]) | {mp["design"]})
        real_tokens -= {"CLK", "RST", "VPWR", "VGND"} | GENERIC   # generic words identify nothing
        real_tokens = {t for t in real_tokens if t not in set(mp["ports"].values()) | set(mp["insts"].values())
                       | set(mp["nets"].values())}
        for f in sorted(glob.glob(os.path.join(a.pins, "packets", P, "**", "*"), recursive=True)):
            if os.path.isdir(f):
                continue
            nfiles += 1
            text = gzip.open(f, "rt").read() if f.endswith(".gz") else open(f, errors="ignore").read()
            low = text.lower()
            for s in names:
                if re.search(r"(?<![A-Za-z0-9])" + re.escape(s.lower()) + r"(?![A-Za-z0-9])", low):
                    hits.append((P, os.path.basename(f), "design/module name", s))
            for s in tags | pointers:
                if s.lower() in low:
                    hits.append((P, os.path.basename(f), "tag/pointer", s))
            for s in distinctive:
                if re.search(r"(?<![A-Za-z0-9_])" + re.escape(s) + r"(?![A-Za-z0-9_])", text):
                    hits.append((P, os.path.basename(f), "real port name", s))
            if f.endswith((".json", ".json.gz", ".jsonl.gz")):
                docs = ([json.loads(x) for x in text.splitlines() if x.strip()] if f.endswith(".jsonl.gz")
                        else [json.loads(text)])
                strs = set()
                for d in docs:
                    json_strings(d, strs, names_keyed=False)
                for t in sorted(strs):
                    parts = {t, unesc(t)} | set(re.split(r"[/:]", unesc(t)))
                    for q in sorted(parts & real_tokens):
                        hits.append((P, os.path.basename(f), "real name in JSON value", q))
            elif f.endswith(".def.gz"):
                toks = {unesc(t) for t in word.findall(text)}
                for t in sorted(toks & real_tokens):
                    hits.append((P, os.path.basename(f), "real name token in DEF", t))
    rep = {"files_scanned": nfiles, "packets": len(index), "forbidden_design_or_module_names": len(names),
           "tags": len(tags), "pointers": sorted(pointers), "distinctive_port_names": len(distinctive), "hits": hits}
    json.dump(rep, open(os.path.join(a.private, "leak_test.json"), "w"), indent=1)
    print(f"[leak] scanned {nfiles} files in {len(index)} packets against {len(names)} design/module names, "
          f"{len(tags)} tags, {len(pointers)} pointers, {len(distinctive)} distinctive port names and every real "
          f"instance/net/port name: {len(hits)} hits")
    for h in hits[:40]:
        print("   ", h)
    return 1 if hits else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "script", "plans", "leak"])
    ap.add_argument("--pins", default=PINS)
    ap.add_argument("--private", default=PRIVATE)
    ap.add_argument("--captures")
    ap.add_argument("--arm", choices=["script", "claude"])
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args()
    return {"build": cmd_build, "script": cmd_script, "plans": cmd_plans, "leak": cmd_leak}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
