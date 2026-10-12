# Current Forge CPU comparison

Measured `2026-10-12T08:29:03Z` to `2026-10-12T08:29:59Z` with 30 paired samples per workload on CPU 0. One frozen current Forge build and one frozen Rust control used the same runtime inputs, dimensions, shared monotonic timer, and independent checksum reference. `builder` reserves capacity in both implementations. `immutable` exercises Forge's conservative native lowering for dead-temporary immutable append loops; Rust uses its normal owned-string append path.

| Workload | Dimensions (`n × rounds`) | Forge median | Rust median | Forge/Rust throughput (95% interval) | 1.10 |
| --- | ---: | ---: | ---: | ---: | --- |
| lcg | 250,000 × 64 | 60.573 ms | 61.175 ms | 1.012x [1.004, 1.014] | below |
| primes | 2,000 × 128 | 74.290 ms | 74.941 ms | 1.011x [1.006, 1.014] | below |
| scan | 131,072 × 512 | 98.854 ms | 93.552 ms | 0.948x [0.944, 0.954] | below |
| builder | 32,768 × 1,024 | 102.861 ms | 99.624 ms | 0.968x [0.906, 0.994] | below |
| immutable append | 4,096 × 512 | 6.886 ms | 94.140 ms | 13.557x [13.142, 13.711] | supported for this case |

All measured checksums matched the independent reference. The immutable result demonstrates a strong optimization for this narrowly recognized workload. The other four rows do not reach 1.10, so this suite does not establish the broader Rust 110% objective. Intervals describe this run and host only; the isolated immutable result does not generalize to arbitrary string workloads.

The frozen build metadata, source and artifact hashes, commands, seeds and all per-sample timings are in the [raw report](cpu-current-2026-10-12.json).
