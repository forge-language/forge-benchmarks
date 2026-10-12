# Forge performance against the Rust control: current evidence

Status: optimization work and benchmarking are in progress. For equal work, this report uses Rust elapsed time divided by Forge elapsed time; a ratio of 1.10 means Forge processed at least 110% as much work per second for that workload. Results are scoped to the named fixture, host, compiler versions and measurement protocol.

## Source-matched CPU results

| Workload | Dimensions | Forge median | Rust median | Rust elapsed / Forge elapsed (95% interval) | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| Checked byte scan | 131,072 × 512 | 37.830 ms | 85.964 ms | 2.2727 [2.2642, 2.2884] | 40 balanced pairs; supports ≥1.10 on this case |
| Reserved string builder | 32,768 × 1,024 | 69.367 ms | 94.195 ms | 1.3607 [1.3099, 1.3812] | 120 balanced pairs; supports ≥1.10 on this case |
| LCG | 250,000 × 64 | 60.729 ms | 61.032 ms | 1.0051 [0.9998, 1.0092] | 40 balanced pairs; near parity |
| Prime search | 2,000 × 128 | 74.796 ms | 75.736 ms | 1.0111 [1.0094, 1.0130] | 40 balanced pairs; below target |

The scan and reserved builder are the strongest source-matched cases currently above the target. The builder creates identical bytes, reserves the same requested capacity, returns the owned buffer, scans it and cleans up within the timed rounds. Forge uses `str_builder_finish_take`; Rust returns the `String` by move. Neither clones the completed buffer. A prior 40-pair all-workload builder interval crossed 1.10, so the focused 120-pair rerun is the decision-grade result for that row.

The experimental immutable-view row is excluded from the matched target summary: Forge uses cached-length immutable views with arena snapshots, while the Rust control copies its growing prefix on every append. It has the same output and checksum, but the storage strategy is not equivalent. A new compiler-only optimization is being developed to make the private Forge append loop linear while preserving the immutable public result; no gain is claimed until its semantic tests and paired measurements pass.

The focused comparison uses GCC 13.3.0 and rustc 1.98.1 on the AMD BC-250 host, with native CPU tuning, the preserved optimized Forge SDK archives, prewarmed balanced order, independent checksum references and bootstrap intervals. Full samples and source/build hashes are in [the 40-pair suite](cpu-current-all-2026-10-12.json) and [the 120-pair builder rerun](cpu-current-builder-120-2026-10-12.json).

Two follow-up probes did not improve the evidence: GCC `-fwrapv` kept LCG and primes near parity, and factor-4 LCG unrolling did not speed up Forge. Their reports remain [here](cpu-wrapv-2026-10-12.md) and [here](cpu-lcg-unroll4-2026-10-12.md).

## HTTP capacity and throughput

The prior V2 loopback test completed four one-request-per-lane bursts at 28,000 configured clients for both servers. At that setting Forge delivered 9,046 successful requests/s and Rust 8,817; the paired ratio was 1.030 [0.940, 1.124]. This shows a finite tested burst, not sustained capacity or an absolute server maximum, and the interval does not establish the 1.10 target. The ephemeral-port range and the two-CPU V2 load observer also constrain interpretation. See [the V2 report](rust110-final-cpu-http-measurements-2026-10-12.md).

The separately versioned V3 single-reactor observer passed nine response/EOF/error-path tests and a fresh smoke validation against both server binaries. Its 8-pair capacity screening attempts were invalidated by shared-host network pressure: one trial recorded 511 connect timeouts after conntrack reached 262,144/262,144; a lower-concurrency rerun recorded 64 timeouts as the same shared table filled. The runner correctly rejected both trials and made no performance summary. These outcomes do not establish a server limit. The observer also used 78–100% of its isolated client CPU on passing samples, so its loopback throughput can become client-limited. No further capacity measurements should be treated as decision-grade until host pressure is cleared or a separate client/server host is available.

The failed reports and per-request diagnostics are preserved in [the high-concurrency report](http-v3-screen-high-2026-10-12.json), [the lower-concurrency report](http-v3-screen-low-2026-10-12.json) and [the raw runs archive](http-v3-screen-runs-2026-10-12.raw.tar.gz). The initial runner labeled a partial request vector as a schema/row-count mismatch; the V3 runner now reports observer footer counts and the first failed request explicitly. No failed samples are included in a throughput claim.

## What the evidence supports

Forge exceeds Rust's measured throughput by at least 10% on the checked scan and ownership-returning builder workloads on this host. It does not yet meet that threshold on the matched LCG or prime-search controls, and the current HTTP result does not prove a 10% advantage or an absolute capacity. These results are workload-specific, not a language-wide performance guarantee. The next material evidence is the immutable-view compiler optimization, followed by generated-code review, semantic and ABI tests, a full CPU regression comparison, and a fresh 60-pair baseline/candidate measurement with identical runtime and standard-library artifacts.
