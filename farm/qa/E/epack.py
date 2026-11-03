#!/usr/bin/env python3
"""Experiment E packer (format E1.0): one run's record -> one blind packet directory.

Every design, module, port, net and instance name, file path and run tag is replaced by a stable per-packet pseudonym
(salted SHA-256; the same object gets the same pseudonym in every file of the packet). Library cell and pin names,
layers and corners are kept. Used for the test packets (run directories with capture/) and for train_E (historical
runs, no layout). See PACKET_FORMAT.md (outbox) / docs/qa_week/E_PREREG.md.

API: build_packet(src_dir, out_dir, salt, info, rung, layout=True) -> manifest dict
  src_dir : a results/<tag>/ directory (metrics.json, resolved.json, checks/, nets.jsonl[.gz], nets_signoff.jsonl[.gz],
            final_nets.json[.gz], labels.json, capture/ when captured)
  info    : {"packet_id", "T0", "drv_bar", "settings"}  (settings = non-clock overrides)
  rung    : 1 (contract + summary only) or 2 (everything)
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import os
import re

FORMAT = "E1.0"
CORNERS = ["nom_tt_025C_1v80", "nom_ss_100C_1v60", "nom_ff_n40C_1v95", "min_tt_025C_1v80", "min_ss_100C_1v60",
           "min_ff_n40C_1v95", "max_tt_025C_1v80", "max_ss_100C_1v60", "max_ff_n40C_1v95"]
HEX = 10
TOOLPRE = re.compile(r"^(clkbuf_leaf|clkbuf|clkload|max_cap|max_length|load_slew|hold|input|output|wire|fanout|"
                     r"rebuffer|split|place|delaybuf|ANTENNA|PHY_EDGE_ROW|TAP|FILLER|clone)(?=[_\d]|$)")
IDX = re.compile(r"((?:\[\d+\])+)$")
SUPPLY = {"VPWR", "VGND", "VPB", "VNB", "vccd1", "vssd1", "vccd2", "vssd2", "vdda1", "vssa1", "VDD", "VSS", "vdd", "vss"}
CHAIN_RULE = ("Same settings, only the clock changes. Rebuild at R1 = ceil05(C0) (C0 rounded up to 0.05 ns). After a "
              "passing rebuild with claim C: rebuild at ceil05(C) while that is below the chain's smallest passing clock "
              "and above every failed clock of the chain below it. If the first rebuild fails: step back once, to "
              "max(ceil05(C1), R1 + 0.05), unless that is not below the chain's smallest passing clock (the source's own "
              "target counts if the source passed); a failure after that ends the chain. At most 4 rebuilds. Kept clock = "
              "the smallest passing clock of the chain, the source included (none if no run passed).")
TASK = ("You see one finished routed run (the source) of a digital block, asked to run at target T0. A tuner would "
        "report its claimed clock C0 = T0 - worst setup slack. The same settings will now be rebuilt at R1 = ceil05(C0) "
        "and then follow the registered chain. Predict, without any new run: (a) p_pass, the probability that the "
        "rebuild at R1 passes the judge, and a call pass/fail/abstain; (b) slope = (C1 - C0)/(R1 - T0), where C1 is "
        "the rebuild's own claimed clock; (c) kept_clock_ns, the clock the registered chain keeps (null if you predict "
        "that no run of the chain passes; a passing source's own target counts). Units: ns.")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def jload(p):
    if os.path.exists(p):
        return json.load(open(p))
    if os.path.exists(p + ".gz"):
        return json.load(gzip.open(p + ".gz", "rt"))
    return None


def open_text(p):
    if os.path.exists(p):
        return open(p, errors="replace")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="replace")
    return None


def canon(tok):
    return tok.replace("\\", "")


def split_idx(c):
    m = IDX.search(c)
    if m and m.start() > 0:
        return c[:m.start()], m.group(1)
    return c, ""


class Namer:
    def __init__(self, salt, design, clock_port=None):
        self.salt = salt
        self.B = {}
        self.used = set()
        self.design = design
        self.clock = clock_port
        self.B[design] = "top"
        self.used.add("top")
        if clock_port:
            self.B[clock_port] = "clk"
            self.used.add("clk")

    def _h(self, s, n):
        return hashlib.sha256((self.salt + "\0" + s).encode()).hexdigest()[:n]

    def add(self, name, kind, direction=None):
        """Register a full (possibly escaped, possibly indexed) name; the base (name minus trailing [i] groups) gets a
        pseudonym of the kind's class. Supply nets/pins (VPWR, VGND, ...) are generic and kept."""
        if not name or canon(name) in SUPPLY:
            return
        c = canon(name)
        b, _ = split_idx(c)
        if b in self.B:
            return
        if kind == "port":
            pre = {"in": "pi", "out": "po"}.get(direction, "pio")
        elif kind == "inst":
            m = TOOLPRE.match(b)
            pre = m.group(1) if m else "u"
        else:
            pre = "clknet" if b.startswith("clknet") else "n"
        n = HEX
        while True:
            p = f"{pre}_{self._h(b, n)}"
            if p not in self.used:
                break
            n += 2
        self.B[b] = p
        self.used.add(p)

    def get(self, tok):
        """Pseudonym for a token in the token's own escaping style, or None when it is not a registered name."""
        if not tok:
            return None
        c = canon(tok)
        b, i = split_idx(c)
        p = self.B.get(b)
        if p is None:
            return None
        if i and "\\[" in tok:
            i = i.replace("[", "\\[").replace("]", "\\]")
        return p + i

    def m(self, tok):
        r = self.get(tok)
        return tok if r is None else r

    def pin(self, s):
        """'inst/PIN' -> 'pseudo/PIN'; 'PORT:p' -> 'PORT:pseudo'; bare port name -> pseudo."""
        if s is None:
            return None
        if s.startswith("PORT:"):
            return "PORT:" + self.m(s[5:])
        if "/" in s:
            a, b = s.rsplit("/", 1)
            return self.m(a) + "/" + b
        return self.m(s)


