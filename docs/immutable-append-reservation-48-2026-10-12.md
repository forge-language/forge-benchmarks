# Frozen Forge optimization comparison

Compiler-only immutable append builder reservation candidate against the frozen current compiler and shared Rust control. The optimization was rejected: across 48 paired samples, reservation reached 1.0396x the baseline median, but its 95% interval [0.9707, 1.0631] includes no improvement; the measured median was slower (7.648 ms vs 4.927 ms).

Measured `2026-10-12T20:26:15Z` to `2026-10-12T20:26:30Z` with 48 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| immutable | base | rust | 18.9799 [17.7069, 19.0973] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | reserve | rust | 12.1970 [10.5595, 18.1685] | 1.0396 [0.9707, 1.0631] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [immutable-append-reservation-48-2026-10-12.json](immutable-append-reservation-48-2026-10-12.json).
