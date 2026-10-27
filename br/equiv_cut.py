#!/usr/bin/env python3
"""State-cut transition equivalence of two mapped netlists of one design.

Method adapted from AfterClock's state-cut transition check.

Usage:
  python3 br/equiv_cut.py --gold <gold.nl.v[.gz]> --gate <gate.nl.v[.gz]> --top <module>
                          --liberty <lib> --out <dir> [--timeout S] [--negative-control]
                          [--engine abc|yosys-sat] [--yosys <bin>] [--abc <bin>] [--keep]
  Exit code 0 when the status is the expected one (PROVED; COUNTEREXAMPLE under
  --negative-control), 1 otherwise. yosys comes from --yosys, $YOSYS or PATH; yosys-abc from
  --abc, $YOSYS_ABC or next to yosys. Pass the plain netlists (nl.v), not powered ones.

Method
  gold = a baseline netlist, gate = the same design after a repair that only resizes
  cells and inserts buffers (flop instance names preserved, flops possibly resized).
  1. Each netlist is read with the Liberty functional models (physical-only cells
     dropped, as in br/equiv.py), so every combinational cell is real logic.
  2. Every sequential cell (flip-flop or latch: any Liberty ff/latch group) is cut:
       - its state becomes a new primary input named after the instance,
         "q:<instance>"; Q is driven by it and Q_N by its complement;
       - every non-clock input pin (D, RESET_B, SET_B, DE, SCD, SCE, ...) becomes a
         new primary output named after the instance and pin, "d:<instance>:<pin>".
     Sequential cells are matched by instance name. An unmatched cell, a matched pair
     whose Liberty function class differs (dfxtp_1 -> dfxtp_4 keeps the class,
     dfxtp -> dfrtp does not), or a clock pin that does not trace through buffers and
     inverters to the same root with the same polarity in both netlists is FAIL_MATCH,
     listed per cell. Every clock root is reported (normally "port:<clock port>").
     Integrated clock gates on a clock path are part of the traced root and their enable
     pins are compared like data pins. A root that is another flop's output is matched
     by that flop's name; a root that is a logic cell (a hand-made clock gate) is matched
     by name and its function is also compared, as an output "clk:<cell>:<pin>".
  3. What remains is purely combinational: one function from (primary inputs, current
     state) to (primary outputs, every sequential data/control input pin). Both cut
     netlists are flattened and written as AIGs; their symbol tables must be identical
     (same input and output names, same order). ABC proves every output pair equal:
       &cec gold.aig gate.aig      (SAT sweeping on the paired miter; complete)
     (Not "&cec -m" on a single multi-output miter: that mode silently checks only the
     first output. Not Yosys' -map file for output names: it omits constant outputs; the
     AIG symbol table is used instead.) --engine yosys-sat runs the Yosys recipe
       miter -equiv -flatten -make_assert; sat -verify -prove-asserts -set-def-inputs
     instead (several times slower; an independent cross-check).
  4. --negative-control inserts an inverter on the D pin of one flop of the gate copy
     (the first flop in name order whose D is driven by logic) before the cut. The
     check must then return COUNTEREXAMPLE naming d:<that flop>:D; anything else is
     CONTROL_FAILED (the underlying status is kept in the result).
  5. <out>/result.json: status (PROVED | COUNTEREXAMPLE | FAIL_MATCH | ERROR | TIMEOUT, or
     CONTROL_FAILED under --negative-control), flops_cut, outputs_compared, seconds,
     assumptions, plus the clock and matching reports, the differing outputs of a
     counterexample, per-step seconds and peak memory (peak_mb: largest resident set of
     this process or any tool it ran). Next to it: equiv_cut.log (run log), the Yosys
     scripts and logs, prove.log (ABC). --keep also keeps the netlists, JSON and AIGs.

What PROVED means, and what it does not
  It proves the next-state and output functions equal under equal current state: for
  every current state and every input vector, both netlists produce the same primary
  outputs and the same value at every sequential input pin (next state, asynchronous
  reset/set, enable, scan). With matched cells and matched clocks, two netlists that
  start in the same state therefore stay in the same state and produce the same
  outputs on every cycle (induction over clock edges; this check is the step).
  It is NOT a reset or base-case proof, and NOT RTL equivalence (see Limits).

Assumptions (also written to result.json)
  mapped vs mapped; equal initial state; zero-delay; clocks matched by name.

Limits
  * Not a reset / base-case proof. Nothing is shown about the state either netlist
    powers up or resets into; equal initial state is assumed, not checked.
  * Not RTL equivalence: both sides are mapped netlists, so it says nothing about the
    netlists against the RTL. Not timing: Liberty functions are evaluated with zero
    delay; glitches, setup/hold and skew are out of scope.
  * Complete only for state-matched designs. Retiming, flop merging/duplication or
    renaming (none of which a resize/buffer repair does) gives FAIL_MATCH or a
    counterexample even when the designs are sequentially equivalent.
  * A COUNTEREXAMPLE is a (state, input) pair on which a next-state or output function
    differs. The state may be unreachable from reset, so it is a real difference of the
    transition functions, not necessarily an observable failure.
  * Undriven nets or x/z constants inside the compared logic (none expected in a routed
    netlist) are modelled as free inputs shared by name between the two netlists and
    are listed in the result. Tri-state cells, inout ports and statetable cells other
    than clock gates are rejected (ERROR).
"""
import argparse
import gzip
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import time
import traceback

ASSUMPTIONS = "mapped vs mapped; equal initial state; zero-delay; clocks matched by name"
LIB_FLAGS = "-ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch"  # as in br/equiv.py
# physical-only cells without a Liberty logic function (taps are not in the Liberty at all);
# same rule as br/equiv.py, for any library prefix
PHYS = re.compile(r"^\s*\w+__(tapvpwrvgnd|fill|decap|diode)\w*\s+\S+\s*\(", re.M)
SIMPLE_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
VERILOG_KW = {"module", "endmodule", "input", "output", "inout", "wire", "assign", "reg", "begin", "end",
              "always", "initial", "if", "else", "case", "endcase", "for", "function", "task", "and", "or",
              "not", "nand", "nor", "xor", "xnor", "buf", "supply0", "supply1", "tri", "parameter", "signed"}


