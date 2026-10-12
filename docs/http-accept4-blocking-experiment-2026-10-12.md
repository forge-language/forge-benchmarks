# Linux HTTP accept4 candidate: experiment and decision

The candidate accepted client sockets as blocking with `accept4(..., SOCK_CLOEXEC)` while keeping the listener nonblocking for epoll. That removes the per-connection `F_GETFL`/`F_SETFL` conversion in `fr_sock_set_blocking`. The candidate patch is preserved at [http-accept4-blocking-candidate-2026-10-12.patch](http-accept4-blocking-candidate-2026-10-12.patch), but it was reverted because the measurements did not establish a performance win.

## Results

| Run | Result | Candidate / baseline Forge | Candidate / Rust |
| --- | --- | ---: | ---: |
| Initial 12-triplet attempt | Failed without a performance claim: the last Rust warmup hit global conntrack capacity and TCP connect timeouts | — | — |
| 12-triplet recheck | Completed, high variance | 1.0969 [0.9825, 1.6156] | 0.9703 [0.8002, 1.1893] |
| 24-triplet guarded run | Completed, no request failures | 0.8323 [0.6969, 1.3336] | 0.8205 [0.7258, 0.9343] |

The paired ratios are candidate throughput divided by the named reference. The final run used two workers, 64 closed-loop clients, a 32-byte body, 4096 measured requests, and a checked 512-request warmup for every arm. Baseline Forge, candidate Forge, and an unchanged Rust control ran in all six arm orders equally often. A 50,000 global conntrack high-water guard paused between triplets; the run waited 609 seconds in total. Each response was byte-checked through EOF. All 72 measured samples and 72 warmups passed.

The 24-triplet run still had very wide confidence intervals: its candidate/baseline interval contains both a regression and a large improvement. Candidate/Rust is below 1.0 for this configuration, so the candidate did not approach the 1.10 goal. Per-sample p99 latency reached about 208 ms across the arms, showing substantial host or loopback variability. The 12-triplet recheck also failed to establish a gain. No aggregate performance improvement is claimed, and the candidate is not retained in `forge-stdlib`.

## Correctness and security checks

The candidate build passed all 14 HTTP V2 correctness probes, including response-byte checks and request handling checks. The standard library CTest suite passed 10/10. A direct Linux socket probe confirmed that the listener remains nonblocking, an accepted fd is blocking without `SOCK_NONBLOCK`, and `SOCK_CLOEXEC` remains set. These checks did not establish full HTTP parser, TLS, routing, or production server behavior.

The first attempt started with 539 global conntrack entries and reached the configured 262,144 maximum. Its last Rust warmup recorded 3,340 attempts, 3,287 completed requests, and 53 connect timeouts; the run was marked `failed_no_claim`. The separate V2 primary report had already shown the same shared-host limit during a longer test. The initial failed run and both successful runs are retained separately; samples from the failed run were not pooled.

## Reproduction and retained evidence

The final run used `benchmark/http_accept4_compare.py` and immutable builds under `/tmp/forge-http-accept4-{baseline,candidate}-build-20261012`. Build metadata confirms identical compiler, runtime, Rust control and load client hashes; only the stdlib archive differed. The candidate's stdlib archive SHA-256 was `f46d8492c64ad26936cfc375df074e2346054e23cb398e118390be6ca6e4cf76`; the baseline archive was `745e923c4331a00608a4d4658eec373e9beac0bce596d0554713a7077c57584a`.

- [24-triplet report and raw samples](http-accept4-blocking-balanced-2026-10-12.json), [compressed raw archive](http-accept4-blocking-balanced-2026-10-12.raw.tar.gz), SHA-256 `dcc7ad52ac598696d1c1558e2ad3bd8c5585c57ecb005bb63240e7fbd3fe9c6b`.
- [12-triplet recheck](http-accept4-blocking-recheck-2026-10-12.json), [compressed raw archive](http-accept4-blocking-recheck-2026-10-12.raw.tar.gz), SHA-256 `9a1682e6e21acaeba1eeb00059ff3e2452f5d68344d722027b4f68bc2c639afd`.
- [Failed initial attempt](http-accept4-blocking-2026-10-12.json), [compressed raw archive](http-accept4-blocking-2026-10-12.raw.tar.gz), SHA-256 `2a857b573532886f6c9d11fe299eebc340883ac6bb506b510c6cc2ffccf592df`.

These are single-host loopback prepared-response measurements, not general HTTP framework, TLS, routing, keepalive, database, or cross-machine performance results.
