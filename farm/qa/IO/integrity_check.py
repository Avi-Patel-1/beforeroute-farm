#!/usr/bin/env python3
"""IO2 integrity check (for the record, not a registered test).

Readers shared a scratch folder; some reported another process overwriting their parsed files. For each packet
(the 5 whose Claude reader moved pins, and for the record the 5 that abstained), check that every pseudonymous
name its rationale.md and pins.txt comments cite (instances i<k>, nets n<k>, ports/groups G<nn>[bit], CLK, RST)
exists in ITS OWN packet (DEF components / nets / pins, both per-net dumps, OpenSTA path reports, port table,
menu), and that the specific properties the text states about those names (cell type, position, connectivity,
path role, slack; hand-coded below from each rationale, one entry per claim) hold in its own packet. As a control,
every property claim is also evaluated against the other nine packets: pseudonyms i<k>/n<k> are per-packet
counters, so bare existence elsewhere is expected; a claim that fails at home but holds in another packet would be
the red flag. Packets: /home/claude/ideas/overnight/pins/packets (rebuildable with packet.py build from the
captures); reader files: <PINS_DIR>/claude/<P>/.

usage: integrity_check.py PINS_DIR OUT.json
"""
import gzip
import json
import os
import re
import sys

PINS = sys.argv[1]
OUT = sys.argv[2]
ALL = sorted(os.listdir(os.path.join(PINS, "packets")))
MOVED = ["p0ba4e7", "p10bfb9", "p114b56", "p6dbefa", "pbae019"]
ABSTAINED = ["p00d863", "p3d0074", "p7a494d", "p89c9e8", "pdc9e8d"]


def load(P):
    d = os.path.join(PINS, "packets", P)
    U = {"comps": {}, "def_nets": set(), "def_pins": set(), "dump_nets": set(), "dump_insts": set(),
         "path_insts": set(), "path_nets": set(), "ports": set(), "groups": set(), "inst_xy_pins": {},
         "starts": {}, "ends": {}, "net_rows": {}}
    sec = None
    for line in gzip.open(os.path.join(d, "run", "layout.def.gz"), "rt"):
        s = line.strip()
        m = re.match(r"^(COMPONENTS|PINS|NETS|SPECIALNETS)\s+\d+", s)
        if m:
            sec = m.group(1)
            continue
        if s.startswith("END "):
            sec = None
            continue
        if sec and s.startswith("- "):
            tok = s.split()
            if sec == "COMPONENTS":
                pm = re.search(r"(PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", s)
                xy = (int(pm.group(2)) / 1000, int(pm.group(3)) / 1000) if pm else None
                U["comps"][tok[1]] = (tok[2], xy)
            elif sec == "PINS":
                U["def_pins"].add(tok[1])
            else:
                U["def_nets"].add(tok[1])
    for f in ("nets_postgrt.jsonl.gz", "nets_signoff.jsonl.gz"):
        for line in gzip.open(os.path.join(d, "run", f), "rt"):
            r = json.loads(line)
            U["dump_nets"].add(r["net"])
            if f.startswith("nets_signoff"):
                U["net_rows"][r["net"]] = r
            if r.get("driver_inst"):
                U["dump_insts"].add(r["driver_inst"])
            for k in r.get("load_keys") or []:
                U["dump_insts"].add(k.split("/")[0])
    paths = json.load(gzip.open(os.path.join(d, "run", "paths.json.gz"), "rt"))

    def walk_checks(obj):
        if isinstance(obj, dict):
            if obj.get("type") in ("check", "output_delay") and "startpoint" in obj:
                yield obj
            else:
                for v in obj.values():
                    yield from walk_checks(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk_checks(v)

    for c in walk_checks(paths):
        sp, ep, sl = c.get("startpoint", ""), c.get("endpoint", ""), c.get("slack")
        U["starts"].setdefault(sp.split("/")[0], []).append((sl, ep))
        U["ends"].setdefault(ep.split("/")[0], []).append((sl, sp))
        for pt in c.get("source_path") or []:
            if pt.get("instance"):
                U["path_insts"].add(pt["instance"])
                if pt.get("x") is not None:
                    U["inst_xy_pins"].setdefault(pt["instance"], set()).add((round(pt["x"] * 1e6, 1),
                                                                              round(pt["y"] * 1e6, 1)))
            if pt.get("net"):
                U["path_nets"].add(pt["net"])
    pj = json.load(open(os.path.join(d, "run", "ports.json")))
    U["ports"] = set(pj["ports"].keys())
    menu = json.load(open(os.path.join(d, "menu.json")))
    U["groups"] = {g["group"] for g in menu["groups"]} | {g["group"] for g in (menu.get("fixed_groups") or [])}
    U["menu"] = {g["group"]: g for g in menu["groups"]}
    U["paths"] = paths
    return U


def tokens(text):
    insts = set(re.findall(r"(?<![A-Za-z0-9_])i\d+(?![A-Za-z0-9_])", text))
    nets = set(re.findall(r"(?<![A-Za-z0-9_])n\d+(?![A-Za-z0-9_])", text))
    ports = set(re.findall(r"(?<![A-Za-z0-9_])G\d{2}(?:\[\d+\])?", text))
    # G03[12]/[9]/[8] style: expand bare [k] after a G-group
    for g, rest in re.findall(r"(G\d{2})((?:\[\d+\]/?)+(?:\[\d+\])?)", text):
        for b in re.findall(r"\[(\d+)\]", rest):
            ports.add(f"{g}[{b}]")
    fixed = {t for t in ("CLK", "RST") if re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text)}
    return insts, nets, ports, fixed


