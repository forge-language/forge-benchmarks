# Prepared HTTP benchmark — observer protocol V3 (single epoll reactor)

This separately versioned path drives the unchanged prepared HTTP servers with a single Linux epoll client reactor. V3 timing is not compatible with V1/V2 and must not be pooled with them.

| Body bytes | Workers | Concurrent sockets | Forge req/s | Rust req/s | Paired Rust/Forge ratio (95% interval) | 1.10 target |
| ---: | ---: | ---: | ---: | ---: | --- | --- |
| 32 | 4 | 64 | 8591.7 | 8556.6 | 1.0046 [0.7070, 1.0254] | below target |

Every request uses a new loopback connection. The observer has one pinned reactor thread and at most the configured number of active sockets. It checks every response byte against an independently generated packet, then separately requires EOF. Partial/failed trials preserve completed TSV rows and fail the comparison without retries or excluded failures. Its CPU, readiness polling, epoll work, request validation, TSV writes, and final process completion are in the reported elapsed interval.

The Forge and Rust server fixtures, server correctness probes, CPU setup, kernel snapshots, and paired-order statistics reuse the V2 runner helpers. The client source, runner, resulting binary hash, snapshot hashes and commands are retained in the build/report metadata. The client uses the same implementation for both server languages, so its work is part of the measured end-to-end loopback workload. Results do not establish general HTTP framework, TLS, keepalive, internet-facing capacity, or language-wide performance.

Raw run and retained attempts: [forge-http-v3-clean-4w64c-20261014.json](forge-http-v3-clean-4w64c-20261014.json); directory `/tmp/forge-http-v3-clean-4w64c-20261014.raw`.
