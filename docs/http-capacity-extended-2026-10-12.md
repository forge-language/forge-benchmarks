# Extended prepared HTTP concurrency and throughput test

The V2 observer was extended past its original 4,096-client ceiling and tested staged concurrency values up to 28,000. Each trial used four server workers, a 32-byte response body, one close-after-response request per client lane, four repeats per language, and a full correctness-checked prewarm immediately before every measured repeat. Both implementations passed every request in every measured repeat at all four extended concurrency levels.

| Concurrent lanes | Forge/Rust clean repeats | Forge median successful req/s | Rust median successful req/s | Forge median payload MB/s | Rust median payload MB/s | Forge/Rust paired req/s ratio (95% interval) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8,192 | 4/4, 4/4 | 8,655 | 7,966 | 0.779 | 0.717 | 1.084 [1.019, 1.289] |
| 16,384 | 4/4, 4/4 | 8,311 | 8,355 | 0.748 | 0.752 | 0.966 [0.860, 1.221] |
| 24,576 | 4/4, 4/4 | 9,246 | 9,242 | 0.832 | 0.832 | 1.000 [0.969, 1.058] |
| 28,000 | 4/4, 4/4 | 9,046 | 8,817 | 0.814 | 0.794 | 1.030 [0.940, 1.124] |

The highest error-free tested value is **at least 28,000 simultaneous loopback lanes**. The server's absolute maximum is undetermined. The client uses one OS thread per lane on two pinned physical CPUs and records every response during the timed interval. These rates describe the complete finite burst benchmark, not isolated server throughput or a general user limit. The local ephemeral-port range is 28,232 ports, close to the highest tested concurrency, so the client-side port range constrains further server-only capacity conclusions. The 28,000-client ratio interval includes both Forge and Rust outcomes; this run does not establish a throughput winner.

The builds and server behavior match the previously documented V2 capacity build. The exact temporary runner source used for these trials is archived with all sample JSON and per-request TSV logs. The committed [extended runner](../benchmark/http_capacity_extended_compare.py) preserves the same 32,768 validation ceiling and uses a workspace-relative import path.

- [Compressed raw reports and request samples](http-capacity-extended-2026-10-12.raw.tar.gz), SHA-256 `567ec1bb64b4ce3c2984f2837826c80558913440ed083b4b098e19ddd70a23f7`
- Build provenance: `/tmp/forge-http-v2-capacity-build-20261012`
- The earlier 4,096-client result is [here](http-v2-capacity-4096-2026-10-12.md); it should be read as a tested lower bound, not a maximum.