# ------------------------------------------------------------------ name collection

def collect_names(src, nm):
    """Register every port, instance and net name found in the run's files (ports first, then instances, nets)."""
    ports, insts, nets = {}, set(), set()
    fn = jload(os.path.join(src, "final_nets.json"))
    dumps = []
    for f in ("nets.jsonl", "nets_signoff.jsonl"):
        fh = open_text(os.path.join(src, f))
        if fh:
            dumps.append([json.loads(l) for l in fh if l.strip()])
    deftxt = None
    dp = os.path.join(src, "capture", "final.def")
    fh = open_text(dp)
    if fh:
        deftxt = fh.read()
    if fn:
        for net, v in fn["nets"].items():
            nets.add(net)
            drv = v.get("driver") or ""
            if drv.startswith("PORT:"):
                ports[drv[5:]] = "in"
            for p in v.get("pins") or []:
                if "/" in p:
                    insts.add(p.rsplit("/", 1)[0])
                elif not drv.startswith("PORT:") or p != drv[5:]:
                    ports.setdefault(p, "out")
            if "/" in drv:
                insts.add(drv.rsplit("/", 1)[0])
    for rows in dumps:
        for r in rows:
            nets.add(r["net"])
            if r.get("driver_kind") == "port":
                ports[r["driver_pin"]] = "in"
            elif r.get("driver_inst"):
                insts.add(r["driver_inst"])
            for k in r.get("load_keys") or []:
                if k.startswith("PORT:"):
                    ports.setdefault(k[5:], "out")
                elif "/" in k:
                    insts.add(k.rsplit("/", 1)[0])
    if deftxt:
        sec = None
        for line in deftxt.splitlines():
            s = line.strip()
            w = s.split()
            if not w:
                continue
            if w[0] in ("COMPONENTS", "PINS", "NETS", "SPECIALNETS"):
                sec = w[0]
                continue
            if w[0] == "END":
                sec = None
                continue
            if sec == "COMPONENTS" and w[0] == "-":
                insts.add(w[1])
            elif sec == "PINS" and w[0] == "-":
                if "USE POWER" in s or "USE GROUND" in s:
                    continue
                d = "in" if "INPUT" in s else ("out" if "OUTPUT" in s else "inout")
                ports[w[1]] = d if w[1] not in ports else ports[w[1]]
                if "NET" in w:
                    nets.add(w[w.index("NET") + 1])
            elif sec == "NETS" and w[0] == "-":
                nets.add(w[1])
    for p, d in sorted(ports.items()):
        nm.add(p, "port", d)
    for i in sorted(insts):
        nm.add(i, "inst")
    for n in sorted(nets):
        nm.add(n, "net")
    return {"ports": ports, "n_insts": len(insts), "n_nets": len(nets)}


