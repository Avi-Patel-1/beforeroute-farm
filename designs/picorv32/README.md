# Larger-design benchmark: PicoRV32

Unmodified upstream `picorv32` RTL at revision
`ef203c2b0a3fb793280f5114941416c425c5b461`, downloaded from
https://github.com/YosysHQ/picorv32. The original ISC license and source
headers are retained. `source.json` binds the copied files to their hashes.

The first local SKY130 run uses the default core parameters, a chosen 25 ns
clock period, 35% floorplan utilization, and 45% target placement density.
These are conservative pilot settings, not a measured frequency optimum.
Both implementation and final timing use the flow's generated base SDC.
The core has active-low `resetn`. This is a bare processor core, without
an on-chip SRAM, program ROM, or peripheral subsystem.

The unchanged upstream public-domain `testbench_ez.v` executed its six-instruction
increment loop in the installed Icarus simulator. The local check verified
45 consecutive writes, values 0 through 44, to address 1020 with all byte
enables active. This is a smoke test, not ISA compliance or mapped equivalence.
Raw evidence is in `state/simulation/picorv32-upstream-v1/`.

The larger-design experiment is declared before physical execution in
`experiments/picorv32_scale_v1.json`. Record actual cell and sequential-bit
counts, all required final corners, failures and runtime. Do not promote this
design into the original small CTS training pool automatically.
