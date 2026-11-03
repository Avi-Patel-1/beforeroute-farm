"""IO1, the I/O pin-placement test: shared pure-Python logic (no OpenROAD imports).

Used inside `openroad -python` (apply_pin_plan.py, capture.py), on the GitHub runner (io_run.py: the rebuild chain),
and locally (menu, the nearest-side script arm, the packet validator, scoring). Pre-registration:
docs/qa_week/IO_PREREG.md.

Coordinates are database units (dbu; 1000 per micron on sky130) unless a name ends in _um.
"""
from __future__ import annotations

import json
import math
import re

EDGES = ("N", "E", "S", "W")
SEGMENTS = (1, 2, 3)
OPTIONS = ("KEEP",) + tuple(f"{e}{k}" for e in EDGES for k in SEGMENTS)
PITCH_TRACKS = 2          # minimum centre-to-centre distance between pins on one edge, in routing tracks (ppl default)
CORNER_MARGIN_UM = 1.5    # no moved pin centre within 1.5 um of a die corner (the stock placer came to 1.7 um)
RESET_RX = re.compile(r"^(i_|in_)?(rst|reset)(_?n|_i|_ni)?$", re.I)
BIT_RX = re.compile(r"^(.*)\[(\d+)\]$")


# ----------------------------------------------------------------------------------------------- ports and groups
def base_and_index(name):
    m = BIT_RX.match(name)
    return (m.group(1), int(m.group(2))) if m else (name, None)


def group_ports(pins, clock_port):
    """pins: {name: {"dir": "INPUT"/"OUTPUT"/..., ...}} -> {group: {"dir", "pins" (bus order), "fixed", "role"}}.
    A group is every port sharing a base name (bus bits) or a scalar port. Bus order = ascending bit index.
    Fixed (never moved by any arm): the clock port and reset ports (RESET_RX on the base name)."""
    groups = {}
    for name, p in pins.items():
        base, idx = base_and_index(name)
        g = groups.setdefault(base, {"dirs": set(), "bits": []})
        g["dirs"].add(p["dir"])
        g["bits"].append((-1 if idx is None else idx, name))
    out = {}
    for base, g in groups.items():
        role = "clock" if base == clock_port else ("reset" if RESET_RX.match(base) else "data")
        dirs = sorted(g["dirs"])
        out[base] = {"dir": dirs[0] if len(dirs) == 1 else "MIXED",
                     "pins": [n for _, n in sorted(g["bits"])],
                     "fixed": role != "data", "role": role}
    return out


# ----------------------------------------------------------------------------------------------- slots
def edge_of_box(box, die, tol=1):
    """box, die: [x0, y0, x1, y1] (dbu). Which die edge a pin shape touches."""
    x0, y0, x1, y1 = box
    if x0 <= die[0] + tol:
        return "W"
    if x1 >= die[2] - tol:
        return "E"
    if y0 <= die[1] + tol:
        return "S"
    if y1 >= die[3] - tol:
        return "N"
    return None


def pos_along(box, edge):
    """Centre of a pin shape along its edge: x for N/S, y for E/W."""
    return (box[0] + box[2]) // 2 if edge in ("N", "S") else (box[1] + box[3]) // 2


def edge_span(floor, edge):
    die = floor["die"]
    return (die[0], die[2]) if edge in ("N", "S") else (die[1], die[3])


def lattice(floor, edge):
    """Candidate slot positions on an edge: the even-numbered routing tracks of the edge's pin layer (V layer tracks for
    N/S, H layer tracks for E/W; numbered from the track-grid origin, which is where the stock placer puts its pins,
    PITCH_TRACKS apart), keeping CORNER_MARGIN_UM clear of each corner."""
    t = floor["tracks"]["V" if edge in ("N", "S") else "H"]
    lo, hi = edge_span(floor, edge)
    m = int(round(CORNER_MARGIN_UM * floor["dbu"]))
    pos = [t["origin"] + i * t["step"] for i in range(0, t["count"], PITCH_TRACKS)]
    return [p for p in pos if lo + m <= p <= hi - m]


def free_slots(floor, edge, occupied):
    step = floor["tracks"]["V" if edge in ("N", "S") else "H"]["step"]
    need = PITCH_TRACKS * step
    return [s for s in lattice(floor, edge) if all(abs(s - q) >= need for q in occupied)]


