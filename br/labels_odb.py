"""Run with: openroad -exit -no_splash -python labels_odb.py <design.odb> <out.json>

Dumps, from a final (post-route) ODB, every signal net with its driver key and
its pin names, so signoff report pins can be mapped to nets and to the net's
driver (the join key against the pre-route feature dump).
"""
import json
import sys

import odb  # noqa: E402

odb_path, out_path = sys.argv[1], sys.argv[2]
db = odb.dbDatabase.create()
odb.read_db(db, odb_path)
block = db.getChip().getBlock()

nets = {}
pin_to_net = {}
for net in block.getNets():
    st = net.getSigType()
    if st in ("POWER", "GROUND"):
        continue
    name = net.getName()
    driver = None
    pins = []
    for it in net.getITerms():
        inst = it.getInst()
        key = f"{inst.getName()}/{it.getMTerm().getName()}"
        pins.append(key)
        pin_to_net[key] = name
        if it.getIoType() in ("OUTPUT", "INOUT") and driver is None:
            driver = key
    for bt in net.getBTerms():
        key = bt.getName()
        pins.append(key)
        pin_to_net[key] = name
        if bt.getIoType() == "INPUT" and driver is None:
            driver = f"PORT:{key}"
    nets[name] = {"sigtype": st, "driver": driver, "pins": pins, "fanout": max(0, len(pins) - 1)}

with open(out_path, "w") as fh:
    json.dump({"design": block.getName(), "nets": nets, "pin_to_net": pin_to_net}, fh)
print(f"[br] {len(nets)} nets, {len(pin_to_net)} pins -> {out_path}")