# ------------------------------------------------------------------ rewriters

def rw_dump_rows(rows, nm):
    out = []
    for r in rows:
        r = dict(r)
        r["net"] = nm.m(r["net"])
        if r.get("driver_kind") == "port":
            r["driver_pin"] = nm.m(r.get("driver_pin"))
        if r.get("driver_inst"):
            r["driver_inst"] = nm.m(r["driver_inst"])
        r["load_keys"] = [nm.pin(k) for k in (r.get("load_keys") or [])]
        out.append(r)
    return out


def rw_connectivity(fn, nm):
    nets = {}
    for net, v in fn["nets"].items():
        nets[nm.m(net)] = {"sigtype": v.get("sigtype"), "driver": nm.pin(v.get("driver")),
                           "pins": [nm.pin(p) for p in v.get("pins") or []], "fanout": v.get("fanout")}
    return {"nets": nets}


def rw_drv(lab, nm):
    s = dict(lab.get("summary") or {})
    for k in ("run_dir", "sta_dir", "unmapped_pins"):
        s.pop(k, None)
    nets = []
    for r in lab.get("nets") or []:
        r = dict(r)
        r["net"] = nm.m(r.get("net"))
        if r.get("driver_s"):
            r["driver_s"] = nm.pin(r["driver_s"])
        if r.get("pins"):
            r["pins"] = [nm.pin(p) for p in r["pins"]]
        nets.append(r)
    return {"summary": s, "nets": nets}


STOP = set("""data arrival required time clock slack network delay propagated source latency uncertainty reconvergence
pessimism library setup hold recovery removal input output external edge rise fall max min net in out inout rising
falling by clocked port Corner Path Group Type Startpoint Endpoint Fanout Cap Slew Delay Time Description MET VIOLATED
check checks unconstrained asynchronous ideal total Pin Limit Slack internal switching leakage power Sequential
Combinational Clock Macro Pad Total group report_checks report reg2reg in2reg reg2out in2out wns tns ws worst flip
flop triggered latch gating gated positive negative level sensitive Startpoint: Endpoint: max_slew max_capacitance
max_fanout Group: Type: Summary Corner: Hold Setup Violations Instance Required Actual Skew Latency CRPR""".split())
RID = re.compile(r"[A-Za-z_\\][A-Za-z0-9_\\\[\]\.\$/]*")
FORCE_AFTER = re.compile(r"^\s*\((in|out|inout|net)\)")


