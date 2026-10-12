# HTTP listener timeout inheritance probe — not adopted

The candidate set `SO_RCVTIMEO` and `SO_SNDTIMEO` once on each Linux listener,
then skipped the two per-connection `setsockopt` calls only when listener setup
succeeded. It propagated that fact with each accepted request and retained the
existing per-client timeout setup as a fallback. A local Linux socket check
confirmed both timeout values were inherited by accepted sockets.

The V2 HTTP runner's larger setting (12,000 requests, 512 clients) failed on
the unmodified baseline during pair 7: 502 connection attempts timed out and
the runner stopped without producing a performance result. That run is kept in
the raw archive but excluded from all estimates. Two smaller runs then compared
baseline and candidate in reversed run order: each used 12 paired groups,
4 workers, 64 clients and 512 requests per sample. All four runs completed;
all measured requests and validation probes passed.

| Run | Baseline Forge req/s | Candidate Forge req/s | Rust control req/s |
| --- | ---: | ---: | ---: |
| 1 | 2,267 | 2,208 | 2,128 baseline / 2,140 candidate |
| 2 | 2,144 | 2,293 | 12,946 baseline / 2,241 candidate |

The second baseline Rust value is a large timing outlier. Across all 24
matched groups, candidate/baseline Forge throughput was 0.976 [0.549, 1.434];
the paired Forge/Rust relative change was 1.018 [0.650, 1.860]. Both intervals
are too wide to establish a gain, and the per-run medians move in opposite
directions. The candidate was reverted; the existing per-connection timeout
configuration remains in place.

All run metadata and paired rows are in
[the machine-readable summary](http-timeout-inheritance-2026-10-12.json).
[Raw requests, failed high-load attempt and four completed runs](http-timeout-inheritance-2026-10-12.raw.tar.gz).
