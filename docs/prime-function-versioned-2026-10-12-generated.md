# Frozen Forge optimization comparison

Prime loop function-level range versioning prototype: validate the complete value interval once per primes call, use unsigned 32-bit trial division only when all loop values are in range, otherwise preserve the original checked 64-bit path.

Measured `2026-10-12T19:27:58Z` to `2026-10-12T19:29:07Z` with 120 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| primes | baseline | rust | 1.0103 [1.0096, 1.0116] | 1.0000 [1.0000, 1.0000] | below target |
| primes | function_versioned | rust | 1.0003 [0.9989, 1.0025] | 0.9905 [0.9881, 0.9914] | below target |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [prime-function-versioned-2026-10-12.json](prime-function-versioned-2026-10-12.json).
