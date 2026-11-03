"""IO1: apply a pin plan to the floorplan right after OpenROAD's own I/O placement (step IOPins.ApplyPinPlan).

Runs inside `openroad -python` through LibreLane's odbpy reader (click_odb). Pins of the groups named in the plan are
moved to legal slots computed by iolib.place_groups from this very database (die area, track grids, the positions the
stock placer just gave every other pin); every other pin is left exactly where the stock placer put it. Writes a JSON
report (stock positions before the move, new positions) for the record.
"""
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import odb  # noqa: E402
from reader import click, click_odb  # noqa: E402  (LibreLane scripts/odbpy, on PYTHONPATH via OdbpyStep)

import iolib  # noqa: E402


def floor_from_block(block, tech, h_layer, v_layer, h_mult, v_mult):
    dbu = block.getDbUnitsPerMicron()
    da = block.getDieArea()
    die = [da.xMin(), da.yMin(), da.xMax(), da.yMax()]
    V, H = tech.findLayer(v_layer), tech.findLayer(h_layer)
    ox, cx, sx = block.findTrackGrid(V).getGridPatternX(0)
    oy, cy, sy = block.findTrackGrid(H).getGridPatternY(0)

    def formula(layer, mult):
        w = int(float(mult) * layer.getWidth())
        d = max(int(math.ceil(layer.getArea() * dbu * dbu / w)), w)
        return {"w": w, "d": d}

    floor = {"dbu": dbu, "die": die,
             "tracks": {"V": {"origin": ox, "count": cx, "step": sx}, "H": {"origin": oy, "count": cy, "step": sy}},
             "layers": {"V": v_layer, "H": h_layer},
             "shape": {"V": formula(V, v_mult), "H": formula(H, h_mult)},
             "pins": {}, "templates": {}}
    for bt in block.getBTerms():
        if bt.getSigType() in ("POWER", "GROUND"):
            continue
        bps = bt.getBPins()
        rec = {"dir": bt.getIoType(), "edge": None, "pos": None, "box": None, "layer": None,
               "status": None}
        if len(bps) > 0:
            boxes = bps[0].getBoxes()
            if len(bps) != 1 or len(boxes) != 1:
                raise SystemExit(f"[iopins] {bt.getName()}: expected one pin shape, got {len(bps)} pins")
            b = boxes[0]
            box = [b.xMin(), b.yMin(), b.xMax(), b.yMax()]
            e = iolib.edge_of_box(box, die)
            rec.update({"edge": e, "pos": iolib.pos_along(box, e) if e else None, "box": box,
                        "layer": b.getTechLayer().getName(), "status": str(bps[0].getPlacementStatus())})
            if e and e not in floor["templates"]:
                w = box[2] - box[0] if e in ("N", "S") else box[3] - box[1]
                d = box[3] - box[1] if e in ("N", "S") else box[2] - box[0]
                floor["templates"][e] = {"w": w, "d": d, "layer": rec["layer"]}
        floor["pins"][bt.getName()] = rec
    return floor


@click.command()
@click.option("--plan", "plan_path", required=True)
@click.option("--hor-layer", required=True)
@click.option("--ver-layer", required=True)
@click.option("--hor-width-mult", default=2.0, type=float)
@click.option("--ver-width-mult", default=2.0, type=float)
@click.option("--report", "report_path", required=True)
@click_odb
def apply_plan(reader, plan_path, hor_layer, ver_layer, hor_width_mult, ver_width_mult, report_path):
    plan = iolib.load_plan(plan_path)
    block, tech = reader.block, reader.tech
    floor = floor_from_block(block, tech, hor_layer, ver_layer, hor_width_mult, ver_width_mult)
    names = set(floor["pins"])
    moves = [m for m in plan["moves"] if m["option"] != "KEEP"]
    for m in moves:
        missing = [p for p in m["pins"] if p not in names]
        if missing:
            raise SystemExit(f"[iopins] plan group {m['group']}: pins not in design: {missing[:5]}")
    res = iolib.place_groups(floor, moves)
    if not res["ok"]:
        raise SystemExit(f"[iopins] plan infeasible: {res['error']}")
    layer_of = {"V": tech.findLayer(ver_layer), "H": tech.findLayer(hor_layer)}
    moved = {}
    for pin, slot in res["placed"].items():
        e, pos = slot["edge"], slot["pos"]
        tmpl = floor["templates"].get(e)
        box = iolib.pin_box(floor, e, pos, tmpl)
        bt = block.findBTerm(pin)
        for bp in list(bt.getBPins()):
            odb.dbBPin_destroy(bp)
        bp = odb.dbBPin_create(bt)
        bp.setPlacementStatus("PLACED")
        layer = layer_of["V" if e in ("N", "S") else "H"]
        odb.dbBox_create(bp, layer, *box)
        moved[pin] = {"edge": e, "pos": pos, "box": box, "layer": layer.getName()}
    # check: every moved pin sits where the plan put it, and no two pins on an edge are closer than the pitch
    after = floor_from_block(block, tech, hor_layer, ver_layer, hor_width_mult, ver_width_mult)
    for pin, mv in moved.items():
        a = after["pins"][pin]
        assert (a["edge"], a["pos"]) == (mv["edge"], mv["pos"]), (pin, a, mv)
    for e in iolib.EDGES:
        step = after["tracks"]["V" if e in ("N", "S") else "H"]["step"]
        ps = sorted(p["pos"] for p in after["pins"].values() if p["edge"] == e)
        close = [(a, b) for a, b in zip(ps, ps[1:]) if b - a < iolib.PITCH_TRACKS * step]
        if close:
            raise SystemExit(f"[iopins] edge {e}: pins closer than {iolib.PITCH_TRACKS} tracks: {close[:3]}")
    rep = {"plan": os.path.abspath(plan_path), "plan_sha256": hashlib.sha256(open(plan_path, "rb").read()).hexdigest(),
           "case": plan.get("case"), "arm": plan.get("arm"), "n_moved_groups": len(moves), "n_moved_pins": len(moved),
           "floor": {k: floor[k] for k in ("dbu", "die", "tracks", "layers", "shape", "templates")},
           "stock": floor["pins"], "moved": moved}
    json.dump(rep, open(report_path, "w"), indent=1)
    print(f"[iopins] moved {len(moved)} pins in {len(moves)} groups; report {report_path}")


if __name__ == "__main__":
    apply_plan()
