# Capacity-reserved builder comparison

Measured `2026-10-12T08:22:42Z` to `2026-10-12T08:23:26Z` with 60 paired samples on CPU 0. The baseline compiler is Forge `8f999c4` with only the new standard-library function registered so it can compile the shared fixture. The candidate uses the current compiler. Both use the same capacity-reserved Forge workload, Rust `String::with_capacity` control, native archives and headers.

| Implementation | Median time | Throughput vs Rust |
| --- | ---: | ---: |
| Baseline Forge | 112.477 ms | 0.879x [0.820, 0.968] |
| Candidate Forge | 104.798 ms | 0.948x [0.921, 0.981] |
| Rust control | 98.919 ms | 1.000x |

Candidate/baseline paired speedup is 1.107x [0.982, 1.160]. The interval includes 1.0, so the result does not establish a statistically clear compiler improvement. Forge remains slower than Rust on this workload. All variants produced matching checksums for all 60 seeds.

This comparison evaluates the current compiler variants with the same reserved-capacity workload; it does not isolate the effect of capacity reservation itself. The compiler snapshots, exact source and artifact hashes, commands, seeds and per-sample timings are preserved in [the raw report](capacity-builder-2026-10-12.json). Results describe this host and run only.
