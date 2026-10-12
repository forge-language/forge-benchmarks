# Frozen Forge optimization comparison

Lower-background-load rerun after proof correction: guarded view bounds-check elimination

Measured `2026-10-12T11:00:36Z` to `2026-10-12T11:02:14Z` with 42 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.0038 [1.0034, 1.0050] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | candidate | rust | 1.0040 [1.0034, 1.0049] | 1.0001 [0.9997, 1.0003] | below target |
| primes | baseline | rust | 1.0111 [1.0107, 1.0114] | 1.0000 [1.0000, 1.0000] | below target |
| primes | candidate | rust | 1.0112 [1.0108, 1.0114] | 1.0001 [0.9999, 1.0003] | below target |
| scan | baseline | rust | 1.9590 [1.9502, 1.9629] | 1.0000 [1.0000, 1.0000] | supported for this case |
| scan | candidate | rust | 2.2463 [2.2415, 2.2527] | 1.1484 [1.1454, 1.1526] | supported for this case |
| builder | baseline | rust | 1.2902 [1.2827, 1.2936] | 1.0000 [1.0000, 1.0000] | supported for this case |
| builder | candidate | rust | 1.2878 [1.2829, 1.2912] | 0.9978 [0.9940, 1.0029] | supported for this case |
| immutable | baseline | rust | 18.1440 [16.5693, 18.2826] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | candidate | rust | 19.2542 [17.6459, 19.6401] | 1.0785 [1.0677, 1.1464] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [forge-view-bounds-quiet-20261012.json](forge-view-bounds-quiet-20261012.json).
