# HTTP V3.3 observed concurrency and throughput

On Linux AMD BC-250, four pinned server workers and one separate pinned epoll observer completed all 32 measured and 32 prewarmed samples. Every sample completed 4,096 new loopback requests, checked every response byte and EOF, and recorded zero errors. Each configuration has eight randomized, position-balanced Forge/Rust pairs; body size is 32 bytes and eight 127/8 source addresses are used. The compiler, runtime and stdlib binary hashes match the frozen current-compiler CPU suite (Forge `420d66f`, runtime `dcbb192`, stdlib `6aa2866`).

| Configured ceiling | Language | Median req/s | Peak in-flight range | Peak connected-state range | Median per-trial median latency (ms) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 256 | Forge | 8,585 | 256–256 | 256–256 | 18.62 |
| 256 | Rust | 8,671 | 256–256 | 256–256 | 19.32 |
| 4,096 | Forge | 8,671 | 512–575 | 256–319 | 38.03 |
| 4,096 | Rust | 8,517 | 512–569 | 256–313 | 38.05 |

At ceiling 256, paired Forge/Rust throughput is 1.0219 [0.9661, 1.0901]; at ceiling 4,096 it is 1.0525 [0.7768, 1.1193]. Neither interval establishes a throughput winner. The 256 row fails the Rust 1.10 target; the 4,096 row is inconclusive. These are row-wise 10,000-resample bootstrap intervals, with no discarded timing outliers or retries.

The configured ceiling is a limit. At ceiling 4,096, Forge observed only 512–575 in-flight request states and 256–319 connected states across measured trials. This directly demonstrates why lane settings and total completed requests cannot be used as actual simultaneous population counts. In-flight states include pending connects, whose peak is capped at 256. Connected states persist through response validation and EOF handling and can outlive server sockets. The gauges measure client state, not accepted server sockets, sessions or users. **Maximum users and absolute server capacity remain unestablished.**

V3.3 adds constant-time gauge updates to the observer. Its timings are preserved separately and are not pooled with V2 or V3.2. Client connect, validation, TSV logging and process completion are timed. These prepared endpoints close each connection, with no application routing, TLS, database work, keepalive or session model. The shared TCP namespace and single client CPU constrain extrapolation. HTTP results are Linux only; separate native CPU evidence covers macOS and Windows.

Validation: seven footer/TSV unit checks pass; nine epoll controlled-peer tests pass, including a four-peer barrier proving the connected peak is four, partial response, wrong bytes, extra bytes, saturated connect queue, stop-after-failure and retained rows after termination. V2 compatibility passes eight tests with the new gauge test explicitly skipped. The first epoll validation failed two assertions because V2 names whole-packet mismatch `response`, while epoll detects it incrementally during `read`; both observer errors were correctly detected. The test was corrected to require the exact protocol-specific stage. Both failed and corrected evidence directories and executed test sources are retained.

[Complete measurements and metadata](http-v33-observed-2026-10-13.json); [all raw attempts, validation evidence and frozen build](http-v33-observed-2026-10-13.raw.tar.gz), SHA-256 `2912fb8eb6624f8646962ab19cd7eeef583f96156f5a465793062bdc018fcd9d`. Earlier capacity interpretations are corrected in the [128k V3.2 report](http-v32-capacity-128k-paired-2026-10-12.md) and [V2 extended report](http-capacity-extended-2026-10-12.md).