def segment_range(floor, edge, k):
    lo, hi = edge_span(floor, edge)
    L = hi - lo
    return lo + (k - 1) * L / 3.0, lo + k * L / 3.0


def place_groups(floor, moves, lenient=False):
    """Deterministic legal placement of moved groups.
    floor: {"dbu", "die", "tracks": {"V": {origin,count,step}, "H": {...}}, "pins": {name: {"edge", "pos"}}}
    moves: [{"group", "pins": [bus order], "option": "W2"}...] in priority order; KEEP entries are ignored.
    Every pin not in a move keeps its stock position and blocks slots closer than PITCH_TRACKS tracks; the stock
    positions of moved pins are freed first, so groups can trade places. Each move, in order, takes the window of
    len(pins) consecutive free slots on its edge whose mean is nearest the segment centre (ties: lower coordinate);
    bus order ascends with the coordinate.
    strict (validation): any group that does not fit makes the plan infeasible.
    lenient (inside a build): a group that does not fit keeps its stock pins, and the placement is redone without it.
    Returns {"ok", "error", "placed": {pin: {"edge", "pos"}}, "dropped": [groups kept at stock because they did not fit]}"""
    moves = [mv for mv in moves if mv["option"] != "KEEP"]
    seen = set()
    for mv in moves:
        if mv["option"] not in OPTIONS:
            return {"ok": False, "error": f"unknown option {mv['option']!r} for {mv['group']}", "placed": {}, "dropped": []}
        if mv["group"] in seen:
            return {"ok": False, "error": f"group {mv['group']} listed twice", "placed": {}, "dropped": []}
        seen.add(mv["group"])
    dropped = []
    while True:
        res = _place(floor, [mv for mv in moves if mv["group"] not in dropped])
        if res["ok"] or not lenient:
            res["dropped"] = dropped
            return res
        dropped.append(res["failed"])


def _place(floor, moves):
    moving = {p for mv in moves for p in mv["pins"]}
    occupied = {e: [] for e in EDGES}
    for name, p in floor["pins"].items():
        if name in moving or p.get("edge") is None:
            continue
        occupied[p["edge"]].append(p["pos"])
    placed = {}
    for mv in moves:
        e, k = mv["option"][0], int(mv["option"][1])
        free = free_slots(floor, e, occupied[e])
        n = len(mv["pins"])
        if n > len(free):
            return {"ok": False, "error": f"{mv['group']}: {n} pins but edge {e} has {len(free)} free slots",
                    "placed": placed, "failed": mv["group"]}
        a, b = segment_range(floor, e, k)
        c = (a + b) / 2.0
        best = None
        for i in range(0, len(free) - n + 1):
            d = abs(sum(free[i:i + n]) / n - c)
            if best is None or d < best[0] - 1e-9:
                best = (d, i)
        win = free[best[1]:best[1] + n]
        for pin, s in zip(mv["pins"], win):
            placed[pin] = {"edge": e, "pos": s}
            occupied[e].append(s)
    return {"ok": True, "error": None, "placed": placed}


def pin_box(floor, edge, pos, template=None):
    """Pin shape flush with the die edge, centred on the slot. template: {"w": along-edge width, "d": depth} (dbu),
    copied from a stock pin on the same edge when one exists (otherwise floor["shape"][V|H])."""
    die = floor["die"]
    t = template or floor["shape"]["V" if edge in ("N", "S") else "H"]
    w, d = t["w"], t["d"]
    h = w // 2
    if edge == "S":
        return [pos - h, die[1], pos - h + w, die[1] + d]
    if edge == "N":
        return [pos - h, die[3] - d, pos - h + w, die[3]]
    if edge == "W":
        return [die[0], pos - h, die[0] + d, pos - h + w]
    return [die[2] - d, pos - h, die[2], pos - h + w]


# ----------------------------------------------------------------------------------------------- plans
def load_plan(path):
    plan = json.load(open(path))
    assert plan.get("version") == 1, "plan version"
    for mv in plan["moves"]:
        assert mv["option"] in OPTIONS, mv
        assert isinstance(mv["pins"], list) and mv["pins"], mv
    return plan


