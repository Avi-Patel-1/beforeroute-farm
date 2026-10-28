# clip16_h0

RISC-V vector narrowing fixed-point clip (vnclip/vnclipu) per-element datapath, 16-bit source, 2-cycle latency (module `pipeline_dut`, 23-bit input, 9-bit output). Version: h0 — AI-written (LLM coding agent sample).
All five versions (h1, h0, packedclip, stickyround, native) are proven equivalent to the reference function (SAT proofs and exhaustive 2^23 simulation). Floorplan, pins and I/O constraints are those of the original clip study (100x100 um die, 2 ns I/O delay); the default clock period is 10 ns.
