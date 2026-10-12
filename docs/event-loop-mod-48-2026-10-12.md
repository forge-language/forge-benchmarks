# Forge event-loop modification benchmark

Registered-fd FR_EVENT_READ modification throughput: Forge public event API versus direct Rust epoll_ctl(MOD). The candidate replaces Linux delete+add with one EPOLL_CTL_MOD, falling back to ADD only when the descriptor is not registered.

48 paired samples, 100,000 successful updates per sample, pinned to CPU 0. Runtime baseline `e3eb0089bdc9760d0d6fbaadd4d9fde0f17f26fe`; optimized implementation `7e7bb50699945815ef427f0c98aeed801399add5`.

| Implementation | Median updates/s | Median time (ms) | Forge/Rust throughput |
| --- | ---: | ---: | ---: |
| base | 491,786 | 203.341 | 0.1649x |
| candidate | 2,890,580 | 34.595 | 0.9682x |
| rust | 2,986,212 | 33.487 | 1.0000x |

Candidate/base paired speedup: 5.8800x [5.8416, 5.9179].
Forge/Rust paired throughput: base 0.1649x [0.1631, 0.1662], candidate 0.9682x [0.9588, 0.9752].

The update path improved 5.88x over the baseline, but reaches 96.8% of direct Rust epoll_ctl(MOD) throughput and stays below the 1.10 target. The interval is tight for this host and workload. The change is an API-level improvement; it is not evidence of end-to-end scheduler throughput, and the event-loop modification API is not currently called by the runtime scheduler. The benchmark checks every update return code and validates final userdata via readiness delivery.

All samples and hashes: [event-loop-mod-48-2026-10-12.json](event-loop-mod-48-2026-10-12.json).
