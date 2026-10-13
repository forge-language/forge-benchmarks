# Frozen Forge optimization comparison

Independent-seed repeat of the compiler-only invariant-parameter remainder lowering, using the same frozen binaries and matched small-prime algorithms. Reciprocal preparation is guarded and cached only for immutable unshadowed integer parameters with loop-repeated remainder; otherwise the checked remainder path is retained. SDK archives/headers, fixture algorithms and clock source match across compiler variants. Pairing, per-input prewarming and independent output checks are preserved.

Measured `2026-10-12T23:55:33Z` to `2026-10-12T23:59:32Z` with 120 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.5062 [1.5039, 1.5081] | 1.0000 [1.0000, 1.0000] | supported for this case |
| lcg | invariant_mod | rust | 1.5024 [1.4996, 1.5061] | 0.9984 [0.9968, 0.9994] | supported for this case |
| primes | baseline | rust | 1.0248 [1.0206, 1.0290] | 1.0000 [1.0000, 1.0000] | below target |
| primes | invariant_mod | rust | 1.5616 [1.5408, 1.5752] | 1.5272 [1.4848, 1.5344] | supported for this case |
| scan | baseline | rust | 1.9402 [1.9345, 1.9494] | 1.0000 [1.0000, 1.0000] | supported for this case |
| scan | invariant_mod | rust | 2.2639 [2.2523, 2.2712] | 1.1634 [1.1606, 1.1727] | supported for this case |
| builder | baseline | rust | 1.0918 [1.0610, 1.1586] | 1.0000 [1.0000, 1.0000] | inconclusive |
| builder | invariant_mod | rust | 1.2148 [1.1358, 1.2764] | 1.0725 [1.0481, 1.1063] | supported for this case |
| immutable | baseline | rust | 18.9806 [18.5203, 19.1702] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | invariant_mod | rust | 13.1377 [11.3787, 17.1067] | 1.0009 [0.9733, 1.0227] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Builder snapshot/copy/ownership-transfer choices are defined by the frozen fixture sources; compare their contracts before interpreting this row. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [invariant-mod-compiler-full-120-2026-10-12.json](invariant-mod-compiler-full-120-2026-10-12.json).