def exists(U, kind, name):
    where = []
    if kind == "inst":
        if name in U["comps"]:
            where.append("DEF")
        if name in U["dump_insts"]:
            where.append("dumps")
        if name in U["path_insts"] or name in U["starts"] or name in U["ends"]:
            where.append("paths")
    elif kind == "net":
        if name in U["def_nets"]:
            where.append("DEF")
        if name in U["dump_nets"]:
            where.append("dumps")
        if name in U["path_nets"]:
            where.append("paths")
    elif kind == "port":
        base = name.split("[")[0]
        if name in U["def_pins"]:
            where.append("DEF")
        if name in U["ports"]:
            where.append("ports.json")
        if base in U["groups"]:
            where.append("menu")
    return where


# ---------------------------------------------------------------------------------------------- property claims
def is_flop(m):
    return bool(re.search(r"__(dfxtp|dfrtp|dfstp|dfbbp|dfrbp|dfxbp|edfxtp|sdf|dfsbp|dlxtp|dfrtn)", m or ""))


def master(U, i):
    return (U["comps"].get(i) or (None, None))[0]


def pos(U, i):
    return (U["comps"].get(i) or (None, None))[1]


def near(U, i, x, y, tol=8.0):
    """cell origin (DEF) or any pin point of the instance (paths) within tol um of (x,y)"""
    pts = []
    if pos(U, i):
        pts.append(pos(U, i))
    pts += list(U["inst_xy_pins"].get(i, []))
    return any(abs(px - x) <= tol and abs(py - y) <= tol for px, py in pts) if pts else False


def in_box(U, i, x0, x1, y0, y1, tol=4.0):
    pts = []
    if pos(U, i):
        pts.append(pos(U, i))
    pts += list(U["inst_xy_pins"].get(i, []))
    return any(x0 - tol <= px <= x1 + tol and y0 - tol <= py <= y1 + tol for px, py in pts) if pts else False


def starts_to(U, i, pred):
    return [e for sl, e in U["starts"].get(i, []) if pred(e)]


def top_starts(U):
    out = {}
    for c in U["paths"]["top"]["checks"]:
        out.setdefault(c["startpoint"].split("/")[0], []).append(c["slack"] * 1e9)
    return out


def end_slacks(U, i):
    return [sl * 1e9 for sl, _ in U["ends"].get(i, []) if sl is not None]


