# Frozen Forge optimization comparison

120-pair final recheck; compiler source commit `1994dc4`. compiler-generated guarded Mersenne modular multiply for unchanged LCG fixtures.

Measured `2026-10-12T18:45:03Z` to `2026-10-12T18:45:48Z` with 120 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.0061 [1.0043, 1.0075] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | mersenne_codegen | rust | 1.5041 [1.5001, 1.5068] | 1.4962 [1.4931, 1.4985] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [lcg-mersenne-codegen-120-2026-10-12.json](lcg-mersenne-codegen-120-2026-10-12.json).
