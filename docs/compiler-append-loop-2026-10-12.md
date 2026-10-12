# Frozen Forge optimization comparison

Conservative native-only lowering of pure, dead-temporary ASCII immutable append loops to the string builder, with legacy fallback.

Measured `2026-10-12T08:06:05Z` to `2026-10-12T08:06:24Z` with 18 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| immutable | baseline | rust | 0.2332 [0.2323, 0.2379] | 1.0000 [1.0000, 1.0000] | below target |
| immutable | candidate | rust | 13.3543 [11.7038, 13.9166] | 57.2439 [50.7729, 58.8508] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. A further 70 baseline/candidate differential cases cover zero work and signed seeds; those cases are recorded in the JSON because Python's negative modulo differs from Forge's signed remainder. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [compiler-append-loop-2026-10-12.json](compiler-append-loop-2026-10-12.json).