def rw_text(text, nm):
    """STA report / free text: replace registered names; 'inst/PIN' keeps the pin; port and net names before
    '(in)/(out)/(net)' and clock names in 'clock X (rise edge)' / 'clocked by X' are always replaced."""
    out = []
    for line in text.splitlines(True):
        res, pos = [], 0
        for mt in RID.finditer(line):
            tok = mt.group(0)
            rep = None
            if "/" in tok:
                a, b = tok.rsplit("/", 1)
                ma = nm.get(a)
                if ma is not None:
                    rep = ma + "/" + b
            else:
                after = line[mt.end():]
                before = line[:mt.start()]
                forced = bool(FORCE_AFTER.match(after)) or before.endswith("clocked by ") or \
                    (before.rstrip().endswith("clock") and re.match(r"^\s*\((rise|fall) edge\)", after) is not None) or \
                    before.endswith("Clock ") or before.endswith("-clock ") or before.endswith("clock_uncertainty ") or \
                    before.endswith("Path Group: ")
                if tok not in STOP or forced:
                    rep = nm.get(tok)
            if rep is not None and rep != tok:
                res.append(line[pos:mt.start()])
                res.append(rep)
                pos = mt.end()
        res.append(line[pos:])
        out.append("".join(res))
    return "".join(out)


DEF_TUPLE = re.compile(r"\(\s+(\S+)\s+(\S+)(\s+\+\s+SYNTHESIZED)?\s+\)")


def rw_def(text, nm):
    out = []
    sec = None
    for line in text.splitlines(True):
        w = line.split()
        if w:
            if w[0] == "DESIGN":
                out.append("DESIGN top ;\n")
                continue
            if w[0] in ("COMPONENTS", "PINS", "NETS", "SPECIALNETS", "GROUPS", "REGIONS", "BLOCKAGES", "VIAS",
                        "NONDEFAULTRULES", "PROPERTYDEFINITIONS"):
                sec = w[0]
            elif w[0] == "END" and len(w) > 1:
                sec = None
        if sec == "COMPONENTS" and w and w[0] == "-":
            line = line.replace(" " + w[1] + " ", " " + nm.m(w[1]) + " ", 1)
        elif sec == "PINS" and w:
            if w[0] == "-":
                line = line.replace("- " + w[1] + " ", "- " + nm.m(w[1]) + " ", 1)
            if "NET" in w:
                n = w[w.index("NET") + 1]
                line = line.replace("NET " + n, "NET " + nm.m(n), 1)
        elif sec in ("NETS", "SPECIALNETS"):
            if w and w[0] == "-" and sec == "NETS":
                line = line.replace("- " + w[1], "- " + nm.m(w[1]), 1)

            def tup(mt):
                a, b, syn = mt.group(1), mt.group(2), mt.group(3) or ""
                if a == "PIN":
                    return f"( PIN {nm.m(b)}{syn} )"
                if a == "*" or re.match(r"^-?\d+$", a):
                    return mt.group(0)
                return f"( {nm.m(a)} {b}{syn} )"
            line = DEF_TUPLE.sub(tup, line)
        out.append(line)
    return "".join(out)


SPEF_HDR = ("*SPEF", "*DESIGN", "*DATE", "*VENDOR", "*PROGRAM", "*VERSION", "*DESIGN_FLOW", "*DIVIDER", "*DELIMITER",
            "*BUS_DELIMITER", "*T_UNIT", "*C_UNIT", "*R_UNIT", "*L_UNIT")
NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _spef_name(t, nm):
    r = nm.get(t)
    if r is not None:
        return r
    if ":" in t:
        a, b = t.rsplit(":", 1)
        ra = nm.get(a)
        if ra is not None:
            return ra + ":" + b
    if "/" in t:
        a, b = t.rsplit("/", 1)
        ra = nm.get(a)
        if ra is not None:
            return ra + "/" + b
    return t


