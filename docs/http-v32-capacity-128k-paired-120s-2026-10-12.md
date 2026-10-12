# Prepared HTTP benchmark — observer protocol V3.2 (windowed multi-source epoll)

This separately versioned path drives the unchanged prepared HTTP servers with a single Linux epoll client reactor. It binds across the configured number of 127/8 source addresses to expand ephemeral-port tuples, caps pending connects at 256, and checks socket deadlines every 25 ms while polling events. V3.2 timing is not compatible with V1/V2 and must not be pooled with them.

| Body bytes | Workers | Concurrent sockets | Forge req/s | Rust req/s | Paired Rust/Forge ratio (95% interval) | 1.10 target |
| ---: | ---: | ---: | ---: | ---: | --- | --- |
| 32 | 4 | 128000 | 2692.5 | 4079.9 | 0.6864 [0.3580, 1.7463] | inconclusive |

Every request uses a new loopback connection across 8 source addresses. The observer has one pinned reactor thread and at most the configured number of active sockets, with no more than 256 pending connects. It checks every response byte against an independently generated packet, then separately requires EOF. Partial/failed trials preserve completed TSV rows and fail the comparison without retries or excluded failures. Its CPU, readiness polling, epoll work, deadline checks, request validation, TSV writes, and final process completion are in the reported elapsed interval.

The Forge and Rust server fixtures, server correctness probes, CPU setup, kernel snapshots, and paired-order statistics reuse the V2 runner helpers. The client source, runner, resulting binary hash, snapshot hashes and commands are retained in the build/report metadata. The client uses the same implementation for both server languages, so its work is part of the measured end-to-end loopback workload. Results do not establish general HTTP framework, TLS, keepalive, internet-facing capacity, or language-wide performance.

Raw run and retained attempts: [http-v32-capacity-128k-paired-120s-2026-10-12.json](http-v32-capacity-128k-paired-120s-2026-10-12.json); directory `/home/helloworld0822/coding/forge-benchmarks/docs/http-v32-capacity-128k-paired-120s-2026-10-12.raw`.