def driver_of_port(U, port):
    for r in U["net_rows"].values():
        if port in [k for k in (r.get("load_keys") or [])] or r["net"] == port:
            if r.get("driver_inst"):
                return r["driver_inst"]
    return None


def drives_port(U, i, port):
    for r in U["net_rows"].values():
        if r.get("driver_inst") == i and any(k == port or k.split("/")[0] == port for k in (r.get("load_keys") or [])):
            return True
    return False


def reaches(U, start, depth=8):
    """output ports reached forward from instance `start` through at most `depth` non-flop cells (signoff dump)"""
    by_drv = {}
    for r in U["net_rows"].values():
        if r.get("driver_inst"):
            by_drv.setdefault(r["driver_inst"], []).append(r)
    seen, frontier, ports = {start}, [start], set()
    for _ in range(depth):
        nxt = []
        for inst in frontier:
            for r in by_drv.get(inst, []):
                for k in r.get("load_keys") or []:
                    if k.startswith("PORT:"):
                        ports.add(k[5:])
                        continue
                    i2 = k.split("/")[0]
                    if i2 not in seen:
                        seen.add(i2)
                        if not is_flop(master(U, i2)):
                            nxt.append(i2)
        frontier = nxt
    return ports


def all_bits(U, inst, groups, n):
    got = {p for p in reaches(U, inst, 12) if p.split("[")[0] in groups}
    return len(got) == n


def conn(U, g):
    return (U["menu"].get(g) or {}).get("connected_bits")


def tie(U, port):
    for r in U["net_rows"].values():
        if f"PORT:{port}" in (r.get("load_keys") or []) or any(k.startswith(f"PORT:{port}[") for k in r.get("load_keys") or []):
            return "conb" in (r.get("driver_master") or "")
    return False


def manhattan(U, a, b):
    pa, pb = pos(U, a), pos(U, b)
    return abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) if pa and pb else None


def port_edge(P, U, port):
    pj = json.load(open(os.path.join(PINS, "packets", P, "run", "ports.json")))
    return pj["ports"].get(port, {}).get("edge")


def port_pos(P, port):
    pj = json.load(open(os.path.join(PINS, "packets", P, "run", "ports.json")))
    return pj["ports"].get(port, {}).get("pos", -1e9) / 1000


def stock_edges(U, g):
    return set((U["menu"].get(g) or {}).get("stock_edges", {}))