def parse_pin_file(text):
    """Reader / script output (pseudonymous names). Returns (moves [(group, option)], errors).
    Grammar: blank lines and lines starting with '#' are ignored; 'ABSTAIN' alone means keep every group;
    otherwise one '<group> <option>' per line, option in OPTIONS. Line order is placement priority."""
    moves, errors, abstain = [], [], False
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tok = line.split()
        if tok == ["ABSTAIN"]:
            abstain = True
            continue
        if len(tok) != 2:
            errors.append(f"line {ln}: expected '<group> <option>', got {line!r}")
            continue
        g, o = tok[0], tok[1].upper()
        if o not in OPTIONS:
            errors.append(f"line {ln}: option {tok[1]!r} not in {', '.join(OPTIONS)}")
            continue
        moves.append((g, o))
    if abstain and any(o != "KEEP" for _, o in moves):
        errors.append("ABSTAIN given together with moves")
    return moves, errors


# ----------------------------------------------------------------------------------------------- judge and chain
def ceil05(x):
    """Rebuild grid of the sky130 record (farm/tune_a32.py ceil05)."""
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def drv_count(m):
    """Slew + capacitance violation pins, as farm/tune.py drv_count."""
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def judge(m, drv_ref):
    """The record's pass test (farm/tune.py outcome/feasible + tune_a32.passed): the flow completed with setup and hold
    met at all nine corners, router DRC 0, and no more slew/cap violation pins than the design's stock bar."""
    if not m or m.get("timing__setup__ws") is None:
        return False
    hold = m.get("timing__hold__ws")
    return (m["timing__setup__ws"] >= 0 and hold is not None and hold >= 0
            and (m.get("route__drc_errors") or 0) == 0 and drv_count(m) <= drv_ref)


def claim(m, period):
    ws = (m or {}).get("timing__setup__ws")
    return None if ws is None else period - ws


def chain_next(T0, runs, max_rebuilds=4):
    """The registered rebuild chain (E5_PREREG's rule on the sky130 0.05 ns grid; the brief's shared facts).
    runs: [{"clock", "passed", "claim", "kind": "source"|"rebuild"}...] in order, runs[0] = the source run at T0.
    Returns the next clock to build, or None when the chain has ended.
      1. first rebuild at R1 = ceil05(C0);
      2. after a passing rebuild with claim C: rebuild at ceil05(C) while that is below the chain's smallest passing
         clock and above every failed clock of the chain that lies below that smallest passing clock;
      3. if the first rebuild fails: step back once, to max(ceil05(C1), R1 + 0.05), unless that is not below the
         smallest passing clock (T0 if the source passed); a failed rebuild after that ends the chain;
      4. at most max_rebuilds rebuilds; a clock already built in the chain is not built again."""
    src = runs[0]
    reb = [r for r in runs[1:]]
    if src.get("claim") is None:
        return None
    if len(reb) >= max_rebuilds:
        return None
    passing = [r["clock"] for r in runs if r["passed"]]
    smallest = min(passing) if passing else None
    built = {round(r["clock"], 2) for r in runs}
    if not reb:
        r1 = ceil05(src["claim"])
        if src["passed"] and r1 >= T0 - 1e-9:
            return None                      # the source already sits at its claimed clock
        return r1
    last = reb[-1]
    if not last["passed"]:
        if len(reb) == 1:                    # rule 3: the first rebuild failed
            c1 = last.get("claim")
            s = max(ceil05(c1) if c1 is not None else last["clock"] + 0.05, round(last["clock"] + 0.05, 2))
            s = round(s, 2)
            if smallest is not None and s >= smallest - 1e-9:
                return None
            return None if s in built else s
        return None                          # any later failure ends the chain
    nxt = ceil05(last["claim"])
    failed_below = [r["clock"] for r in runs if not r["passed"] and r["clock"] < smallest]
    if nxt >= smallest - 1e-9 or any(f >= nxt - 1e-9 for f in failed_below) or nxt in built:
        return None
    return nxt


def kept_clock(runs):
    """Smallest passing clock of the chain, source run included; None if no run passed."""
    ok = [r["clock"] for r in runs if r["passed"]]
    return min(ok) if ok else None
