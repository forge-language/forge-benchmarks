# Prepared HTTP capacity and throughput — observer protocol V2

This records the largest configured client-lane count whose requests all succeeded in every measured repeat. A common start barrier releases one thread per lane; actual simultaneous connected or accepted sockets were not measured. No simultaneous population lower bound or maximum user count is established.

| Body bytes | Workers | Configured client lanes | Forge clean repeats | Rust clean repeats | Forge successful req/s (median) | Rust successful req/s (median) | Forge response MB/s | Rust response MB/s | Largest clean lane configuration |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 32 | 4 | 16 | 8/8 | 8/8 | 2957.9 | 3729.6 | 0.266 | 0.336 | 512 configured lanes |
| 32 | 4 | 64 | 8/8 | 8/8 | 3134.0 | 4001.7 | 0.282 | 0.360 | 512 configured lanes |
| 32 | 4 | 128 | 8/8 | 8/8 | 4116.1 | 3909.3 | 0.370 | 0.352 | 512 configured lanes |
| 32 | 4 | 256 | 8/8 | 8/8 | 4239.6 | 4326.5 | 0.382 | 0.389 | 512 configured lanes |
| 32 | 4 | 512 | 8/8 | 8/8 | 3451.9 | 3720.2 | 0.311 | 0.335 | 512 configured lanes |
| 4096 | 4 | 16 | 8/8 | 8/8 | 3732.2 | 3749.4 | 15.511 | 15.582 | 512 configured lanes |
| 4096 | 4 | 64 | 8/8 | 8/8 | 4170.4 | 4109.0 | 17.332 | 17.077 | 512 configured lanes |
| 4096 | 4 | 128 | 8/8 | 8/8 | 4056.4 | 4254.2 | 16.859 | 17.680 | 512 configured lanes |
| 4096 | 4 | 256 | 8/8 | 8/8 | 4210.8 | 4092.3 | 17.500 | 17.008 | 512 configured lanes |
| 4096 | 4 | 512 | 8/8 | 8/8 | 4055.7 | 3949.8 | 16.855 | 16.415 | 512 configured lanes |

Every response is byte-compared with an independently generated expected packet and checked through EOF. A failed trial retains every completed row and its error stage; failed and partial trials are excluded from the error-free throughput medians. No outlier trimming or retry is used. The V2 observer bounds connect at the configured timeout, separates connect/setup/write/read/EOF time, and writes each completed attempt immediately. Its logging and loopback client work are included in the observer interval.

Successful finite request completion at a configured lane count does not establish a simultaneous connection count or maximum capacity. Throughput reports successful requests/s and successful response payload bytes/s. Latency medians and p95/p99 are retained per trial in the JSON and raw TSV files. These are prepared-response endpoints, not full HTTP framework, TLS, routing, database or keepalive results.

Protocol: `prepared-http-v2-capacity-sweep`. Raw JSON and TSV attempts: `/home/helloworld0822/coding/forge-benchmarks/docs/http-v2-capacity-2026-10-12.raw`. Build provenance: `/tmp/forge-http-v2-capacity-build-20261012`.
Executed runner SHA-256: `3ab1794535eeec7b39c0a5d1da67d87f2d8e6a9d8c7e90dc91d99d340b941e9e`.

Correction 2026-10-13: the earlier simultaneous-capacity interpretation is withdrawn. Original JSON/TSV samples and throughput values remain unchanged.