def rw_spef(text, nm):
    """SPEF: header *DESIGN -> top; *NAME_MAP names; every other name token (ports in *PORTS/*P, nets, inst:pin and
    net:node references written without the map) is rewritten; indices (*N), numbers and directions are kept."""
    out = []
    in_map = False
    for line in text.splitlines(True):
        s = line.strip()
        w = s.split()
        if not w:
            out.append(line)
            continue
        if w[0] == "*DESIGN":
            out.append('*DESIGN "top"\n')
            continue
        if w[0] in SPEF_HDR:
            out.append(line)
            continue
        if w[0] == "*NAME_MAP":
            in_map = True
            out.append(line)
            continue
        if in_map:
            if len(w) == 2 and w[0].startswith("*") and w[0][1:].isdigit():
                out.append(f"{w[0]} {_spef_name(w[1], nm)}\n")
                continue
            in_map = False
        toks = re.split(r"(\s+)", line)
        for i, t in enumerate(toks):
            if not t or t.isspace() or t.startswith("*") or t in ("I", "O", "B") or NUM.match(t):
                continue
            toks[i] = _spef_name(t, nm)
        out.append("".join(toks))
    return "".join(out)


VID = re.compile(r"\\\S+|[A-Za-z_][A-Za-z0-9_$]*")
VKEY = set("""module endmodule input output inout wire reg assign supply0 supply1 tri wand wor parameter localparam begin
end always initial if else case endcase posedge negedge or and not buf generate endgenerate genvar integer function
endfunction task endtask specify endspecify signed unsigned""".split())


def rw_verilog(text, nm):
    out = []
    for line in text.splitlines(True):
        res, pos = [], 0
        for mt in VID.finditer(line):
            tok = mt.group(0)
            before = line[:mt.start()].rstrip()
            if before.endswith(".") or before.endswith("'") or tok in VKEY or tok.startswith("sky130_"):
                continue
            if tok.startswith("\\"):
                r = nm.get(tok[1:])
                rep = None if r is None else "\\" + r
            else:
                rep = nm.get(tok)
            if rep is not None and rep != tok:
                res.append(line[pos:mt.start()])
                res.append(rep)
                pos = mt.end()
        res.append(line[pos:])
        out.append("".join(res))
    return "".join(out)


SID = re.compile(r"[A-Za-z_\\][A-Za-z0-9_\\\[\]\.\$/]*")


def rw_sdc(text, nm):
    out = []
    for line in text.splitlines(True):
        if line.lstrip().startswith("#"):
            out.append(line)
            continue
        res, pos = [], 0
        for mt in SID.finditer(line):
            tok = mt.group(0)
            before = line[:mt.start()]
            if before.endswith("-") or re.search(r"-(pin|lib_cell)\s+$", before):
                continue
            rep = nm.get(tok)
            if rep is not None and rep != tok:
                res.append(line[pos:mt.start()])
                res.append(rep)
                pos = mt.end()
        res.append(line[pos:])
        out.append("".join(res))
    return "".join(out)


# ------------------------------------------------------------------ summaries, contract

