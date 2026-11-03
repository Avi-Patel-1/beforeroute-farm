You are a physical-design engineer asked for a forecast. You have exactly one packet directory (given to you as
PACKET_DIR) and a Python sandbox. Read anything inside PACKET_DIR (start with `contract.json`, `MANIFEST.json` and
`reports/summary.txt`); do not open anything outside it, do not search the web, and do not run any EDA tool. You have
at most 40 tool calls. Files ending in .gz are gzip-compressed text; units are in `contract.json`.

The packet is the full raw record of one finished routed run (the "source") of a digital block on SkyWater sky130A with
LibreLane 3.0.16 (Yosys/ABC, OpenROAD, OpenRCX, OpenSTA), asked to run at clock period T0: per-net dumps after global
route and at signoff (`nets/`), the routed DEF, the mapped netlist, SPEF at three RC corners and the signoff SDC
(`layout/`), STA reports (`reports/`, `sta/`), the flow's final metrics and the contract. Names of the design, its
ports, nets and instances are pseudonyms (library cell and pin names are real). A tuner reports the source's claimed
clock C0 = T0 − worst setup slack. The same flow settings will now be rebuilt from scratch at R1 = ceil05(C0) (C0
rounded up to 0.05 ns): the whole flow reruns at the new clock target, from synthesis through routing and signoff.
After that the registered chain in `contract.json` continues. Nothing has been rebuilt yet; your forecast is locked
before it is.

Predict, without any new run:
1. `p_pass`: the probability that the rebuild at R1 passes the judge in `contract.json`, and a `call`: "pass", "fail"
   or "abstain" (abstaining is allowed; give p_pass anyway).
2. `slope` = (C1 − C0)/(R1 − T0), where C1 is the rebuild's own claimed clock (R1 − its worst setup slack).
3. `kept_clock_ns`: the clock the registered chain keeps (its smallest passing clock, the source's own target
   included if the source passed), or null if you predict that no run of the chain passes.

Finish with only this JSON object as your final message (no other text):
{"packet_id": "<from contract.json>", "arm": "rung2", "p_pass": <0..1>, "call": "pass|fail|abstain",
 "slope": <number>, "claim1_ns": <number, = C0 + slope*(R1 - T0)>, "kept_clock_ns": <number or null>,
 "rationale": "<at most 150 words, naming the evidence you used>"}
