# HTTP V3.2 capacity and throughput observation

## Result

Forge and Rust each completed all 128,000 requests in all eight measured samples with four server workers, 32-byte response bodies, and eight loopback client source addresses. The configured concurrency ceiling and total request count were both 128,000, but the observer did not record peak active/connected sockets. Its 256-pending-connect window launches more work while completed requests are drained. Therefore these samples establish repeated completion of 128,000 total one-shot requests per sample, **not 128,000 actual simultaneous clients, accepted connections, or users**, and no absolute server maximum. Separate single-shot smoke trials completed 220,000 total requests with that configured ceiling for both programs, while other high-load trials at 128,000–200,000 lanes had connect timeouts. Those conflicting outcomes are retained as evidence that the host's TCP and observer limits make the boundary unstable.

| Metric | Forge | Rust |
| --- | ---: | ---: |
| Complete measured samples | 8/8 | 8/8 |
| Requests completed per sample | 128,000 | 128,000 |
| Errors | 0 | 0 |
| Median successful throughput | 2,692 req/s | 4,080 req/s |
| Per-sample throughput range | 1,859–5,163 req/s | 1,712–9,242 req/s |
| Median request latency | 36.4 ms | 35.1 ms |
| Highest observer RSS | 162 MiB | 162 MiB |

The paired Forge/Rust throughput ratio has median 0.686 and a bootstrap 95% interval of 0.358–1.746. The samples are too variable to establish a throughput winner. These values include client connect, request write, exact response verification, EOF verification, and immediate TSV logging. The single client reactor is pinned to one CPU, so this measures the full local observer/server setup rather than server-only capacity.

## Conditions and limits

The test ran on Linux 6.8 with an AMD BC-250 (12 logical CPUs). Four server workers were pinned to CPUs 0, 2, 4, and 6; one epoll client reactor was pinned to CPU 8. Each trial launched 128,000 one-shot TCP connections with a 32-byte body and exact 90-byte prepared response. The observer used up to 256 pending connects, eight loopback source addresses, a 120-second connect timeout, and a 120-second I/O timeout. Eight randomized-order Forge/Rust pairs were measured after warmups.

The host's ephemeral port range was 32768–60999 and its TCP TIME_WAIT bucket count was already at the configured 65,536 ceiling during these tests. Passive kernel counters are global to the shared network namespace and cannot attribute drops or overflows to this benchmark. The one-reactor observer, connection churn, logging, loopback networking, and shared kernel state all constrain the result. It is not a prediction of internet-facing user capacity, keepalive performance, or complete application throughput.

The V3.2 observer improves ramp-up with a bounded connect window and periodic deadline scans, and distributes client binds over multiple 127/8 source addresses. V3.2 timing is not poolable with earlier V1/V2 measurements.

## Reproduction and evidence

The machine-readable report is [`http-v32-capacity-128k-paired-120s-2026-10-12.json`](http-v32-capacity-128k-paired-120s-2026-10-12.json). It retains every measured sample, command, correctness check, environment snapshot, and failed-attempt detail. All warmup and measurement JSON/TSV files are in [`http-v32-capacity-128k-paired-120s-2026-10-12.raw.tar.gz`](http-v32-capacity-128k-paired-120s-2026-10-12.raw.tar.gz), SHA-256 `1ac66244b50ddc3f0759698da68a6f274e90b03b9afbca8541b976e28078ba24`.

Related capacity attempts at 56k, 128k, 180k, 200k, and 220k, including failed and single-shot trials, are preserved in the [attempt summary JSON files](http-v32-capacity-220k-paired-2026-10-12.json) and [`http-v32-capacity-attempts-2026-10-12.raw.tar.gz`](http-v32-capacity-attempts-2026-10-12.raw.tar.gz), SHA-256 `403a9f052a16b027efffa6599170c112ba1f0960e970dff9e2c21e6c28f66955`. Do not combine them with the V2 throughput baseline.


Correction 2026-10-13: the original "at least 128,000 simultaneous request lanes" lower-bound claim was unsupported by the observer telemetry and is withdrawn. The original JSON/TSV samples and throughput statistics are retained unchanged. A new observer protocol will measure actual peak in-flight request states and connected-client states; those gauges still must not be equated with accepted server sessions or user population.
