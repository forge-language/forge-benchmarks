# LCG factor-4 loop-unroll comparison

Recorded at `2026-10-12T17:45:09Z`. Forge and Rust retain the same recurrence and wrapping semantics; only the inner loop is manually unrolled by four with a scalar tail.

| Metric | Median | Bootstrap 95% interval |
| --- | ---: | ---: |
| Baseline Rust / Forge throughput | 1.0037 | [1.0007, 1.0054] |
| Unroll-4 Rust / Forge throughput | 1.0109 | [1.0086, 1.0132] |
| Forge baseline / unroll-4 speedup | 0.9990 | [0.9971, 1.0019] |
| Rust baseline / unroll-4 speedup | 0.9932 | [0.9912, 0.9953] |
| Unroll-4 relative Rust/Forge change | 1.0083 | [1.0037, 1.0128] |

All 252 direct edge/reference checks, 480 prewarms and 480 timed measurements passed. Source and binary hashes, every sample and the exact runner are preserved in [cpu-lcg-unroll4-2026-10-12.json](cpu-lcg-unroll4-2026-10-12.json).

The result applies only to this LCG workload, host, toolchain and build snapshot; it does not establish language-wide performance. A relative interval crossing 1.0 or no Forge absolute speedup is not evidence of a gain.