CLAIMS = {
    "p0ba4e7": [
        ("i17576 starts most of the worst (top) paths",
         lambda P, U: len(top_starts(U).get("i17576", [])) >= 0.5 * sum(len(v) for v in top_starts(U).values())
         if top_starts(U) else False),
        ("i5920 is a buffer at about (118,50)",
         lambda P, U: bool(re.search(r"__(buf|clkbuf)", master(U, "i5920") or "")) and near(U, "i5920", 118, 50)),
        ("i7912, i8840, i18610 are registers about 220-243 um (Manhattan) from i5920, endpoint slack 0.63-0.64 ns",
         lambda P, U: all(is_flop(master(U, i)) and 205 <= (manhattan(U, i, "i5920") or 0) <= 260
                          and any(0.625 <= s <= 0.645 for s in end_slacks(U, i)) for i in ("i7912", "i8840", "i18610"))),
        ("G09 bits 25-28 on edge W, bit 31 on edge N (stock)",
         lambda P, U: all(port_edge(P, U, f"G09[{b}]") == "W" for b in (25, 26, 27, 28))
         and port_edge(P, U, "G09[31]") == "N"),
        ("G03 pins spread over edge W, y about 165-260 (stock)",
         lambda P, U: stock_edges(U, "G03") == {"W"}
         and abs(min(port_pos(P, f"G03[{b}]") for b in range(U["menu"]["G03"]["bits"])) - 165) < 3
         and abs(max(port_pos(P, f"G03[{b}]") for b in range(U["menu"]["G03"]["bits"])) - 260) < 3),
        ("top paths at T0 have slack 0.51-0.68 ns",
         lambda P, U: abs(min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 - 0.51) < 0.01),
    ],
    "p10bfb9": [
        ("i2224 is an and3 at about (104,128)",
         lambda P, U: "and3" in (master(U, "i2224") or "") and near(U, "i2224", 104, 128)),
        ("G01 on edge N, G09 on edge E, G04[0] on edge N (stock)",
         lambda P, U: port_edge(P, U, "G01") == "N" and port_edge(P, U, "G09") == "E" and port_edge(P, U, "G04[0]") == "N"),
        ("worst slack at T0 is reg-to-reg at 0.533 ns",
         lambda P, U: [(c["startpoint"][:1], c["endpoint"][:1]) for c in
                       [min(U["paths"]["top"]["checks"], key=lambda c: c["slack"])]
                       if abs(c["slack"] * 1e9 - 0.533) < 0.0015] == [("i", "i")]),
        ("G04 stock pins: G04[0] on N, the rest on W at y about 143-208",
         lambda P, U: port_edge(P, U, "G04[0]") == "N"
         and all(port_edge(P, U, f"G04[{b}]") == "W" for b in range(1, U["menu"]["G04"]["bits"]))
         and abs(min(port_pos(P, f"G04[{b}]") for b in range(1, U["menu"]["G04"]["bits"])) - 143) < 3
         and abs(max(port_pos(P, f"G04[{b}]") for b in range(1, U["menu"]["G04"]["bits"])) - 208) < 3),
    ],
    "p114b56": [
        ("i14705, i22835, i9097, i25353 are registers at x 167-196, y 177-184",
         lambda P, U: all(is_flop(master(U, i)) and in_box(U, i, 167, 196, 177, 184)
                          for i in ("i14705", "i22835", "i9097", "i25353"))),
        ("these four registers feed outputs G10/G18/G09/G20 (each reaches one through <= 8 non-flop cells; the "
         "worst-path reports name >= 3 of them as launch points of those outputs)",
         lambda P, U: all(any(re.match(r"^G(10|18|09|20)(\[|$)", o) for o in reaches(U, i))
                          for i in ("i14705", "i22835", "i9097", "i25353"))
         and sum(1 for i in ("i14705", "i22835", "i9097", "i25353")
                 if starts_to(U, i, lambda e: re.match(r"^G(10|18|09|20)(\[|$)", e))) >= 3),
        ("i8237 is an a22o_4 and i24017 an a21o_4",
         lambda P, U: (master(U, "i8237") or "").endswith("a22o_4") and (master(U, "i24017") or "").endswith("a21o_4")),
        ("G20 sits on E at 179.86 um, G18 on N at x about 216, G10 has 6 bits on E and 2 on N (stock)",
         lambda P, U: port_edge(P, U, "G20") == "E" and abs(port_pos(P, "G20") - 179.86) < 0.02
         and port_edge(P, U, "G18") == "N" and abs(port_pos(P, "G18") - 216) < 1.5
         and (U["menu"].get("G10") or {}).get("stock_edges") == {"E": 6, "N": 2}),
    ],
    "p6dbefa": [
        ("i1488, i3589, i8398, i8954 are registers at x about 99-116, y about 125-133",
         lambda P, U: all(is_flop(master(U, i)) and in_box(U, i, 99, 116, 125, 133)
                          for i in ("i1488", "i3589", "i8398", "i8954"))),
        ("i5663 is an a21o that drives G15 (through <= 3 cells) and an ~87 um net",
         lambda P, U: "a21o" in (master(U, "i5663") or "") and "G15" in reaches(U, "i5663", 3)
         and any(r.get("driver_inst") == "i5663" and abs(r["hpwl_um"] - 87) < 3 for r in U["net_rows"].values())),
        ("i4559 is an a22o at about (163,131)",
         lambda P, U: "a22o" in (master(U, "i4559") or "") and near(U, "i4559", 163, 131)),
        ("i7671 at about (167,158) and i6211 at about (157,136)",
         lambda P, U: near(U, "i7671", 167, 158) and near(U, "i6211", 157, 136)),
        ("i8109 is an and2",
         lambda P, U: "and2" in (master(U, "i8109") or "")),
        ("G15 on edge N at x about 150 (stock); G08 on E, G10 on W, G12 on E",
         lambda P, U: port_edge(P, U, "G15") == "N" and abs(port_pos(P, "G15") - 150.2) < 1.0
         and max((U["menu"].get("G08") or {}).get("stock_edges", {"-": 0}).items(), key=lambda kv: kv[1])[0] == "E"
         and stock_edges(U, "G10") == {"W"} and stock_edges(U, "G12") == {"E"}),
    ],
    # ---- ABSTAIN packets (their no-op plans are identical to stock; checked for the record of the blind findings)
    "p7a494d": [
        ("every top path at T0 starts at i1330 (a flop); worst slack 5.70 ns",
         lambda P, U: is_flop(master(U, "i1330"))
         and min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 > 5.69
         and min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 < 5.71
         and all(c["startpoint"].split("/")[0] == "i1330" for c in U["paths"]["top"]["checks"]
                 if c["slack"] * 1e9 < 5.70 + 0.05)),
        ("i1330 reaches all 64 bits of G01 and G05",
         lambda P, U: all_bits(U, "i1330", ("G01", "G05"), 64)),
        ("G02, G04, G06 unconnected; G03 driven by a tie cell; G07 slack about 7 ns",
         lambda P, U: all(conn(U, g) == 0 for g in ("G02", "G04", "G06")) and tie(U, "G03")
         and 6.5 <= (U["menu"].get("G07") or {}).get("worst_setup_slack_ns", 0) <= 7.5),
    ],
    "p89c9e8": [
        ("i976 is a dfrtp_2 and starts every critical (top, within 50 ps of worst) path",
         lambda P, U: (master(U, "i976") or "").endswith("dfrtp_2")
         and all(c["startpoint"].split("/")[0] == "i976" for c in U["paths"]["top"]["checks"]
                 if c["slack"] <= min(x["slack"] for x in U["paths"]["top"]["checks"]) + 0.05e-9)),
        ("i976 reaches all 64 bits of G01 and G04",
         lambda P, U: all_bits(U, "i976", ("G01", "G04"), 64)),
        ("G02, G05, G07 unconnected; G03 driven by a tie cell",
         lambda P, U: all(conn(U, g) == 0 for g in ("G02", "G05", "G07")) and tie(U, "G03")),
    ],
    "pdc9e8d": [
        ("i394 starts every critical (top, within 50 ps of worst) path; worst slack 5.78 ns",
         lambda P, U: abs(min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 - 5.78) < 0.01
         and all(c["startpoint"].split("/")[0] == "i394" for c in U["paths"]["top"]["checks"]
                 if c["slack"] <= min(x["slack"] for x in U["paths"]["top"]["checks"]) + 0.05e-9)),
        ("i394 reaches all 64 bits of G06 and G07",
         lambda P, U: all_bits(U, "i394", ("G06", "G07"), 64)),
        ("G02, G04, G05 unconnected; G01 driven by a tie cell; G03 slack about 8.2 ns",
         lambda P, U: all(conn(U, g) == 0 for g in ("G02", "G04", "G05")) and tie(U, "G01")
         and abs((U["menu"].get("G03") or {}).get("worst_setup_slack_ns", 0) - 8.2) < 0.15),
    ],
    "p00d863": [
        ("110 flip-flops in the block",
         lambda P, U: sum(1 for m, _ in U["comps"].values() if is_flop(m)) == 110),
        ("ten-odd top paths at 0.505-0.56 ns include G04 -> i1450, i372 -> registers, G05 -> i4246, G04 -> i2065/i1907",
         lambda P, U: abs(min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 - 0.505) < 0.006
         and {("G04", "i1450"), ("G05", "i4246"), ("G04", "i2065"), ("G04", "i1907")}
         <= {(c["startpoint"].split("/")[0], c["endpoint"].split("/")[0]) for c in U["paths"]["top"]["checks"]}
         and any(c["startpoint"].split("/")[0] == "i372" for c in U["paths"]["top"]["checks"])),
    ],
    "p3d0074": [
        ("worst slack 0.718 ns on output G02[5]; G02 has 3 bits on N and 5 on E (stock)",
         lambda P, U: any(c["endpoint"] == "G02[5]" and abs(c["slack"] * 1e9 - 0.718) < 0.0015
                          for c in U["paths"]["top"]["checks"])
         and abs(min(c["slack"] for c in U["paths"]["top"]["checks"]) * 1e9 - 0.718) < 0.0015
         and (U["menu"].get("G02") or {}).get("stock_edges") == {"N": 3, "E": 5}),
    ],
    "pbae019": [
        ("i469 and i11659 start paths to G11 output flops (worst family, about 0.48 ns)",
         lambda P, U: bool(U["starts"].get("i469")) and bool(U["starts"].get("i11659"))),
        ("i4564 starts paths of the next family (0.53-0.74 ns)",
         lambda P, U: any(0.50 <= (sl or 9) * 1e9 <= 0.76 for sl, _ in U["starts"].get("i4564", []))),
        ("G01 is a 32-bit input group",
         lambda P, U: U["menu"].get("G01", {}).get("bits") == 32 and U["menu"]["G01"].get("dir") == "INPUT"),
        ("G11 is an output group; G15, G13, G12 are inputs",
         lambda P, U: U["menu"].get("G11", {}).get("dir") == "OUTPUT"
         and all(U["menu"].get(g, {}).get("dir") == "INPUT" for g in ("G15", "G13", "G12"))),
    ],
}


