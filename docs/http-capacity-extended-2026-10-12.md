# Extended prepared HTTP concurrency and throughput test

The V2 observer was extended past its original 4,096-client ceiling and tested staged concurrency values up to 28,000. Each trial used four server workers, a 32-byte response body, one close-after-response request per client lane, four repeats per language, and a full correctness-checked prewarm immediately before every measured repeat. Both implementations passed every request in every measured repeat at all four extended concurrency levels.

| Concurrent lanes | Forge/Rust clean repeats | Forge median successful req/s | Rust median successful req/s | Forge median payload MB/s | Rust median payload MB/s | Forge/Rust paired req/s ratio (95% interval) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8,192 | 4/4, 4/4 | 8,655 | 7,966 | 0.779 | 0.717 | 1.084 [1.019, 1.289] |
| 16,384 | 4/4, 4/4 | 8,311 | 8,355 | 0.748 | 0.752 | 0.966 [0.860, 1.221] |
| 24,576 | 4/4, 4/4 | 9,246 | 9,242 | 0.832 | 0.832 | 1.000 [0.969, 1.058] |
| 28,000 | 4/4, 4/4 | 9,046 | 8,817 | 0.814 | 0.794 | 1.030 [0.940, 1.124] |

The highest error-free tested configuration started **28,000 client threads/lanes** behind a common start barrier, each completing one request. Actual simultaneous connected or accepted sockets were not measured: some threads can finish before others establish connections. Consequently this is a finite burst completion result, and neither a connected-population lower bound nor a maximum user count. The client uses two pinned physical CPUs and records every response during the timed interval. The local ephemeral-port range is 28,232 ports, close to the largest configured lane count. The 28,000-lane ratio interval includes both Forge and Rust outcomes; this run does not establish a throughput winner.

The builds and server behavior match the previously documented V2 capacity build. The exact temporary runner source used for these trials is archived with all sample JSON and per-request TSV logs. The committed [extended runner](../benchmark/http_capacity_extended_compare.py) preserves the same 32,768 validation ceiling and uses a workspace-relative import path.

- [Compressed raw reports and request samples](http-capacity-extended-2026-10-12.raw.tar.gz), SHA-256 `567ec1bb64b4ce3c2984f2837826c80558913440ed083b4b098e19ddd70a23f7`
- Build provenance: `/tmp/forge-http-v2-capacity-build-20261012`
- The earlier 4,096-lane result is [here](http-v2-capacity-4096-2026-10-12.md); it records a tested client configuration, with no measured simultaneous socket population.

Correction 2026-10-13: the earlier simultaneous-capacity lower-bound wording is withdrawn. The original JSON/TSV and throughput values remain unchanged.
