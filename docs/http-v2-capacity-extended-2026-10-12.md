# Prepared HTTP capacity and throughput — observer protocol V2

This reports the largest tested concurrency level with all requests successful in every measured repeat. Each client lane holds at most one connection at a time; concurrency therefore means simultaneous in-flight loopback clients for this connection-per-request workload. It is not a general internet-facing user limit.

| Body bytes | Workers | Concurrent clients | Forge clean repeats | Rust clean repeats | Forge successful req/s (median) | Rust successful req/s (median) | Forge response MB/s | Rust response MB/s | Error-free max observed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 32 | 4 | 1024 | 4/4 | 4/4 | 8043.6 | 7291.4 | 0.724 | 0.656 | at least 2048 |
| 32 | 4 | 2048 | 4/4 | 4/4 | 4423.2 | 6550.4 | 0.398 | 0.590 | at least 2048 |

Every response is byte-compared with an independently generated expected packet and checked through EOF. A failed trial retains every completed row and its error stage; failed and partial trials are excluded from the error-free throughput medians. No outlier trimming or retry is used. The V2 observer bounds connect at the configured timeout, separates connect/setup/write/read/EOF time, and writes each completed attempt immediately. Its logging and loopback client work are included in the observer interval.

Capacity is a tested bound: if the highest tested level passes, the result is “at least N”; it does not claim the absolute maximum. Throughput reports successful requests/s and successful response payload bytes/s. Latency medians and p95/p99 are retained per trial in the JSON and raw TSV files. These are prepared-response endpoints, not full HTTP framework, TLS, routing, database or keepalive results.

Protocol: `prepared-http-v2-capacity-sweep`. Raw JSON and TSV attempts: `/home/helloworld0822/coding/forge-benchmarks/docs/http-v2-capacity-extended-2026-10-12.raw`. Build provenance: `/tmp/forge-http-v2-capacity-build-20261012`.
Executed runner SHA-256: `80871568874b9b9580c95754cc37706fe1b779004b36fa741861608aa0a9e8aa`.

Compressed attempt archive: [`http-v2-capacity-extended-2026-10-12.raw.tar.gz`](http-v2-capacity-extended-2026-10-12.raw.tar.gz), SHA-256 `79007cf7963260029fab26e8b87d2a70db43f4438c8eda48013a93318d884af1`.
