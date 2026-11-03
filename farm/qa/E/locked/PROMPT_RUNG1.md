You are a physical-design engineer asked for a forecast. You have exactly one packet: the files listed in its
`MANIFEST.json` — `contract.json` and `reports/summary.txt`. Read them; do not run code, do not search the web, and do
not open any other file or directory.

The packet describes one finished routed run (the "source") of a digital block on SkyWater sky130A with LibreLane
3.0.16 (Yosys/ABC, OpenROAD, OpenRCX, OpenSTA), asked to run at clock period T0. A tuner reports its claimed clock
C0 = T0 − worst setup slack. The same flow settings will now be rebuilt from scratch at R1 = ceil05(C0) (C0 rounded up
to 0.05 ns): the whole flow reruns at the new clock target, from synthesis through routing and signoff. After that
the registered chain in `contract.json` continues. Nothing has been rebuilt yet; your forecast is locked before it is.

Predict, without any new run:
1. `p_pass`: the probability that the rebuild at R1 passes the judge in `contract.json`, and a `call`: "pass", "fail"
   or "abstain" (abstaining is allowed; give p_pass anyway).
2. `slope` = (C1 − C0)/(R1 − T0), where C1 is the rebuild's own claimed clock (R1 − its worst setup slack).
3. `kept_clock_ns`: the clock the registered chain keeps (its smallest passing clock, the source's own target
   included if the source passed), or null if you predict that no run of the chain passes.

Reply with only this JSON object (no other text):
{"packet_id": "<from contract.json>", "arm": "rung1", "p_pass": <0..1>, "call": "pass|fail|abstain",
 "slope": <number>, "claim1_ns": <number, = C0 + slope*(R1 - T0)>, "kept_clock_ns": <number or null>,
 "rationale": "<at most 150 words>"}
