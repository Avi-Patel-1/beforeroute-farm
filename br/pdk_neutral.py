"""PDK-neutral views of PDK-specific per-net features (sky130 hd, gf180mcu fd_sc 7t/9t).

- neutral_class(master): the driver cell's logic family and output polarity, independent of
  the cell library's naming (buf, clkbuf, inv, dly, nand, nor, and, or, xor, mux, aoi, oai,
  ao, oa, ff, latch, icg, tie, adder, tristate, port, other). Non-inverting complex gates
  (sky130 a21o / o21a ...) keep their own classes (ao / oa); gf180 has none, and the
  electrically closest gf180 cells (aoi / oai, single-stage inverting) map to the same
  classes as sky130's inverting a21oi / o21ai.
- drive_strength(master): the trailing _<n> size suffix (both libraries use it).
- layer_role(layer): routing-guide layer by role from the bottom of the stack: 0 = cell-pin
  layer (sky130 li1, gf180 Metal1), 1 = first routing layer (met1 / Metal2), 2 = second
  (met2 / Metal3), 3 = upper (met3+ / Metal4+). The dataset keeps the historical column
  names guide_frac_li1 / met1 / met2 / met3up for roles 0 / 1 / 2 / 3+.
- nominal_tt(corner_dict): the value at the nominal typical corner (nom_tt_*).
"""
from __future__ import annotations

import math
import re

_BASE_RE = re.compile(r"__([A-Za-z0-9]+?)(?:_\d+)?$")
_DRIVE_RE = re.compile(r"_(\d+)$")

NEUTRAL_CLASSES = [
    "port", "buf", "clkbuf", "inv", "dly", "nand", "nor", "and", "or", "xor", "mux",
    "aoi", "oai", "ao", "oa", "ff", "latch", "icg", "tie", "adder", "tristate", "other",
]


def cell_base(master: str | None) -> str | None:
    """Library-local cell function name: sky130_fd_sc_hd__a21oi_2 -> a21oi; gf180mcu_..__aoi21_2 -> aoi21."""
    if not master:
        return None
    m = _BASE_RE.search(master)
    return (m.group(1) if m else master).lower()


def neutral_class(master: str | None) -> str:
    if master is None or (isinstance(master, float) and math.isnan(master)) or master == "":
        return "port"
    b = cell_base(master)
    # tristates / keepers first (bufz/invz would otherwise read as buf/inv)
    if b.startswith(("einv", "ebuf", "bufz", "invz")):
        return "tristate"
    if b.startswith(("clkdly", "dlygate", "dlymetal", "dlya", "dlyb", "dlyc", "dlyd", "dly")):
        return "dly"
    if b.startswith("clkbuf"):
        return "clkbuf"
    if b.startswith(("clkinv", "bufinv", "inv")):
        return "inv"
    if b.startswith("buf"):
        return "buf"
    if b.startswith(("dlclkp", "sdlclkp", "icgt")):
        return "icg"
    if b.startswith(("dlx", "dlr", "lat")):
        return "latch"
    if b.startswith(("df", "edf", "sdf", "sedf")):
        return "ff"
    if b.startswith(("xor", "xnor")):
        return "xor"
    if b.startswith("nand"):
        return "nand"
    if b.startswith("nor"):
        return "nor"
    if b.startswith("and"):
        return "and"
    if b.startswith("or"):
        return "or"
    if b.startswith("mux"):
        return "mux"
    if b.startswith("aoi"):
        return "aoi"
    if b.startswith("oai"):
        return "oai"
    if re.match(r"^a\d", b):  # sky130 AND-OR family: a21oi (inverting) vs a21o (non-inverting)
        return "aoi" if b.endswith("oi") else "ao"
    if re.match(r"^o\d", b):  # sky130 OR-AND family: o21ai (inverting) vs o21a (non-inverting)
        return "oai" if b.endswith("ai") else "oa"
    if b.startswith(("conb", "tieh", "tiel")):
        return "tie"
    if b in ("fa", "fah", "fahcin", "fahcon", "ha", "maj3") or b.startswith(("addf", "addh")):
        return "adder"
    return "other"


def drive_strength(master: str | None) -> float:
    if not master or (isinstance(master, float) and math.isnan(master)):
        return float("nan")
    m = _DRIVE_RE.search(master)
    return float(m.group(1)) if m else float("nan")


_LAYER_ROLE = {
    # sky130
    "li1": 0, "met1": 1, "met2": 2, "met3": 3, "met4": 3, "met5": 3,
    # gf180mcu (5LM)
    "metal1": 0, "metal2": 1, "metal3": 2, "metal4": 3, "metal5": 3,
}


def layer_role(layer: str) -> int | None:
    return _LAYER_ROLE.get(layer.lower())


def guide_role_fracs(by_layer: dict | None, total: float | None) -> tuple[float, float, float, float]:
    """(role0, role1, role2, role3+) fractions of the net's global-route guide length."""
    by_layer = by_layer or {}
    if not total:
        return 0.0, 0.0, 0.0, 0.0
    acc = [0.0, 0.0, 0.0, 0.0]
    for k, v in by_layer.items():
        r = layer_role(k)
        if r is not None:
            acc[min(r, 3)] += v
    return tuple(x / total for x in acc)


def nominal_tt(by_corner: dict | None):
    for k, v in (by_corner or {}).items():
        if k.startswith("nom_tt"):
            return v
    return None
