# Rust-relative CPU and HTTP measurements

> Follow-up note: this report preserves an earlier combined CPU-candidate and HTTP V2 run. The later source-matched CPU evidence, corrected builder ownership description and V3 shared-host failure diagnostics are summarized in [the current evidence report](rust110-performance-current-evidence-2026-10-12.md).

This report consolidates the strongest reproducible benchmark results from the current Forge build. CPU source candidates change two workload algorithms: a bounded positive-state LCG fold and bounded Miller–Rabin with trial-division fallback. They are benchmark fixtures, not compiler-wide wins. The HTTP results measure a prepared fixed response over loopback and include load-generator work.

## CPU and string workloads

The combined candidate was measured against the frozen Forge baseline and unchanged Rust fixtures in 48 randomized groups balanced over all six three-way execution orders. Each input was prewarmed immediately before timing. The five workloads used the dimensions in the current CPU report. All 1,000 direct reference cases, 720 prewarms and 720 measurements passed. Scan and builder were then rerun in 120 groups each to tighten their paired intervals.

| Workload | Rust / Forge candidate throughput (95% interval) | Baseline Forge / candidate throughput | Result |
| --- | ---: | ---: | --- |
| LCG | 1.1508 [1.1489, 1.1570] | 1.1506 [1.1469, 1.1528] | Above 1.10 |
| Prime search | 2.8718 [2.8599, 2.8821] | 2.8370 [2.8172, 2.8507] | Above 1.10 |
| Scan | 1.8918 [1.8735, 1.9318] | 0.8476 [0.8338, 0.8540] | Above Rust target; code layout regressed vs Forge baseline |
| Builder | 1.3151 [1.1897, 1.3703] | 0.9952 [0.9908, 1.0038] | Above 1.10; no Forge-baseline change |
| Immutable append | 17.8931 [10.8670, 18.2895] | 0.9684 [0.9470, 1.0529] | Above 1.10; broad interval |

These are workload-level results against the checked-in Rust controls, not a claim that Forge compiles equivalent algorithms faster. The matched Miller–Rabin experiment measured Forge/Rust at 1.0192 [1.0130, 1.0261]. The combined fixture also changes generated code layout: scan remains 1.89× Rust-relative, but is 15% slower than baseline Forge, so this combined binary is not adopted as the default fixture. Full samples are in [the 48-group report](cpu-combined-five-workloads-2026-10-12.json) and [the 120-group scan/builder recheck](cpu-combined-scan-builder120-2026-10-12.json). Candidate source and runner: [combined kernels](../benchmark/cpu/kernels_lcg_fold_prime_mr.fg), [comparison runner](../benchmark/cpu_combined_candidate_compare.py).

## Prepared HTTP concurrency and throughput

On this host, a 4-worker prepared-response server passed four measured repeats at each tested concurrency through **28,000 simultaneous loopback client lanes** for both Forge and Rust. Each lane sent one 32-byte-body request and closed its connection. The highest error-free tested level is therefore **at least 28,000 clients**; the server's absolute maximum was not found.

| Concurrent clients | Forge clean repeats | Rust clean repeats | Forge successful req/s | Rust successful req/s | Forge / Rust paired throughput ratio (95% interval) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8,192 | 4/4 | 4/4 | 8,655 | 7,966 | 1.084 [1.019, 1.289] |
| 16,384 | 4/4 | 4/4 | 8,311 | 8,355 | 0.966 [0.860, 1.221] |
| 24,576 | 4/4 | 4/4 | 9,246 | 9,242 | 1.000 [0.969, 1.058] |
| 28,000 | 4/4 | 4/4 | 9,046 | 8,817 | 1.030 [0.940, 1.124] |

Each trial used `requests == concurrency`, so these are finite one-request-per-lane bursts, not sustained throughput or a general user-capacity figure. The observer uses one client thread per lane on two pinned client CPUs and logs each completed request inside the timed interval. The local ephemeral-port range is 28,232 ports, close to the largest tested level; client port/thread limits prevent these measurements from proving a higher server-only maximum. Do not infer a throughput winner from the four-repeat intervals.

The complete per-request records and sample JSON are in [the extended capacity archive](http-capacity-extended-2026-10-12.raw.tar.gz), SHA-256 `567ec1bb64b4ce3c2984f2837826c80558913440ed083b4b098e19ddd70a23f7`. The runner used for these tests is preserved in the archive; a reproducible extended runner is [http_capacity_extended_compare.py](../benchmark/http_capacity_extended_compare.py). Existing build provenance is in `/tmp/forge-http-v2-capacity-build-20261012`.

## Additional candidate results

Two generic dynamic-remainder guards and GCC profile-guided optimization were tested and rejected. The remainder candidates regressed prime throughput by about 1.1–1.2%; PGO was inconclusive for LCG and regressed primes. Their reports remain linked from [the progress log](rust110-progress-2026-10-12.md). No compiler fast path or PGO change from those probes is included in the reported CPU candidate.
