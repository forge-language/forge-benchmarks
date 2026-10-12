# GCC loop-unrolling screen — no performance win

Tested the semantics-preserving `-funroll-loops` option on the generated Forge
C for the two below-target integer workloads, LCG and trial-division primes.
The default and candidate used the same Forge fixture, compiler, runtime and
stdlib archives, Rust control, inputs and CPU. The only build difference was
the additional GCC flag. Each run used 20 prewarmed position-balanced pairs,
the frozen current dimensions, CPU 0 and the independent Python output
reference; every check passed. The same seed stream and execution order were
used for both runs. All per-attempt data, hashes and commands are retained in
the linked JSON files.

| Workload | Default Forge / Rust | `-funroll-loops` Forge / Rust | Default / candidate Forge speedup (95% interval) |
| --- | ---: | ---: | ---: |
| LCG | 1.0033 [0.9992, 1.0119] | 1.0045 [0.9966, 1.0124] | 1.0001 [0.9927, 1.0101] |
| Primes | 1.0073 [1.0030, 1.0133] | 1.0109 [1.0074, 1.0138] | 1.0013 [0.9990, 1.0033] |

The candidate does not improve Forge throughput on either workload and both
remain below 1.10x Rust. LCG disassembly contains duplicated remainder-update
instructions, confirming GCC unrolled the loop; the Forge text segment grew
from 20,406 to 23,198 bytes, while median throughput stayed unchanged. The
hot arithmetic, rather than loop branch count, is the likely limit on this
case; that is an inference from the unchanged timing and emitted loop. Keep
the normal `-O3` build flags. [Default run](gcc-loop-unroll-default-2026-10-12.json),
[unrolled run](gcc-loop-unroll-candidate-2026-10-12.json).