# ------------------------------------------------------------------------------------------ util
class Log:
    def __init__(self, path):
        self.f = open(path, "w")
        self.t0 = time.time()

    def __call__(self, msg):
        line = f"[{time.time() - self.t0:8.1f}s] {msg}"
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


def run_tool(cmd, log_path, deadline, cwd=None):
    """Run cmd with stdout/stderr to log_path; kill it at the deadline.
    Returns dict(rc, timed_out, seconds, peak_mb) using wait4 for the child's peak RSS."""
    t0 = time.time()
    with open(log_path, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=cwd, start_new_session=True)
        timed_out = False
        while True:
            pid, status, ru = os.wait4(p.pid, os.WNOHANG)
            if pid:
                break
            if time.time() > deadline:
                timed_out = True
                try:
                    os.killpg(p.pid, 9)
                except ProcessLookupError:
                    pass
                pid, status, ru = os.wait4(p.pid, 0)
                break
            time.sleep(0.2)
    p.returncode = os.waitstatus_to_exitcode(status)
    return {"rc": p.returncode, "timed_out": timed_out, "seconds": round(time.time() - t0, 2),
            "peak_mb": round(ru.ru_maxrss / 1024.0, 1)}


def aiger_symbols(path):
    """(input names, output names) from a binary AIGER file's symbol table, in AIG order.
    (Yosys' -map file leaves out outputs that are constants; the symbol table has them all.)"""
    data = open(path, "rb").read()
    pos = data.index(b"\n")
    hdr = data[:pos].split()
    if hdr[0] != b"aig":
        raise ValueError(f"{path}: not a binary AIGER file")
    nums = [int(x) for x in hdr[1:]] + [0] * 9
    _, n_i, n_l, n_o, n_a, n_b, n_c, n_j, n_f = nums[:9]
    pos += 1

    def skip(n):
        nonlocal pos
        for _ in range(n):
            pos = data.index(b"\n", pos) + 1

    skip(n_l + n_o + n_b + n_c)
    if n_j:
        cnt = 0
        for _ in range(n_j):
            e = data.index(b"\n", pos)
            cnt += int(data[pos:e])
            pos = e + 1
        skip(cnt)
    skip(n_f)
    for _ in range(2 * n_a):  # two LEB128 deltas per AND gate
        while data[pos] & 0x80:
            pos += 1
        pos += 1
    ins, outs = [None] * n_i, [None] * n_o
    for line in data[pos:].split(b"\n"):
        if line == b"c" or not line:
            break
        kind, rest = line[:1], line[1:].decode(errors="replace")
        idx, _, name = rest.partition(" ")
        if kind == b"i" and int(idx) < n_i:
            ins[int(idx)] = name
        elif kind == b"o" and int(idx) < n_o:
            outs[int(idx)] = name
    return ins, outs


def vname(name):
    """Verilog identifier for an arbitrary name (escaped when needed)."""
    if SIMPLE_ID.match(name) and name not in VERILOG_KW:
        return name
    return "\\" + name + " "