def drv_count(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def summary_text(m, bar):
    """The compact signoff summary (farm/tune_a32.py diagnostics(), without run time) + a 9-corner table."""
    corners = sorted({k.split("corner:")[1] for k in m if k.startswith("timing__setup__ws__corner:")})
    ws = {c: m["timing__setup__ws__corner:" + c] for c in corners}
    hs = {c: m.get("timing__hold__ws__corner:" + c) for c in corners}
    cw = min(ws, key=ws.get)
    ch = min((c for c in corners if hs[c] is not None), key=lambda c: hs[c], default=None)
    worst_ws, r2r = m.get("timing__setup__ws"), m.get("timing__setup_r2r__ws")
    io_limited = r2r is not None and worst_ws is not None and worst_ws < r2r - 1e-3
    slew = max([m.get(k) or 0 for k in m if k.startswith("design__max_slew_violation__count__corner:")] or [0])
    cap = max([m.get(k) or 0 for k in m if k.startswith("design__max_cap_violation__count__corner:")] or [0])
    fo = m.get("design__max_fanout_violation__count") or 0
    drc_it = [m.get(f"route__drc_errors__iter:{i}") for i in range(0, 64) if m.get(f"route__drc_errors__iter:{i}") is not None]
    wl, wl_est = m.get("route__wirelength"), m.get("route__wirelength__estimated")
    lines = [
        f"  setup: worst slack {worst_ws:+.3f} ns at {cw} (reg-to-reg worst {r2r:+.3f} ns"
        f"{'; the worst path touches an input/output port' if io_limited else ''}); TNS {m.get('timing__setup__tns', 0):.2f} ns; "
        f"{m.get('timing__setup_vio__count', 0)} violating endpoints at the target",
        f"  hold: worst slack {m.get('timing__hold__ws', 0):+.3f} ns" + (f" at {ch}" if ch else "")
        + f"; {m.get('timing__hold_vio__count', 0)} violations; {m.get('design__instance__count__hold_buffer', 0)} hold buffers inserted",
        f"  electrical: {drv_count(m)} slew/cap pins summed over corners (bar {bar}); worst corner max-slew {slew}, max-cap {cap}; "
        f"fanout violations {fo}",
        f"  cells: {m.get('design__instance__count__stdcell', 0)} std cells, {m.get('design__instance__count__class:timing_repair_buffer', 0)} "
        f"timing-repair buffers; std-cell area {m.get('design__instance__area__stdcell', 0):,.0f} um2; utilisation "
        f"{100 * (m.get('design__instance__utilization') or 0):.0f}%",
        f"  routing: wirelength {wl or 0:,.0f} um (pre-route estimate {wl_est or 0:,.0f}); detailed-route DRC by iteration "
        f"{drc_it[:6]}{'...' if len(drc_it) > 6 else ''}, final {m.get('route__drc_errors', 0)}",
        f"  clock: skew {m.get('clock__skew__worst_setup', 0):.3f} ns (setup) / {m.get('clock__skew__worst_hold', 0):.3f} ns (hold); "
        f"power {1000 * (m.get('power__total') or 0):.2f} mW",
    ]
    tab = ["", "  corner              setup WS   setup TNS  setup vio  r2r setup WS   hold WS   hold vio",
           "  ------------------  ---------  ---------  ---------  ------------  --------  --------"]
    for c in corners:
        tab.append(f"  {c:18s}  {ws[c]:+9.3f}  {m.get('timing__setup__tns__corner:' + c, 0):9.3f}  "
                   f"{m.get('timing__setup_vio__count__corner:' + c, 0):9d}  {m.get('timing__setup_r2r__ws__corner:' + c, float('nan')):+12.3f}  "
                   f"{(hs[c] if hs[c] is not None else float('nan')):+8.3f}  {m.get('timing__hold_vio__count__corner:' + c, 0):8d}")
    return "Signoff summary of the source run (9 corners; ns)\n" + "\n".join(lines + tab) + "\n"


def contract(info, m, r):
    T0 = float(info["T0"])
    ws, wr = m.get("timing__setup__ws"), m.get("timing__setup_r2r__ws")
    C0 = T0 - ws
    return {
        "format": FORMAT, "packet_id": info["packet_id"],
        "flow": "LibreLane 3.0.16 (Yosys/ABC, OpenROAD, OpenRCX, OpenSTA) on SkyWater sky130A, sky130_fd_sc_hd cells; "
                "deterministic (identical settings and clock give bit-identical results)",
        "units": {"time": "ns", "capacitance": "pF (output_load_ff in fF)", "length": "um", "area": "um^2", "power": "W"},
        "corners": CORNERS,
        "corner_meaning": "{min,nom,max} = OpenRCX RC corner; tt 25C 1.80V, ss 100C 1.60V, ff -40C 1.95V",
        "constraints": {
            "clock": "one clock, on port 'clk'",
            "clock_uncertainty_ns": float(r.get("CLOCK_UNCERTAINTY_CONSTRAINT", 0.25)),
            "timing_derate_pct": float(r.get("TIME_DERATING_CONSTRAINT", 5)),
            "io_delay_pct_of_period": float(r.get("IO_DELAY_CONSTRAINT", 20)),
            "io_delay_rule": "input delay and output delay = io_delay_pct_of_period % of the clock period on every "
                             "non-clock port, relative to the clock (they scale with the target)",
            "output_load_ff": float(r.get("OUTPUT_CAP_LOAD", 0) or 0),
            "input_driving_cell": r.get("SYNTH_DRIVING_CELL"),
            "clock_transition_ns": float(r.get("CLOCK_TRANSITION_CONSTRAINT", 0.15) or 0.15),
            "max_transition_ns": float(r.get("MAX_TRANSITION_CONSTRAINT", 0.75) or 0.75),
            "max_capacitance_pf": float(r.get("MAX_CAPACITANCE_CONSTRAINT", 0.2) or 0.2),
            "max_fanout": float(r.get("MAX_FANOUT_CONSTRAINT", 10) or 10)},
        "settings": info.get("settings") or {},
        "source": {"target_ns": T0, "worst_setup_slack_ns": ws, "claim_ns": C0, "r2r_worst_setup_slack_ns": wr,
                   "port_limited": bool(ws is not None and wr is not None and ws < wr - 1e-4),
                   "worst_hold_slack_ns": m.get("timing__hold__ws"), "route_drc": m.get("route__drc_errors"),
                   "drv_count": drv_count(m),
                   "passes_judge": bool(ws >= 0 and (m.get("timing__hold__ws") or -1) >= 0 and
                                        (m.get("route__drc_errors") or 0) == 0 and drv_count(m) <= info["drv_bar"])},
        "judge": {"pass": "setup WS >= 0 and hold WS >= 0 at all 9 corners, detailed-route DRC = 0, and max-slew + "
                          "max-cap violation count (9 corners summed) <= drv_bar; a rebuild without results fails",
                  "drv_bar": info["drv_bar"]},
        "chain": {"R1_ns": ceil05(C0), "grid_ns": 0.05, "max_rebuilds": 4, "rule": CHAIN_RULE},
        "task": TASK,
    }


# ------------------------------------------------------------------ packet

def _wjson(p, obj, gz=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if gz:
        with gzip.open(p, "wt", compresslevel=6) as f:
            json.dump(obj, f, separators=(",", ":"))
    else:
        json.dump(obj, open(p, "w"), indent=1)


def _wtext(p, text, gz=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if gz:
        with gzip.open(p, "wt", compresslevel=6) as f:
            f.write(text)
    else:
        open(p, "w").write(text)


def build_packet(src, out, salt, info, rung=2, layout=True, shuffle_seed=None, write_connectivity=True):
    m = json.load(open(os.path.join(src, "metrics.json")))
    r = json.load(open(os.path.join(src, "resolved.json")))
    design = r.get("DESIGN_NAME")
    nm = Namer(salt, design, r.get("CLOCK_PORT"))
    names = collect_names(src, nm)
    os.makedirs(out, exist_ok=True)
    _wjson(os.path.join(out, "contract.json"), contract(info, m, r))
    _wtext(os.path.join(out, "reports", "summary.txt"), summary_text(m, info["drv_bar"]))
    if rung >= 2:
        _wjson(os.path.join(out, "metrics.json"), m)
        cdir = os.path.join(src, "checks")
        if os.path.isdir(cdir):
            for f in sorted(os.listdir(cdir)):
                fh = open_text(os.path.join(cdir, f.replace(".gz", "")))
                _wtext(os.path.join(out, "reports", "checks", f.replace(".gz", "")), rw_text(fh.read(), nm))
        for f, dst in (("nets.jsonl", "postgrt"), ("nets_signoff.jsonl", "signoff")):
            fh = open_text(os.path.join(src, f))
            if fh:
                rows = rw_dump_rows([json.loads(l) for l in fh if l.strip()], nm)
                if shuffle_seed is not None:
                    rows = shuffle_rows(rows, shuffle_seed)
                buf = "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in rows)
                _wtext(os.path.join(out, "nets", dst + ".jsonl.gz"), buf, gz=True)
        fn = jload(os.path.join(src, "final_nets.json"))
        if fn and write_connectivity:
            _wjson(os.path.join(out, "nets", "connectivity.json.gz"), rw_connectivity(fn, nm), gz=True)
        lab = jload(os.path.join(src, "labels.json"))
        if lab:
            _wjson(os.path.join(out, "nets", "drv.json"), rw_drv(lab, nm))
        cap = os.path.join(src, "capture")
        if layout and shuffle_seed is None and os.path.isdir(cap):
            fh = open_text(os.path.join(cap, "final.def"))
            if fh:
                _wtext(os.path.join(out, "layout", "final.def.gz"), rw_def(fh.read(), nm), gz=True)
            fh = open_text(os.path.join(cap, "final.nl.v"))
            if fh:
                _wtext(os.path.join(out, "layout", "final.nl.v.gz"), rw_verilog(fh.read(), nm), gz=True)
            fh = open_text(os.path.join(cap, "final.sdc"))
            if fh:
                _wtext(os.path.join(out, "layout", "final.sdc"), rw_sdc(fh.read(), nm))
            sdir = os.path.join(cap, "spef")
            if os.path.isdir(sdir):
                for f in sorted(os.listdir(sdir)):
                    fh = open_text(os.path.join(sdir, f.replace(".gz", "")))
                    _wtext(os.path.join(out, "layout", "spef", f if f.endswith(".gz") else f + ".gz"),
                           rw_spef(fh.read(), nm), gz=True)
            for sub, dst in (("sta_postpnr", "postpnr"), ("sta_postgrt", "postgrt")):
                sd = os.path.join(cap, sub)
                if not os.path.isdir(sd):
                    continue
                for root, _, files in os.walk(sd):
                    for f in sorted(files):
                        rel = os.path.relpath(os.path.join(root, f), sd)
                        fh = open_text(os.path.join(root, f.replace(".gz", "")))
                        txt = rw_text(fh.read(), nm)
                        _wtext(os.path.join(out, "sta", dst, rel if rel.endswith(".gz") else rel + ".gz"), txt, gz=True)
    man = {"format": FORMAT, "packet_id": info["packet_id"], "rung": rung, "files": {}}
    for root, _, files in os.walk(out):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, out)
            if rel == "MANIFEST.json":
                continue
            man["files"][rel] = {"bytes": os.path.getsize(p), "sha256": sha256_file(p)}
    _wjson(os.path.join(out, "MANIFEST.json"), man)
    return {"packet_id": info["packet_id"], "names": names, "map": nm.B}


SHUF_FIELDS = ["driver_x_um", "driver_y_um", "hpwl_um", "bbox_w_um", "bbox_h_um", "density_mean", "density_max",
               "guide_len_um", "guide_len_by_layer_um", "net_cap_pf_by_corner", "net_cap_pf_max", "pin_cap_pf_by_corner",
               "pin_cap_pf_max", "driver_slew_ns", "worst_load_slew_ns", "driver_slew_ratio", "worst_load_slew_ratio",
               "cap_ratio"]


def shuffle_rows(rows, seed):
    """Shuffled-view diagnostic: permute the geometric/electrical fields among nets with the same driver cell and
    fanout (totals preserved); connectivity, slack and names stay with their nets."""
    import random
    rng = random.Random(seed)
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault((r.get("driver_master"), r.get("fanout"), r.get("is_clock")), []).append(i)
    out = [dict(r) for r in rows]
    for idx in groups.values():
        if len(idx) < 2:
            continue
        perm = idx[:]
        rng.shuffle(perm)
        for dst, srci in zip(idx, perm):
            for f in SHUF_FIELDS:
                out[dst][f] = rows[srci].get(f)
    return out
