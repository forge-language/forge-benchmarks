# HTTP accept4 blocking-client A/B benchmark

The candidate keeps each Linux listener nonblocking for epoll and accepts client sockets as blocking with `SOCK_CLOEXEC`, removing the per-client `F_GETFL`/`F_SETFL` conversion. The Rust control and the baseline Forge binary are unchanged. Ratios are candidate throughput divided by the paired comparison arm; 1.10 means 110% throughput.

| Comparison | Baseline median req/s | Candidate median req/s | Paired ratio | Bootstrap 95% interval | 1.10 target |
| --- | ---: | ---: | ---: | --- | --- |
| candidate / baseline Forge | 8052.6 | 7497.9 | 0.8323 | [0.6969, 1.3336] | inconclusive |
| candidate / Rust control | 9919.6 | 7497.9 | 0.8205 | [0.7258, 0.9343] | below target |

Protocol: `prepared-http-v2-bounded-connect-stage-observer`; 24 balanced triplets, 4096 measured and 512 warmup requests per sample, 64 client lanes, 2 workers, 32 byte body. Each measured sample followed a complete checked prewarm. Every response was compared byte-for-byte and checked through EOF; failed trials are retained and invalidate the comparison rather than being excluded or retried.

Candidate build: `/tmp/forge-http-accept4-candidate-build-20261012` (Forge binary SHA-256 `d70b987ea7b4ec559f9a1592cb091c92d01f160e779da2193365ea044e077cdb`).
Baseline build: `/tmp/forge-http-accept4-baseline-build-20261012` (Forge binary SHA-256 `8dcff9687308ee9bee1a411885acf98bb0e4ed62c196c2908c819c43f246f0f5`).
Rust control SHA-256 `b0bcadb11d5f95dcee78ea543283fc134c1644e04841d3f450437d26c4b031c4`. Raw attempts and executed runner: `/home/helloworld0822/coding/forge-benchmarks/docs/http-accept4-blocking-balanced-2026-10-12.raw`.

Global conntrack high-water guard: 50000; total wait between triplets: 609 seconds. Global counters are shared-host observations, not per-process attribution.

This is a single-host loopback prepared-response test. It does not establish general HTTP framework, TLS, routing, keepalive, or cross-machine performance.