def main():
    Us = {P: load(P) for P in ALL}
    report = {"packets": {}, "summary": {}}
    for P in MOVED + ABSTAINED:
        text = ""
        for f in ("rationale.md", "pins.txt"):
            fp = os.path.join(PINS, "claude", P, f)
            if os.path.exists(fp):
                text += open(fp).read() + "\n"
        insts, nets, ports, fixed = tokens(text)
        U = Us[P]
        rows, missing = [], []
        for kind, names in (("inst", insts), ("net", nets), ("port", ports | fixed)):
            for n in sorted(names, key=lambda s: (len(s), s)):
                w = exists(U, kind, n)
                also = [Q for Q in ALL if Q != P and exists(Us[Q], kind, n)]
                rows.append({"kind": kind, "name": n, "own_packet": w, "other_packets_with_name": len(also)})
                if not w:
                    missing.append(f"{kind} {n}")
        claims = []
        for desc, fn in CLAIMS.get(P, []):
            try:
                own = bool(fn(P, U))
            except Exception as e:  # noqa: BLE001
                own = f"error {e}"
            others = []
            for Q in ALL:
                if Q == P:
                    continue
                try:
                    if fn(Q, Us[Q]) is True:
                        others.append(Q)
                except Exception:  # noqa: BLE001
                    pass
            claims.append({"claim": desc, "holds_in_own_packet": own, "holds_in_other_packets": others})
        report["packets"][P] = {"moved": P in MOVED, "names_cited": len(rows), "missing_in_own_packet": missing, "names": rows,
                                "claims": claims}
        report["summary"][P] = {"names_cited": len(rows), "missing": len(missing),
                                "claims_hold_own": sum(1 for c in claims if c["holds_in_own_packet"] is True),
                                "claims_total": len(claims),
                                "claims_holding_elsewhere": sorted({Q for c in claims for Q in c["holds_in_other_packets"]})}
    json.dump(report, open(OUT, "w"), indent=1)
    for P in MOVED + ABSTAINED:
        r = report["packets"][P]
        print(f"== {P} ({'moved' if r['moved'] else 'ABSTAIN'}): {r['names_cited']} names cited, missing in own packet: {r['missing_in_own_packet'] or 'none'}")
        for c in r["claims"]:
            print(f"   [{'OK ' if c['holds_in_own_packet'] is True else 'NO '}] {c['claim']}"
                  f"   (also holds in: {c['holds_in_other_packets'] or 'none'})")


if __name__ == "__main__":
    main()
