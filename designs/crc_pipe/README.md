# Pipelined CRC-32 byte updater

An original, small RTL benchmark for physical-design experiments. It performs a
reflected CRC-32 update over one byte, using polynomial `0xEDB88320`. Four pipeline
stages consume two bits each. The declared RTL storage is **144 bits**: 128 CRC
state bits, 12 delayed data bits, and four valid bits. Synthesis may optimize the
register implementation; 144 is not a measured mapped-cell count.

This is a different logic family from the serial/parallel multiplier (`spm`):
shift/XOR logic with pipelined transaction alignment and a global enable, instead
of arithmetic multiplication. Two small designs still do not establish broad
generalization, and this block alone does not demonstrate an AI benefit.

## Interface and timing

- On a rising `clk` edge with `rst_n=1`, `enable=1`, and `valid_i=1`, the block
  accepts the independent input pair `crc_i` and `data_i`.
- The corresponding result is visible after the **fourth enabled rising edge,
  counting the accepting edge as the first**. It advances through four registers.
  With continuous enable, one new transaction can be accepted per clock.
- `enable=0` freezes the complete pipeline, including output data and `valid_o`.
  A held `valid_o` is not a second result during disabled cycles. Consumers must
  honor the shared enable when advancing their transaction state.
- `valid_i=0` inserts a bubble on an enabled edge. `crc_o` is meaningful only
  when `valid_o=1`; datapath registers may change for invalid transactions.
- Active-low asynchronous reset clears all registers and discards in-flight
  work. Reset deassertion must be synchronized by the surrounding system.

There is no packet accumulator or automatic initial/final XOR. For the usual
CRC-32/ISO-HDLC convention, start with `0xFFFFFFFF`, chain returned states, and
XOR the final state with `0xFFFFFFFF`. Consecutive bytes of one dependent stream
must wait for its preceding state; independent streams can fill the pipeline.

## Verification

The self-checking testbench uses an independent one-bit-at-a-time reference,
checks the standard `123456789` result `0xCBF43926`, covers all 256 byte values,
then exercises 1,200 deterministic mixed-valid/mixed-enable cycles and resets
with outstanding transactions. It checks output latency, freeze behavior,
valid/bubble propagation, asynchronous reset, and transaction accounting.
It exits nonzero on a mismatch. This is RTL simulation, not equivalence proof or
gate-level timing validation.

Verified on October 25, 2026 using the pinned ARM64 container below. The simulator
returned exit code zero with:

```text
PASS crc_pipe: cycles=1504 accepted=921 checked=917 discarded_by_reset=4 stalls=316 resets=3 known_crc=CBF43926
```

Four accepted transactions were deliberately flushed by reset. The remaining
917 were checked; dropped transactions are not counted as successful outputs.

From the repository root, with Icarus Verilog installed:

```sh
iverilog -g2012 -Wall -s crc_pipe_tb -o /tmp/crc_pipe_tb \
  designs/crc_pipe/src/crc_pipe.v designs/crc_pipe/verify/crc_pipe_tb.v
vvp /tmp/crc_pipe_tb
```

To use the pinned LibreLane image without installing another simulator:

```sh
docker run --rm --name businesschallenge-crc-sim --platform linux/arm64 \
  --cpus 1 --memory 512m -v "$(pwd):/workspace:ro" -w /workspace \
  ghcr.io/librelane/librelane@sha256:bf76533ff7928b0c68f6232a6def27f23dee2a98541d2afc279e26f28702b0c0 \
  sh -c 'iverilog -g2012 -Wall -s crc_pipe_tb -o /tmp/crc_pipe_tb designs/crc_pipe/src/crc_pipe.v designs/crc_pipe/verify/crc_pipe_tb.v && vvp /tmp/crc_pipe_tb'
```

## Physical-flow configuration and provenance

`config.yaml` uses a 10 ns target and 45% core utilization, with the flow's
generated base SDC. No hand-written false paths or multicycle exceptions are
added. The resolved SDC, corner set, PDK revision, and actual tool settings must
be inspected and archived with each run. The initial 10 ns target is an
experiment setting, **not demonstrated timing closure**.

RTL, testbench, and pin ordering were written for this project; they are not
copied from an existing CRC IP core. The CRC polynomial and check value are
standard mathematical parameters, not a novelty claim. The testbench reference
does not import or call the RTL's two-bit update function.

The PDN geometry and YAML configuration pattern follow the Apache-2.0-licensed
[LibreLane 3.0.16 SPM example](https://github.com/librelane/librelane/tree/3.0.16/librelane/examples/spm).
No physical baseline, routed result, or AI performance improvement is implied by
the existence of these source files.
