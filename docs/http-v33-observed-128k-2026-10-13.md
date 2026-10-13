# HTTP V3.3: 128,000-request observation

Forge and Rust each completed all 128,000 one-shot loopback requests in every one of eight measured trials and eight immediately preceding prewarms. The 4,096,000 measured/prewarmed requests all passed exact response and EOF verification with zero errors. Four server workers, 32-byte bodies, eight source addresses, a configured ceiling of 128,000 and 120-second phase timeouts match the previous high-count setup. The immutable current-compiler build and observer validation are documented in the [V3.3 calibration report](http-v33-observed-2026-10-13.md).

| Metric | Forge | Rust |
| --- | ---: | ---: |
| Complete measured trials | 8/8 | 8/8 |
| Completed requests per trial | 128,000 | 128,000 |
| Measured errors | 0 | 0 |
| Median observer request-loop req/s | 2,860 | 4,595 |
| Peak in-flight request states | 512–576 | 512–566 |
| Peak connected client states | 260–320 | 260–310 |
| Peak pending connects | 256–256 | 256–256 |
| Median per-trial median request latency (ms) | 34.55 | 36.06 |

The paired Forge/Rust throughput ratio is 0.7627, with a row-wise bootstrap 95% interval [0.3424, 1.6531]. The wide interval establishes neither a throughput winner nor the Rust 1.10 target. Individual measured Forge rates span 1,740–9,138 req/s; Rust spans 1,770–9,173 req/s. All timing outliers and attempts are retained, with no retry or discarded failures.

**The maximum user count and absolute server connection capacity remain unknown.** The observer recorded only 512–576 in-flight request states for Forge at the 128,000 ceiling, and 260–320 connected states. The connected counter describes client request states through response/EOF handling and may outlive server sockets; it does not count accepted server sockets, sessions or users. The previous interpretation of 128,000 as a simultaneous-population lower bound is withdrawn in the [V3.2 report](http-v32-capacity-128k-paired-2026-10-12.md). The old V3.2 raw timings remain unchanged and are not pooled with V3.3.

The full observation ran 2026-10-13 06:12:45–06:35:07 UTC on Linux AMD BC-250. Server CPUs are 0/2/4/6 and the sole observer CPU is 8. The observer internal timer starts after epoll/map setup and before event-vector allocation and ends after the final request TSV write. Client syscall, epoll, validation and TSV logging costs are timed. Readiness/go handshakes, footer printing and process exit are excluded; the parent go-to-exit wall time is retained separately. TCP churn, shared kernel state, a single observer reactor and closed connections constrain these finite runs. A read-only OMO review server ran on spare CPU 11 during part of this observation; source-oracle checks were also pinned there. Those processes are retained as background-load limitations, not excluded samples. CPU affinity does not eliminate shared-cache/kernel interference. HTTP was not tested on macOS or Windows; [native CPU verification](integrated-compiler-cross-os-2026-10-13.md) is separate.

[All measured samples, commands, peaks, passive kernel state and build hashes](http-v33-observed-128k-2026-10-13.json); [raw request TSVs and every attempt](http-v33-observed-128k-2026-10-13.raw.tar.gz), SHA-256 `83507f74d04ba9c0eb5ea9fb83d2f82cbb1731d7ab9560314237f6c415b8a40f`. The frozen server/compiler/SDK/observer binaries and validation evidence are in the [calibration archive](http-v33-observed-2026-10-13.raw.tar.gz).
