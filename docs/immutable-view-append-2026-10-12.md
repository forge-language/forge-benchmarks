# Cached-length immutable append experiment

The additive native API `str_view_append_byte(view, value)` carries a cached
byte length while keeping every returned view immutable. Its metadata and
snapshot share one arena allocation. The legacy `str_append` implementation
and exported symbol are unchanged.

Two independent same-session comparisons used 16 paired groups each at
`n=4096`, `rounds=512`. Both workloads used the same runtime seeds and balanced
Forge/Rust execution order within each run. Every sample matched the
independent weighted-checksum reference; no failures or outliers were removed.
The runner used the same frozen compiler, runtime and stdlib artifacts within
each run, a shared monotonic timer, one CPU affinity, and per-input prewarming.

| Run | Legacy Forge/Rust throughput | Cached-view Forge/Rust throughput | Candidate / legacy Forge throughput |
| --- | ---: | ---: | ---: |
| Seed 20261012 | 0.2347 | 0.2862 | 1.1149 |
| Seed 20261013 | 0.2356 | 0.2824 | 1.1134 |
| Combined 32 pairs | — | — | 1.1141 [1.1060, 1.1189] |

The combined interval is a paired median bootstrap over the 32 per-pair
`legacy Forge time / cached-view Forge time` ratios, using 10,000 resamples
with `random.Random(20261012)`. Each run independently
showed about an 11% gain over the prior Forge implementation. The cached-view
path still reached only 28.6% of Rust throughput in the first run and 28.2% in
the second, far below the 1.10 Rust-relative target.

This is a constant-factor improvement to the tested ASCII workload. It still
copies each prefix and retains every snapshot until arena reset, so its work
and arena use remain O(n²). The fixture does not establish gains for arbitrary
Unicode, other input sizes, applications, or other hosts. Rust still uses the
same repeated-prefix-copy control; the comparison does not claim that the
cached-view operation itself is a Rust language feature.

Raw records, including all samples, commands, checksums, environment and
artifact hashes:

- [Fixed dimensions](immutable-view-append-rounds-2026-10-12.json),
  `4096 × 512` for both variants.

- [Run 1 raw JSON](immutable-view-append-2026-10-12.json), SHA-256
  `383a38a8a76ca5a4dcadfd46ade9bacd7546b03f34ddfce9322f7aeb929e6f19`.
- [Run 2 raw JSON](immutable-view-append-recheck-2026-10-12.json), SHA-256
  `0bf1b40b2407b67f7928612c6d02a4036904714e48aabd3127917ea9b7519db6`.
