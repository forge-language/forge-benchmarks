# Passive diagnosis of long HTTP benchmark attempts

The ongoing prepared-HTTP comparison encountered complete, correct attempts
whose duration was dominated by TCP connection stalls. These attempts remain
in the original report and raw request vectors. No sample was discarded,
retried, restarted or edited for this diagnosis; no new workload or build ran.

The first affected Forge prewarm used a 4,096-byte body, four serving workers,
16 client threads and 12,000 requests. It completed every request with exact
response bytes and zero errors in 105.514286 seconds. Its median request latency
was 354,902 ns and p99 was 2,134,701 ns. Exactly 32 requests exceeded one second:
each client lane had one request taking approximately 68.1–68.46 seconds and
another taking 35.63–36.14 seconds. The server used 1.40 CPU seconds during the
105.5-second observed load, and all worker affinity/count checks passed.

A subsequent Forge prewarm with **one** serving worker also completed correctly
in 69.640 seconds; all 16 lanes had one request taking about 68.32 seconds. During
that stall, passive observation showed:

- Server PID 3504216 listening on port 60833, with LISTEN receive queue zero and
  effective backlog 4,096; its wait channel was `ep_poll`.
- All 16 client sockets in `SYN-SENT` to that port, with Send-Q 1 and Recv-Q 0.
- No `SYN-RECV` sockets; all client worker wait channels were `wait_woken`.
- Client PID 3504218 waiting for its worker threads, with the expected 17 threads.

These observations place this event before the HTTP header-reading and response
algorithm. The one-worker event shows that SO_REUSEPORT or a stranded
multi-worker listener cannot be a necessary cause. Normal accept-backlog
saturation is unsupported: the listener queue was empty, concurrency was 16,
and global `ListenOverflows`/`ListenDrops` counters were both zero. These are
observations of this event, not proof that every long request has the same cause.

The Forge and Rust listener source paths both use AF_INET/TCP, bind `0.0.0.0`,
set SO_REUSEADDR, set SO_REUSEPORT for multi-worker listeners, request
65,536-byte receive/send buffers, request backlog 8,192, and use nonblocking
listeners with level-triggered EPOLLIN. Neither path enables TCP_DEFER_ACCEPT,
TCP_FASTOPEN, TCP_NODELAY on prepared-path accepted sockets, socket filters or
IP_FREEBIND. Both accept with NONBLOCK|CLOEXEC and then use blocking receive/send
with five-second timeouts. Rust's socket2 additionally makes listener fds
CLOEXEC; listener startup/rebinding order also differs outside measurement.
No handshake-relevant option difference was found in these source paths. This
source inspection does not prove actual per-socket kernel values or an external
cause; final root cause remains unproven.

A later Forge four-worker/concurrency-64 **measurement** completed correctly in
38.216 seconds and retained 66 requests exceeding one second. A Rust
one-worker/concurrency-64 **prewarm** also completed correctly in 20.153 seconds
with 42 requests exceeding one second. Both implementations can therefore
encounter the anomaly; a Forge-only algorithm explanation is insufficient.

The observer in `benchmark/http/src/load.rs` calls blocking `TcpStream::connect`
before installing its ten-second socket read/write timeouts. Consequently those
timeouts do not bound connection establishment, and successful requests can
include much longer TCP handshake retries. Observed kernel settings were
`tcp_syn_retries=6` and `tcp_syn_linear_timeouts=4`; the long delays are consistent
with retransmission/backoff, although their exact packet-loss cause remains
unproven. The separately recorded snapshot contains the actual settings and
all long request IDs/durations from these completed attempts.

The live host had roughly 150,090 conntrack entries versus a maximum of 262,144,
about 7,971 TIME_WAIT sockets versus a maximum of 65,536, and ephemeral ports
32,768–60,999. These instantaneous counts did not show table/port exhaustion.
Global TCP memory use was 272,674 pages, above the middle configured memory
threshold of 240,493 pages; this merits further investigation but does not prove
that memory pressure caused the handshake loss. Global counters are shared
across unrelated host services and cannot attribute events to this benchmark.
Firewall rules could not be read without elevated privileges, so a firewall,
network namespace policy or other host drop mechanism was not ruled out.

Keep the current run unchanged. Once timing is finished, a separately identified
observer protocol should use `TcpStream::connect_timeout` and record separate
connection, write and read/EOF durations. It should preserve every failed
request and periodically flush request observations so a parent timeout cannot
lose the already completed portion of an attempt. Readiness checks can retain
per-listener inode/queue information, while passive before/after global TCP
counter and socket snapshots can help distinguish TCP retry episodes from
server queueing. Any changed observer, timeout or socket/port policy requires
fresh immutable build hashes, a new validation pass and a new report; results
must not be silently merged with this protocol.

The present throughput ratio includes connection establishment and every
complete request, so the stalls belong to its measured outcome. They materially
limit interpretation as isolated server capacity, and their preserved latency
vectors must accompany any target claim.

Evidence: [passive snapshot and long request vectors](http-prepared-handshake-diagnostic-2026-10-12.json),
and the unmodified `http-prepared-rust-forge-2026-10-12.raw` attempt files named in
that snapshot. This note was written while the original 16-pair run was active;
it describes the observed subset rather than the final run distribution.