# --------------------------------------------------------------------------------------- liberty
def _unq(s):
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def parse_liberty(path):
    """Minimal Liberty reader: cell -> {pins: {pin: attrs}, seq: [(group, args, attrs)], attrs}."""
    txt = open(path, errors="replace").read()
    txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S).replace("\\\n", " ")
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|[{}();:,]|[^\s{}();:,"]+', txt)
    n = len(toks)
    sys.setrecursionlimit(10000)

    def body(i):
        attrs, groups = {}, []
        while i < n and toks[i] != "}":
            name = toks[i]
            i += 1
            if i < n and toks[i] == ":":
                attrs.setdefault(name, _unq(toks[i + 1]))
                i += 2
                if i < n and toks[i] == ";":
                    i += 1
            elif i < n and toks[i] == "(":
                i += 1
                args = []
                while toks[i] != ")":
                    if toks[i] != ",":
                        args.append(_unq(toks[i]))
                    i += 1
                i += 1
                if i < n and toks[i] == "{":
                    b, i = body(i + 1)
                    groups.append((name, args, b))
                elif i < n and toks[i] == ";":
                    i += 1
        return (attrs, groups), i + 1

    (_, top), _ = body(0)
    cells = {}
    keep_pin = ("direction", "function", "state_function", "clock", "three_state", "internal_node",
                "clock_gate_enable_pin", "clock_gate_clock_pin", "clock_gate_out_pin", "clock_gate_test_pin")
    for (lname, _largs, (_lattrs, lgroups)) in top:
        if lname != "library":
            continue
        for (gname, args, (attrs, groups)) in lgroups:
            if gname != "cell" or not args:
                continue
            c = {"name": args[0], "attrs": attrs, "pins": {}, "seq": [], "bus": False}
            for (g2, a2, (at2, _gr2)) in groups:
                if g2 == "pin":
                    for pn in a2:
                        c["pins"][pn] = {k: v for k, v in at2.items() if k in keep_pin}
                elif g2 in ("ff", "latch", "statetable", "ff_bank", "latch_bank"):
                    c["seq"].append((g2, a2, dict(at2)))
                elif g2 in ("bus", "bundle"):
                    c["bus"] = True
            cells[c["name"]] = c
    return cells


def _norm(f):
    f = re.sub(r"\s+", "", f or "")
    while f.startswith("(") and f.endswith(")"):
        depth, ok = 0, True
        for k, ch in enumerate(f):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and k < len(f) - 1:
                ok = False
                break
        if not ok:
            break
        f = f[1:-1]
    return f


def lib_eval(expr, env):
    """Evaluate a Liberty boolean function. Precedence (Liberty): ' and ! > ^ > & * space > | +."""
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_\[\]\.]*|[01]|[!'()^&*|+]", expr)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        pos[0] += 1
        return toks[pos[0] - 1]

    def unary():
        t = take()
        if t == "!":
            v = not unary()
        elif t == "(":
            v = p_or()
            if take() != ")":
                raise ValueError("unbalanced function " + expr)
        elif t in ("0", "1"):
            v = t == "1"
        else:
            v = bool(env[t])
        while peek() == "'":
            take()
            v = not v
        return v

    def p_xor():
        v = unary()
        while peek() == "^":
            take()
            v = v ^ unary()
        return v

    def p_and():
        v = p_xor()
        while peek() is not None and peek() not in ("|", "+", ")"):
            if peek() in ("&", "*"):
                take()
            v = p_xor() and v
        return v

    def p_or():
        v = p_and()
        while peek() in ("|", "+"):
            take()
            v = p_and() or v
        return v

    v = p_or()
    if pos[0] != len(toks):
        raise ValueError("trailing tokens in function " + expr)
    return v


def classify_liberty(cells):
    """cell name -> info dict with kind in phys | comb | buf | inv | seq | icg | unsupported."""
    out = {}
    for name, c in cells.items():
        pins = c["pins"]
        ins = sorted(p for p, v in pins.items() if v.get("direction") == "input")
        outs = sorted(p for p, v in pins.items() if v.get("direction") == "output")
        inouts = sorted(p for p, v in pins.items() if v.get("direction") == "inout")
        info = {"name": name, "inputs": ins, "outputs": outs, "kind": "comb", "why": ""}
        out[name] = info
        if c["bus"]:
            info.update(kind="unsupported", why="bus/bundle pins")
        elif not outs and not inouts:
            info["kind"] = "phys"
        elif inouts or any("three_state" in pins[p] for p in outs):
            info.update(kind="unsupported", why="tri-state or inout pin")
        elif c["seq"]:
            if len(c["seq"]) != 1 or c["seq"][0][0] not in ("ff", "latch", "statetable"):
                info.update(kind="unsupported", why="sequential group " + ",".join(g[0] for g in c["seq"]))
                continue
            g, args, attrs = c["seq"][0]
            if g == "statetable":
                if c["attrs"].get("clock_gating_integrated_cell") and len(outs) == 1:
                    clk = [p for p in ins if pins[p].get("clock_gate_clock_pin") == "true"
                           or pins[p].get("clock") == "true"]
                    if len(clk) != 1:
                        info.update(kind="unsupported", why="clock gate without one clock pin")
                        continue
                    info.update(kind="icg", clock_pins=clk, data_pins=[p for p in ins if p not in clk],
                                cls=json.dumps(["icg", c["attrs"].get("clock_gating_integrated_cell"),
                                                sorted(attrs.items()),
                                                [(p, pins[p].get("direction"), _norm(pins[p].get("state_function", "")),
                                                  p in clk) for p in sorted(ins + outs)]]))
                else:
                    info.update(kind="unsupported", why="statetable cell that is not a clock gate")
                continue
            iq = args[0] if args else "IQ"
            iqn = args[1] if len(args) > 1 else None
            ids = set()
            for k in ("clocked_on", "clocked_on_also") + (("enable",) if g == "latch" else ()):
                ids |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", attrs.get(k, "")))
            clk = sorted(p for p in ins if pins[p].get("clock") == "true" or p in ids)
            data = [p for p in ins if p not in clk]
            both = "clear" in attrs and "preset" in attrs
            compl = (not both) or (attrs.get("clear_preset_var1"), attrs.get("clear_preset_var2")) in (("L", "H"), ("H", "L"))
            pol, bad = {}, None
            for p in outs:
                f = _norm(pins[p].get("function", ""))
                if f == iq:
                    pol[p] = 0
                elif iqn and f == iqn:
                    pol[p] = 1 if compl else "sep"
                elif f in ("!" + iq, iq + "'"):
                    pol[p] = 1
                elif iqn and compl and f in ("!" + iqn, iqn + "'"):
                    pol[p] = 0
                else:
                    bad = f"output {p} function '{f}'"
            if bad or not clk:
                info.update(kind="unsupported", why=bad or "no clock/enable pin")
                continue
            info.update(kind="seq", group=g, clock_pins=clk, data_pins=data, out_pol=pol,
                        cls=json.dumps([g, sorted(attrs.items()),
                                        [(p, pins[p].get("direction"), _norm(pins[p].get("function", "")), p in clk)
                                         for p in sorted(ins + outs)]]))
        else:
            nof = [p for p in outs if "function" not in pins[p]]
            if nof:
                info.update(kind="unsupported", why="output without function: " + ",".join(nof))
                continue
            if len(ins) == 1 and len(outs) == 1:
                f = pins[outs[0]]["function"]
                try:
                    v = (lib_eval(f, {ins[0]: 0}), lib_eval(f, {ins[0]: 1}))
                except Exception:
                    v = None
                if v == (False, True):
                    info["kind"] = "buf"
                elif v == (True, False):
                    info["kind"] = "inv"
    return out


# --------------------------------------------------------------------------------------- netlist
def prepare_netlist(src, dst):
    """Decompress if needed and drop physical-only cells (tap, fill, decap, antenna diode)."""
    opener = gzip.open if src.endswith(".gz") else open
    with opener(src, "rt", errors="replace") as f:
        txt = f.read()
    out, i, dropped = [], 0, 0
    for m in PHYS.finditer(txt):
        if m.start() < i:
            continue
        end = txt.index(");", m.end()) + 2
        out.append(txt[i:m.start()])
        i = end
        dropped += 1
    out.append(txt[i:])
    with open(dst, "w") as f:
        f.write("".join(out))
    return dropped


class Side:
    """One netlist (gold or gate) as read by Yosys into JSON, plus its cut."""

    def __init__(self, name, mod, lib):
        self.name, self.mod, self.lib = name, mod, lib
        self.ports = mod["ports"]
        self.cells = mod["cells"]
        self.errors, self.warnings = [], []
        self.drivers = {}
        self.max_bit = 1
        for p in self.ports.values():
            for b in p["bits"]:
                if isinstance(b, int):
                    self.max_bit = max(self.max_bit, b)
        for c in self.cells.values():
            for bits in c["connections"].values():
                for b in bits:
                    if isinstance(b, int):
                        self.max_bit = max(self.max_bit, b)

    def new_bit(self):
        self.max_bit += 1
        return self.max_bit

    def build(self):
        kinds = {}
        for inst, c in self.cells.items():
            info = self.lib.get(c["type"])
            if info is None:
                self.errors.append(f"{inst}: cell type {c['type']} not in the Liberty file")
                continue
            kinds.setdefault(info["kind"], 0)
            kinds[info["kind"]] += 1
            if info["kind"] == "unsupported":
                self.errors.append(f"{inst}: cell type {c['type']} unsupported ({info['why']})")
        self.kind_counts = kinds
        dup = 0
        for pname, p in self.ports.items():
            if p["direction"] == "inout":
                self.errors.append(f"inout port {pname} unsupported")
            if p["direction"] != "input":
                continue
            for i, b in enumerate(p["bits"]):
                if isinstance(b, int):
                    if b in self.drivers:
                        dup += 1
                    self.drivers[b] = ("port", pname, i)
        for inst, c in self.cells.items():
            info = self.lib.get(c["type"])
            if not info or info["kind"] in ("phys", "unsupported"):
                continue
            for pin in info["outputs"]:
                for b in c["connections"].get(pin, []):
                    if isinstance(b, int):
                        if b in self.drivers:
                            dup += 1
                            if dup <= 5:
                                self.errors.append(f"net {b} has two drivers: {self.drivers[b]} and {inst}.{pin}")
                        self.drivers[b] = ("cell", inst, pin)
        if dup:
            self.errors.append(f"{dup} nets with more than one driver")
        self.seq = {i: c for i, c in self.cells.items() if self.lib.get(c["type"], {}).get("kind") == "seq"}
        self.icg = {i: c for i, c in self.cells.items() if self.lib.get(c["type"], {}).get("kind") == "icg"}

    def port_label(self, pname, i):
        return pname if len(self.ports[pname]["bits"]) == 1 else f"{pname}[{self.ports[pname].get('offset', 0) + i}]"

    def trace_clock(self, bit, memo):
        """Follow a clock net back through buffers/inverters (and clock gates) to its root.
        Returns (root, parity, gates) with root port:<name> | cell:<inst>:<pin> | state:<inst>:<pin>
        | const:<v> | undriven."""
        path, parity, gates = [], 0, []
        b = bit
        while True:
            if isinstance(b, int) and b in memo:
                r, par, g = memo[b]
                res = (r, par ^ parity, tuple(gates) + g)
                break
            path.append((b, parity, tuple(gates)))
            if not isinstance(b, int):
                res = (f"const:{b}", parity, tuple(gates))
                break
            d = self.drivers.get(b)
            if d is None:
                res = ("undriven", parity, tuple(gates))
                break
            if d[0] == "port":
                res = ("port:" + self.port_label(d[1], d[2]), parity, tuple(gates))
                break
            inst, pin = d[1], d[2]
            c = self.cells[inst]
            info = self.lib[c["type"]]
            if info["kind"] in ("buf", "inv"):
                parity ^= info["kind"] == "inv"
                b = (c["connections"].get(info["inputs"][0]) or ["x"])[0]
            elif info["kind"] == "icg":
                gates.append(inst)
                b = (c["connections"].get(info["clock_pins"][0]) or ["x"])[0]
            elif info["kind"] == "seq":
                res = (f"state:{inst}:{pin}", parity, tuple(gates))
                break
            else:
                res = (f"cell:{inst}:{pin}", parity, tuple(gates))
                break
            if len(path) > 100000:
                res = ("loop", parity, tuple(gates))
                break
        # memoize every net on the path relative to that net
        r, par, g = res
        for (pb, ppar, pg) in path:
            if isinstance(pb, int):
                memo[pb] = (r, par ^ ppar, g[len(pg):])
        return res

    def analyze(self):
        """Per sequential cell: function class, clock signatures, data pins."""
        memo = {}
        self.seqinfo = {}
        for inst, c in list(self.seq.items()) + list(self.icg.items()):
            info = self.lib[c["type"]]
            clocks = {}
            for pin in info["clock_pins"]:
                bits = c["connections"].get(pin) or ["x"]
                root, par, gates = self.trace_clock(bits[0], memo)
                clocks[pin] = (root, par, gates)
            self.seqinfo[inst] = {"type": c["type"], "kind": info["kind"], "cls": info["cls"], "clocks": clocks}

    def cut(self, clock_roots):
        """Cut every sequential cell. Fills self.inputs (cut state inputs), self.outputs (compared
        outputs: name -> net bit or constant), the cone of influence and the free inputs that model
        undriven nets or x/z constants inside it."""
        lib = self.lib
        self.inputs = set()     # cut state input names
        self.pi_bit = {}        # state net -> cut input driving it
        self.inv_bit = {}       # state net -> cut input driving it inverted (Q_N)
        self.outputs = {}       # compared output -> bit; original output bits keyed ("o", port, index)
        for inst in sorted(self.seq):
            c = self.seq[inst]
            info = lib[c["type"]]
            qname = f"q:{inst}"
            self.inputs.add(qname)
            for pin, pol in info["out_pol"].items():
                for b in c["connections"].get(pin, []):
                    if not isinstance(b, int):
                        continue
                    if pol == 0:
                        self.pi_bit[b] = qname
                    elif pol == 1:
                        self.inv_bit[b] = qname
                    else:  # separate state variable for an output that is not always !Q
                        self.inputs.add(f"q:{inst}:{pin}")
                        self.pi_bit[b] = f"q:{inst}:{pin}"
            for pin in info["data_pins"]:
                self.outputs[f"d:{inst}:{pin}"] = (c["connections"].get(pin) or ["x"])[0]
        for inst in sorted(self.icg):
            c = self.icg[inst]
            for pin in lib[c["type"]]["data_pins"]:
                self.outputs[f"d:{inst}:{pin}"] = (c["connections"].get(pin) or ["x"])[0]
        self.outputs.update(clock_roots)
        for pname, p in self.ports.items():
            if p["direction"] == "output":
                for i, b in enumerate(p["bits"]):
                    self.outputs[("o", pname, i)] = b
        # cone of influence of everything compared
        removed = set(self.seq) | set(self.icg)
        self.cone_cells, seen, undriven = set(), set(), {}
        self.free = {}          # free input name -> reason
        self.xpin = {}          # (inst, pin) with an x/z constant -> free input name
        self.xout = {}          # compared output that is an x/z constant -> free input name
        stack = []
        for key, b in self.outputs.items():
            if isinstance(b, int):
                stack.append(b)
            elif b not in ("0", "1"):
                nm = "x:" + (self.port_label(key[1], key[2]) if isinstance(key, tuple) else key)
                self.xout[key] = nm
                self.free[nm] = f"compared output is the constant '{b}'"
        while stack:
            b = stack.pop()
            if b in seen:
                continue
            seen.add(b)
            if b in self.pi_bit or b in self.inv_bit:
                continue
            d = self.drivers.get(b)
            if d is None or (d[0] == "cell" and d[1] in removed):
                undriven[b] = d
                continue
            if d[0] == "port":
                continue
            inst = d[1]
            if inst in self.cone_cells:
                continue
            self.cone_cells.add(inst)
            c = self.cells[inst]
            for pin in lib[c["type"]]["inputs"]:
                for x in c["connections"].get(pin) or ["x"]:
                    if isinstance(x, int):
                        stack.append(x)
                    elif x not in ("0", "1"):
                        nm = f"x:{inst}:{pin}"
                        self.xpin[(inst, pin)] = nm
                        self.free[nm] = f"cell input is the constant '{x}'" if x != "x" or c["connections"].get(pin) \
                            else "cell input unconnected"
        self.free_bit = {}      # undriven net -> free input name
        if undriven:
            names = {}
            for nn, n in self.mod.get("netnames", {}).items():
                if n.get("hide_name"):
                    continue
                for i, b in enumerate(n["bits"]):
                    if isinstance(b, int) and b in undriven:
                        lab = nn if len(n["bits"]) == 1 else f"{nn}[{i}]"
                        if b not in names or (len(lab), lab) < (len(names[b]), names[b]):
                            names[b] = lab
            for b, d in undriven.items():
                nm = "x:" + names.get(b, f"net{b}")
                self.free_bit[b] = nm
                self.free[nm] = "driven by a clock gate output" if d else "undriven net"
        for nm, why in sorted(self.free.items()):
            self.warnings.append(f"{nm}: {why}; modelled as a free input shared by name")

    def write_cut(self, path, modname, all_inputs, out_names):
        """Write the cut module as structural Verilog over the Liberty cells (cone of influence only)."""
        lib = self.lib
        used = set()

        def net(b):
            if isinstance(b, int):
                used.add(b)
                return f"n${b}"
            return "1'b1" if b == "1" else "1'b0"

        def pref(pname, i):
            p = self.ports[pname]
            return vname(pname) if len(p["bits"]) == 1 else f"{vname(pname)}[{p.get('offset', 0) + i}]"

        body, assigns = [], []
        for inst in sorted(self.cone_cells):
            c = self.cells[inst]
            info = lib[c["type"]]
            conns = []
            for pin in info["inputs"]:
                if (inst, pin) in self.xpin:
                    conns.append(f".{pin}({vname(self.xpin[(inst, pin)])})")
                else:
                    conns.append(f".{pin}({net(c['connections'][pin][0])})")
            for pin in info["outputs"]:
                bits = c["connections"].get(pin)
                if bits and isinstance(bits[0], int):
                    conns.append(f".{pin}({net(bits[0])})")
            body.append(f"  {c['type']} {vname(inst)} ({', '.join(conns)});")
        orig_in = sorted(p for p in self.ports if self.ports[p]["direction"] == "input")
        orig_out = sorted(p for p in self.ports if self.ports[p]["direction"] == "output")
        decl = []
        for pname in orig_in + orig_out:
            p = self.ports[pname]
            w, off = len(p["bits"]), p.get("offset", 0)
            rng = "" if w == 1 else f"[{off + w - 1}:{off}] "
            decl.append(f"  {p['direction']} {rng}{vname(pname)};")
        decl += [f"  input {vname(nm)};" for nm in all_inputs]
        decl += [f"  output {vname(nm)};" for nm in out_names]
        for pname in orig_in:
            for i, b in enumerate(self.ports[pname]["bits"]):
                if isinstance(b, int) and self.drivers.get(b) == ("port", pname, i):
                    assigns.append(f"  assign {net(b)} = {pref(pname, i)};")
        for b, nm in sorted(self.pi_bit.items()):
            assigns.append(f"  assign {net(b)} = {vname(nm)};")
        for b, nm in sorted(self.inv_bit.items()):
            assigns.append(f"  assign {net(b)} = ~{vname(nm)};")
        for b, nm in sorted(self.free_bit.items()):
            assigns.append(f"  assign {net(b)} = {vname(nm)};")
        for key, b in self.outputs.items():
            lhs = pref(key[1], key[2]) if isinstance(key, tuple) else vname(key)
            rhs = vname(self.xout[key]) if key in self.xout else net(b)
            assigns.append(f"  assign {lhs} = {rhs};")
        portlist = [vname(p) for p in orig_in + orig_out] + [vname(n) for n in all_inputs] + [vname(n) for n in out_names]
        with open(path, "w") as f:
            f.write(f"module {vname(modname)} (\n    " + ",\n    ".join(portlist) + ");\n")
            f.write("\n".join(decl) + "\n")
            for b in sorted(used):
                f.write(f"  wire n${b};\n")
            f.write("\n".join(assigns) + "\n")
            f.write("\n".join(body) + "\n")
            f.write("endmodule\n")


# ------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gold", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--top", required=True)
    ap.add_argument("--liberty", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=3600, help="wall-clock limit for the whole check, seconds")
    ap.add_argument("--negative-control", action="store_true",
                    help="insert an inverter on the D pin of one flop of the gate copy; the check must find a counterexample")
    ap.add_argument("--engine", choices=("abc", "yosys-sat"), default="abc")
    ap.add_argument("--yosys", default=os.environ.get("YOSYS") or shutil.which("yosys") or "yosys")
    ap.add_argument("--abc", default=os.environ.get("YOSYS_ABC"), help="yosys-abc binary (default: next to yosys)")
    ap.add_argument("--keep", action="store_true", help="keep intermediate netlists, JSON and AIG files")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)
    log = Log(os.path.join(out, "equiv_cut.log"))
    t0 = time.time()
    deadline = t0 + a.timeout
    abc = a.abc or os.path.join(os.path.dirname(os.path.realpath(a.yosys)), "yosys-abc")
    if not os.path.exists(abc):
        abc = shutil.which("yosys-abc") or abc
    res = {"status": "ERROR", "flops_cut": 0, "outputs_compared": 0, "seconds": 0.0, "assumptions": ASSUMPTIONS,
           "method": "state-cut transition check (adapted from AfterClock's state-cut transition check)",
           "gold": a.gold, "gate": a.gate, "top": a.top, "liberty": a.liberty, "engine": a.engine,
           "negative_control": bool(a.negative_control), "steps": {}, "warnings": []}
    intermediates = []

    def step(name, r):
        res["steps"][name] = r
        log(f"{name}: rc={r['rc']} {r['seconds']}s peak {r['peak_mb']} MB" + (" TIMEOUT" if r["timed_out"] else ""))
        if r["timed_out"]:
            raise Timeout(name)
        if r["rc"] != 0:
            msg = ""
            for lp in (os.path.join(out, name + ".log"), os.path.join(out, name + ".stdout")):
                if os.path.exists(lp):
                    errl = [l.strip() for l in open(lp, errors="replace") if l.startswith("ERROR")]
                    msg = msg or (errl[-1][:400] if errl else "")
            raise ToolError(f"{name} failed (rc {r['rc']}){': ' + msg if msg else ''}; see {name}.log")

    try:
        lib_path = os.path.abspath(a.liberty)
        log(f"liberty {lib_path}")
        lib = classify_liberty(parse_liberty(lib_path))
        log(f"liberty: {len(lib)} cells, {sum(1 for v in lib.values() if v['kind'] == 'seq')} flip-flop/latch types")

        sides = {}
        for side, src in (("gold", a.gold), ("gate", a.gate)):
            v = os.path.join(out, f"{side}-logic.v")
            js = os.path.join(out, f"{side}-parsed.json")
            intermediates += [v, js]
            dropped = prepare_netlist(src, v)
            res[f"{side}_physical_cells_dropped"] = dropped
            ys = os.path.join(out, f"parse_{side}.ys")
            with open(ys, "w") as f:
                f.write(f"read_liberty -lib {LIB_FLAGS} {lib_path}\n"
                        f"read_verilog {v}\n"
                        f"hierarchy -check -top {a.top}\n"
                        f"flatten\n"
                        f"write_json {js}\n")
            step(f"parse_{side}", run_tool([a.yosys, "-q", "-l", os.path.join(out, f"parse_{side}.log"), "-s", ys],
                                           os.path.join(out, f"parse_{side}.stdout"), deadline))
            with open(js) as f:
                d = json.load(f)
            if a.top not in d["modules"]:
                raise ToolError(f"top module {a.top} not in {side} netlist")
            s = Side(side, d["modules"][a.top], lib)
            del d
            s.build()
            sides[side] = s
            log(f"{side}: {len(s.cells)} cells ({', '.join(f'{k} {n}' for k, n in sorted(s.kind_counts.items()))}), "
                f"{len(s.seq)} flops/latches, {len(s.icg)} clock gates")
        gold, gate = sides["gold"], sides["gate"]
        errs = [f"gold: {e}" for e in gold.errors[:20]] + [f"gate: {e}" for e in gate.errors[:20]]
        if errs:
            res["errors"] = errs
            raise ToolError("unsupported or malformed netlist content")

        # ---- negative control: invert the D pin of one flop in the gate copy (before the cut)
        if a.negative_control:
            invs = sorted((n for n, v in lib.items() if v["kind"] == "inv"), key=lambda n: ("__inv_" not in n, n))
            pick = None
            for inst in sorted(set(gold.seq) & set(gate.seq)):
                c = gate.cells[inst]
                info = lib[c["type"]]
                dpin = "D" if "D" in info["data_pins"] else (info["data_pins"][0] if info["data_pins"] else None)
                b = (c["connections"].get(dpin) or [None])[0] if dpin else None
                drv = gate.drivers.get(b) if isinstance(b, int) else None
                if drv and drv[0] == "cell" and lib[gate.cells[drv[1]]["type"]]["kind"] in ("comb", "buf", "inv"):
                    pick = (inst, dpin, b)
                    break
            if pick is None or not invs:
                raise ToolError("negative control: no flop with a logic-driven data pin found")
            inst, dpin, b = pick
            nb = gate.new_bit()
            cname = "NEGATIVE_CONTROL_INV"
            while cname in gate.cells:
                cname += "_"
            ip, op = lib[invs[0]]["inputs"][0], lib[invs[0]]["outputs"][0]
            gate.cells[cname] = {"type": invs[0], "connections": {ip: [b], op: [nb]}, "port_directions": {}}
            gate.cells[inst]["connections"][dpin] = [nb]
            gate.drivers[nb] = ("cell", cname, op)
            res["negative_control_detail"] = {"flop": inst, "pin": dpin, "cell": invs[0],
                                              "how": f"{invs[0]} inserted on {inst}.{dpin} in the gate copy before the cut"}
            log(f"negative control: inverter {invs[0]} on {inst}.{dpin} (gate copy)")

        # ---- match sequential cells by instance name; class and clock checks
        for s in (gold, gate):
            s.analyze()
        g_names, h_names = set(gold.seqinfo), set(gate.seqinfo)
        only_g, only_h = sorted(g_names - h_names), sorted(h_names - g_names)
        common = sorted(g_names & h_names)
        cls_bad, clk_bad = [], []
        roots, nonport = {}, {}
        for inst in common:
            gi, hi = gold.seqinfo[inst], gate.seqinfo[inst]
            if gi["cls"] != hi["cls"]:
                cls_bad.append({"cell": inst, "gold": gi["type"], "gate": hi["type"]})
                continue
            if gi["clocks"] != hi["clocks"]:
                clk_bad.append({"cell": inst, "gold": {p: list(v) for p, v in gi["clocks"].items()},
                                "gate": {p: list(v) for p, v in hi["clocks"].items()}})
                continue
            for pin, (root, par, gates) in gi["clocks"].items():
                key = f"{root}{' inverted' if par else ''}{' via ' + ','.join(gates) if gates else ''}"
                roots[key] = roots.get(key, 0) + 1
                if not root.startswith("port:"):
                    nonport[key] = nonport.get(key, 0) + 1
        resized = sum(1 for i in common if gold.seqinfo[i]["type"] != gate.seqinfo[i]["type"])
        port_bad = []
        for pname in sorted(set(gold.ports) | set(gate.ports)):
            gp, hp = gold.ports.get(pname), gate.ports.get(pname)
            if not gp or not hp or gp["direction"] != hp["direction"] or len(gp["bits"]) != len(hp["bits"]):
                port_bad.append(pname)
        n_flops = sum(1 for i in common if gold.seqinfo[i]["kind"] == "seq")
        res["matching"] = {"gold_sequential": len(g_names), "gate_sequential": len(h_names), "matched": len(common),
                           "resized_matched": resized,
                           "only_in_gold": len(only_g), "only_in_gate": len(only_h),
                           "only_in_gold_list": only_g[:50], "only_in_gate_list": only_h[:50],
                           "class_mismatch": len(cls_bad), "class_mismatch_list": cls_bad[:50],
                           "clock_mismatch": len(clk_bad), "clock_mismatch_list": clk_bad[:50],
                           "port_mismatch": port_bad[:50]}
        res["clock"] = {"roots": roots, "nonport_roots": nonport,
                        "note": "every clock/enable pin of every matched sequential cell traced through buffers, "
                                "inverters and clock gates; root, polarity and gates must agree between gold and gate"}
        res["flops_cut"] = n_flops
        res["clock_gates"] = sum(1 for i in common if gold.seqinfo[i]["kind"] == "icg")
        log(f"matching: {len(common)} matched ({resized} resized), {len(only_g)} only in gold, {len(only_h)} only in gate, "
            f"{len(cls_bad)} class mismatches, {len(clk_bad)} clock mismatches, {len(port_bad)} port mismatches")
        log(f"clock roots: {roots}")
        if nonport:
            log(f"clock roots that are not primary inputs (compared as clk:* outputs): {nonport}")
        if only_g or only_h or cls_bad or clk_bad or port_bad:
            res["status"] = "FAIL_MATCH"
            raise Done()

        # ---- cut
        roots_cmp = {}
        for s in (gold, gate):
            r = {}
            for inst in common:
                for (root, _par, _gates) in s.seqinfo[inst]["clocks"].values():
                    if root.startswith("cell:"):
                        _, rinst, rpin = root.split(":", 2)
                        r["clk:" + root[5:]] = s.cells[rinst]["connections"][rpin][0]
            roots_cmp[s.name] = r
        for s in (gold, gate):
            s.cut(roots_cmp[s.name])
        res["warnings"] = [f"gold: {w}" for w in gold.warnings[:20]] + [f"gate: {w}" for w in gate.warnings[:20]]
        for w in res["warnings"]:
            log("warning: " + w)
        if set(gate.outputs) != set(gold.outputs):
            raise ToolError("internal: gold and gate cut outputs differ")
        cut_inputs = sorted(gold.inputs | gate.inputs | set(gold.free) | set(gate.free))
        only = sorted((set(gold.free) ^ set(gate.free)))
        if only:
            res["free_inputs_one_side_only"] = only[:50]
        out_names = sorted(k for k in gold.outputs if isinstance(k, str))
        clash = (set(cut_inputs) | set(out_names)) & (set(gold.ports) | set(gate.ports))
        if clash:
            raise ToolError(f"cut port names clash with design ports: {sorted(clash)[:5]}")
        n_po = sum(1 for k in gold.outputs if isinstance(k, tuple))
        res["outputs_compared"] = len(gold.outputs)
        res["outputs_detail"] = {"primary_output_bits": n_po,
                                 "sequential_input_pins": sum(1 for k in out_names if k.startswith("d:")),
                                 "clock_roots": sum(1 for k in out_names if k.startswith("clk:")),
                                 "cut_inputs": len(cut_inputs),
                                 "free_inputs": len(set(gold.free) | set(gate.free)),
                                 "gold_cone_cells": len(gold.cone_cells), "gate_cone_cells": len(gate.cone_cells)}
        log(f"cut: {n_flops} flops/latches -> {len(cut_inputs)} inputs added, {len(gold.outputs)} outputs compared "
            f"({n_po} primary output bits); cone {len(gold.cone_cells)} / {len(gate.cone_cells)} cells")
        for s in (gold, gate):
            p = os.path.join(out, f"{s.name}-cut.v")
            intermediates.append(p)
            s.write_cut(p, s.name, cut_inputs, out_names)
            s.mod = s.cells = s.drivers = None  # free the parsed netlist before the solver runs

        # ---- prove
        if a.engine == "abc":
            for side in ("gold", "gate"):
                # one Yosys process per side: flatten the Liberty models, check, map to AIG.
                # (write_aiger warns "Treating undriven bit <input> like $anyseq" for input-port bits that
                # feed logic; the bits are ordinary AIG inputs, see the .aig.map.)
                aig = os.path.join(out, f"{side}.aig")
                intermediates.append(aig)
                ys = os.path.join(out, f"build_{side}.ys")
                with open(ys, "w") as f:
                    f.write(f"read_liberty {LIB_FLAGS} {lib_path}\n"
                            f"read_verilog -noautowire {os.path.join(out, side + '-cut.v')}\n"
                            f"hierarchy -check -top {side}\n"
                            f"flatten\n"
                            f"hierarchy -top {side}\n"
                            f"opt_clean\n"
                            f"check -assert\n"
                            f"aigmap\n"
                            f"opt_clean\n"
                            f"stat\n"
                            f"write_aiger -symbols -map {os.path.join(out, side + '.aig.map')} {aig}\n")
                step(f"build_{side}", run_tool([a.yosys, "-q", "-l", os.path.join(out, f"build_{side}.log"), "-s", ys],
                                               os.path.join(out, f"build_{side}.stdout"), deadline))
            syms = [aiger_symbols(os.path.join(out, f"{side}.aig")) for side in ("gold", "gate")]
            if syms[0] != syms[1]:
                raise ToolError("gold and gate AIG interfaces differ (input/output symbol tables)")
            aig_in, outs_order = syms[0]
            n_in_bits = sum(len(p["bits"]) for p in gold.ports.values() if p["direction"] == "input") + len(cut_inputs)
            if len(outs_order) != len(gold.outputs) or len(aig_in) != n_in_bits or None in aig_in + outs_order:
                raise ToolError(f"AIG interface does not match the cut: {len(aig_in)} inputs / {len(outs_order)} outputs, "
                                f"expected {n_in_bits} / {len(gold.outputs)}")
            res["aig_interface"] = {"inputs": len(aig_in), "outputs": len(outs_order)}
            log(f"AIGs: {len(aig_in)} inputs, {len(outs_order)} outputs each, identical symbol tables")
            remaining = max(10, int(deadline - time.time()))
            # two networks, paired output by output (not "&cec -m": it checks only output 0 of a miter)
            cmd = f"&cec -T {remaining} {os.path.join(out, 'gold.aig')} {os.path.join(out, 'gate.aig')}"
            with open(os.path.join(out, "prove.abc"), "w") as f:
                f.write(cmd + "\n")
            r = run_tool([abc, "-c", cmd], os.path.join(out, "prove.log"), deadline + 30)
            res["steps"]["prove"] = r
            log(f"prove: rc={r['rc']} {r['seconds']}s peak {r['peak_mb']} MB" + (" TIMEOUT" if r["timed_out"] else ""))
            txt = open(os.path.join(out, "prove.log")).read()
            res["solver_lines"] = [l.strip()[:300] for l in txt.splitlines()
                                   if re.search(r"equivalent|undecided|disproved|time =", l, re.I)][-8:]
            verdicts = re.findall(r"Networks are (NOT EQUIVALENT|equivalent|UNDECIDED|undecided)", txt)
            verdict = verdicts[-1].upper() if verdicts else ""
            if r["timed_out"]:
                res["status"] = "TIMEOUT"
                res["timeout_reason"] = "wall-clock limit reached in step prove"
            elif verdict == "NOT EQUIVALENT":
                res["status"] = "COUNTEREXAMPLE"

                def oname(k):
                    return outs_order[k] if k < len(outs_order) else f"output#{k}"

                m = re.search(r"(?:zero-based number|Output) (\d+)", txt)
                if m:
                    res["counterexample_output"] = oname(int(m.group(1)))
                # ABC prints the whole output vectors of both networks under the counterexample input
                m = re.search(r"OUTPUT: \S+ = \d+'h([0-9a-fA-F]+) \(.*?\), \S+ = \d+'h([0-9a-fA-F]+) \(", txt)
                if m:
                    diff = int(m.group(1), 16) ^ int(m.group(2), 16)
                    bits = [k for k in range(diff.bit_length()) if diff >> k & 1]
                    res["counterexample_differing_outputs"] = len(bits)
                    res["counterexample_differing_list"] = [oname(k) for k in bits[:20]]
            elif verdict == "EQUIVALENT" and r["rc"] == 0:
                res["status"] = "PROVED"
            elif verdict == "UNDECIDED":
                res["status"] = "TIMEOUT"
                res["timeout_reason"] = "solver resource limit (undecided)"
            else:
                res["status"] = "ERROR"
                res["errors"] = [f"unrecognised solver output (rc {r['rc']}); see prove.log"]
        else:
            ys = os.path.join(out, "prove.ys")
            remaining = max(10, int(deadline - time.time()))
            with open(ys, "w") as f:
                f.write(f"read_liberty {LIB_FLAGS} {lib_path}\n"
                        f"read_verilog -noautowire {os.path.join(out, 'gold-cut.v')}\n"
                        f"read_verilog -noautowire {os.path.join(out, 'gate-cut.v')}\n"
                        f"hierarchy -check\n"
                        f"miter -equiv -flatten -make_assert gold gate miter\n"
                        f"hierarchy -top miter\n"
                        f"sat -verify -prove-asserts -set-def-inputs -enable_undef -timeout {remaining} miter\n")
            r = run_tool([a.yosys, "-q", "-l", os.path.join(out, "prove.log"), "-s", ys],
                         os.path.join(out, "prove.stdout"), deadline + 30)
            res["steps"]["prove"] = r
            log(f"prove: rc={r['rc']} {r['seconds']}s peak {r['peak_mb']} MB" + (" TIMEOUT" if r["timed_out"] else ""))
            txt = open(os.path.join(out, "prove.log")).read()
            res["solver_lines"] = [l.strip()[:300] for l in txt.splitlines() if "SAT " in l or "timeout" in l.lower()][-6:]
            if r["timed_out"] or re.search(r"(?i)timed out|timeout reached", txt):
                res["status"] = "TIMEOUT"
            elif "no model found: SUCCESS" in txt and r["rc"] == 0:
                res["status"] = "PROVED"
            elif "model found: FAIL" in txt:
                res["status"] = "COUNTEREXAMPLE"
            else:
                res["status"] = "ERROR"
                res["errors"] = ["unrecognised solver output; see prove.log"]
    except Done:
        pass
    except Timeout as e:
        res["status"] = "TIMEOUT"
        res["timeout_reason"] = f"wall-clock limit reached in step {e}"
    except ToolError as e:
        res["status"] = "ERROR"
        res.setdefault("errors", []).insert(0, str(e))
    except Exception as e:  # noqa: BLE001 - report, do not hide
        res["status"] = "ERROR"
        res.setdefault("errors", []).insert(0, f"{type(e).__name__}: {e}")
        res["traceback"] = traceback.format_exc()[-3000:]
    if a.negative_control:
        res["underlying_status"] = res["status"]
        res["status"] = "COUNTEREXAMPLE" if res["status"] == "COUNTEREXAMPLE" else "CONTROL_FAILED"
    res["peak_mb"] = round(max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                               resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) / 1024.0, 1)
    res["seconds"] = round(time.time() - t0, 2)
    if not a.keep:
        for p in intermediates:
            if os.path.exists(p):
                os.remove(p)
    with open(os.path.join(out, "result.json"), "w") as f:
        json.dump(res, f, indent=1)
    log(f"status {res['status']}  flops_cut {res['flops_cut']}  outputs_compared {res['outputs_compared']}  "
        f"{res['seconds']}s  peak {res['peak_mb']} MB")
    ok = res["status"] == ("COUNTEREXAMPLE" if a.negative_control else "PROVED")
    sys.exit(0 if ok else 1)


class Done(Exception):
    pass


class Timeout(Exception):
    pass


class ToolError(Exception):
    pass


if __name__ == "__main__":
    main()
