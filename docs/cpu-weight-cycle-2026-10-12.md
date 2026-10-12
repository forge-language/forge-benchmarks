# Frozen Forge optimization comparison

Current CPU suite comparing the original weighted formula with an equivalent modulo-free recurrence and source-matched Rust controls.

Measured `2026-10-12T08:58:16Z` to `2026-10-12T09:00:40Z` with 40 position-balanced pairs per workload.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.0123 [1.0080, 1.0163] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | baseline | rust_recurrence | 1.0067 [1.0027, 1.0084] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | recurrence | rust | 1.0144 [1.0084, 1.0163] | 0.9998 [0.9951, 1.0040] | below target |
| lcg | recurrence | rust_recurrence | 1.0073 [1.0022, 1.0093] | 0.9998 [0.9951, 1.0040] | below target |
| primes | baseline | rust | 1.0100 [1.0091, 1.0124] | 1.0000 [1.0000, 1.0000] | below target |
| primes | baseline | rust_recurrence | 1.0109 [1.0086, 1.0127] | 1.0000 [1.0000, 1.0000] | below target |
| primes | recurrence | rust | 1.0116 [1.0086, 1.0146] | 1.0000 [0.9971, 1.0042] | below target |
| primes | recurrence | rust_recurrence | 1.0106 [1.0076, 1.0137] | 1.0000 [0.9971, 1.0042] | below target |
| scan | baseline | rust | 0.9391 [0.9346, 0.9515] | 1.0000 [1.0000, 1.0000] | below target |
| scan | baseline | rust_recurrence | 0.8543 [0.8479, 0.8623] | 1.0000 [1.0000, 1.0000] | below target |
| scan | recurrence | rust | 2.1348 [2.1099, 2.1619] | 2.2567 [2.2467, 2.2916] | supported for this case |
| scan | recurrence | rust_recurrence | 1.9381 [1.9166, 1.9527] | 2.2567 [2.2467, 2.2916] | supported for this case |
| builder | baseline | rust | 0.8941 [0.8396, 0.9587] | 1.0000 [1.0000, 1.0000] | below target |
| builder | baseline | rust_recurrence | 0.8581 [0.8022, 0.8951] | 1.0000 [1.0000, 1.0000] | below target |
| builder | recurrence | rust | 1.1842 [1.0559, 1.2655] | 1.3179 [1.2338, 1.4147] | inconclusive |
| builder | recurrence | rust_recurrence | 1.1239 [0.9907, 1.2098] | 1.3179 [1.2338, 1.4147] | inconclusive |
| immutable | baseline | rust | 13.4999 [12.9376, 13.7413] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | baseline | rust_recurrence | 13.5033 [12.9322, 13.6061] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | recurrence | rust | 16.1753 [13.3163, 17.7972] | 1.3413 [1.1809, 1.3592] | supported for this case |
| immutable | recurrence | rust_recurrence | 16.2574 [13.4215, 18.0978] | 1.3413 [1.1809, 1.3592] | supported for this case |

All correctness, prewarm and measured checksums match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not universal performance. Cyclic schedules balance ordinal positions but not every adjacency.

The weighted-scan recurrence is an equivalent source-level algorithm rewrite in both Forge and Rust, not a compiler optimization. Forge retains arena snapshots until reset; allocator lifetime and compiler/runtime policies remain implementation differences. The full set of provenance and source hashes is recorded below.

These five CPU/string cases do not establish full language, HTTP, concurrency or other-machine performance. Builder’s confidence interval crosses 1.10 and does not establish the target.

Runner SHA-256: `52ca7d81ee7869ab58f0c677b8bc53503314b4b478f2e68f64aaa2a33b7ea1d0`.
Raw provenance and all samples: [cpu-weight-cycle-2026-10-12.json](cpu-weight-cycle-2026-10-12.json).
