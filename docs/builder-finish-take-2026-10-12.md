# Builder finish versus finish_take

A source-matched paired experiment compared `str_builder_finish` (copy snapshot) with `str_builder_finish_take` (transfer buffer) on the builder workload. Compiler, runtime, stdlib, headers, Rust control, and timer hashes match. Rust uses the same ownership-returning builder implementation in both variants.

Measured `2026-10-12T09:10:58Z` to `2026-10-12T09:12:10Z` with 80 position-balanced pairs. The runner checked 28 edge cases, 320 prewarms, and 320 timed outputs against the independent oracle.

| Variant | Forge/Rust throughput (95% interval) | Median Forge time |
| --- | ---: | ---: |
| baseline | 1.0351 [0.9680, 1.1384] | 92.380 ms |
| take | 1.0666 [0.9989, 1.1319] | 89.417 ms |

`finish_take` was 1.0078x the baseline Forge throughput, 95% interval [0.9462, 1.0296]. The interval includes no change, so this experiment does not establish a standalone speedup. It measures the explicit builder API path; the separate compiler comparison measures the proven immutable-append loop lowering.

[Raw provenance and samples](builder-finish-take-2026-10-12.json).
