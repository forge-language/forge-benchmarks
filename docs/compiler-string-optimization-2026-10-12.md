# Frozen Forge optimization comparison

Current wrapping-int64 baseline versus checked dynamic unsigned32 division, length-delimited builder writes with checked inline append APIs, and their combination. Compiler-only and stdlib-only snapshots isolate effects; all archives/headers/binaries are frozen, and all four variants share one unchanged Rust control.

Measured `2026-10-12T00:07:41Z` to `2026-10-12T00:10:07Z` with 20 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | ---: | ---: | --- |
| lcg | baseline | 1.0096 [1.0084, 1.0107] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | strings | 1.0096 [1.0086, 1.0113] | 0.9999 [0.9989, 1.0005] | below target |
| lcg | division | 1.0099 [1.0084, 1.0115] | 1.0001 [0.9997, 1.0004] | below target |
| lcg | combined | 1.0099 [1.0079, 1.0109] | 0.9998 [0.9993, 1.0003] | below target |
| primes | baseline | 1.0108 [1.0104, 1.0113] | 1.0000 [1.0000, 1.0000] | below target |
| primes | strings | 1.0111 [1.0109, 1.0114] | 1.0004 [1.0000, 1.0005] | below target |
| primes | division | 1.0008 [1.0003, 1.0014] | 0.9902 [0.9898, 0.9905] | below target |
| primes | combined | 1.0007 [1.0003, 1.0010] | 0.9904 [0.9897, 0.9907] | below target |
| scan | baseline | 0.9488 [0.9444, 0.9509] | 1.0000 [1.0000, 1.0000] | below target |
| scan | strings | 0.9454 [0.9389, 0.9502] | 0.9987 [0.9955, 1.0035] | below target |
| scan | division | 0.9466 [0.9435, 0.9499] | 0.9987 [0.9937, 1.0042] | below target |
| scan | combined | 0.9462 [0.9345, 0.9494] | 0.9973 [0.9898, 1.0017] | below target |
| builder | baseline | 0.9072 [0.9049, 0.9087] | 1.0000 [1.0000, 1.0000] | below target |
| builder | strings | 1.0037 [0.9811, 1.0056] | 1.1060 [1.0884, 1.1088] | below target |
| builder | division | 0.8952 [0.8917, 0.8991] | 0.9872 [0.9817, 0.9895] | below target |
| builder | combined | 1.0009 [0.9997, 1.0039] | 1.1067 [1.1019, 1.1079] | below target |
| immutable | baseline | 0.2303 [0.2288, 0.2313] | 1.0000 [1.0000, 1.0000] | below target |
| immutable | strings | 0.2300 [0.2291, 0.2311] | 0.9991 [0.9969, 1.0032] | below target |
| immutable | division | 0.2307 [0.2290, 0.2314] | 1.0002 [0.9969, 1.0034] | below target |
| immutable | combined | 0.2301 [0.2292, 0.2313] | 0.9998 [0.9984, 1.0016] | below target |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [compiler-string-optimization-2026-10-12.json](compiler-string-optimization-2026-10-12.json).
