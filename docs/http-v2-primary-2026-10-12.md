# Prepared HTTP V2 primary paired run — failed, no performance claim

The pre-registered primary configuration was Forge public `http_prepare`/`http_serve_mt` versus the owned Rust/socket2 backend: 4 server workers, 64 closed-loop client lanes, 12,000 requests per sample, and a 4,096-byte body. Inputs, expected response bytes, worker/client CPU affinity, and build artifacts were shared and checked. The run completed seven full Forge/Rust pairs, then stopped during the Rust prewarm of pair 8. The observer retained all attempts and the runner made no retries.

The failed Rust prewarm recorded 991 request rows: 927 completed and 64 connect timeouts at the configured 5-second timeout. It did not reach the 12,000-request target, so the whole comparison is `failed_no_claim`; completed pairs are not selectively aggregated as a performance result. The Forge and Rust response validation on completed requests was retained in each TSV/JSON attempt file.

The passive host snapshot recorded global `nf_conntrack_count` at 261,217 / 262,144 before this trial and 262,144 / 262,144 afterward. The global `TCPTimeWaitOverflow` counter increased from 5,864,498 to 5,865,425 during the failed sample. These counters are shared-host diagnostics, not per-process attribution.

This is evidence of network resource pressure during the failed sample, but the counters are global to the network namespace and do not establish which process filled the table or caused the timeouts. The run cannot support a Forge-versus-Rust throughput claim or an absolute service capacity. The earlier short capacity sweep remains limited to its 1,024-request trials.

| Evidence | Value |
| --- | --- |
| Completed full pairs | 7 |
| Failed sample | Rust prewarm, pair 8 |
| Attempted rows in failed sample | 991 |
| Completed / failed rows | 927 / 64 |
| Failed stage | TCP connect (64 × 5 s) |
| Conntrack count before / after | 261,217 / 262,144; maximum 262,144 |
| Comparison status | `failed_no_claim` |

Full report: [http-v2-primary-2026-10-12.json](http-v2-primary-2026-10-12.json). All attempt JSON, TSV, process logs and observer output are preserved in [the compressed raw bundle](http-v2-primary-2026-10-12.raw.tar.gz), SHA-256 `0a479b026a896a58ee2faa9e7d0203fd41a5447de00ff2adbcebe26b32a51b53`.
