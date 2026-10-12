# Event-loop batch capacity results

The runtime now uses a default event batch capacity of 256. In paired Linux burst-drain measurements, capacity 256 kept the 64-ready-fd case at parity with the 64-entry baseline and improved median throughput by 3.8–4.0% for bursts of 256 and 1024. The 4096-fd sample favored 256, but its confidence interval was wide. None of the sampled burst sizes established the 1.10x Rust-throughput target.

Capacity 1024 was rejected: it substantially regressed the 64- and 256-fd bursts and did not establish an improvement for larger bursts. This tradeoff favors a moderate batch size that avoids repeated polling under moderate fan-in without imposing the large-batch cost on common small batches.

The selected implementation is [forge-runtime commit `0b1e7d4`](https://github.com/forge-language/forge-runtime/commit/0b1e7d4). The selected 48-pair comparison includes raw measurements, source and binary hashes, and per-row paired bootstrap intervals in [JSON](event-batch-256-adopted-48-2026-10-12.json) and [Markdown](event-batch-256-adopted-48-2026-10-12.md). The rejected 1024-capacity run is in [JSON](event-batch-1024-48-2026-10-12.json) and [Markdown](event-batch-1024-48-2026-10-12.md). The reproducible harness is under [`benchmark/event_batch`](../benchmark/event_batch).

These are event-loop microbenchmarks. They measure ready-descriptor drain time through Forge's public callback API against direct Rust `epoll_wait`; they do not measure scheduler or application throughput.
