# Unchanged generic compiler: local full-suite recheck

Compiler `a750b60` is compared with the frozen `420d66f` producer and unchanged matched Rust on local Linux AMD BC-250. Both compilers use one immutable SDK, source fixtures, timer and native build flags. No generated-C probe is applied. All 120 direct checks, 900 input-matched prewarms and 900 measurements pass independent references. Every workload has 60 balanced three-way groups with all six orders equally represented. The six OMO reviews finished and their own server was stopped before measurement.

| Workload | New/current Forge throughput ratio (95% interval) | New Forge/Rust throughput ratio (95% interval) |
| --- | --- | --- |
| lcg | 1.0357 [1.0115, 1.0719] | 1.3052 [1.2801, 1.3694] |
| primes | 1.1684 [1.1134, 1.2015] | 1.5680 [1.4779, 1.6223] |
| scan | 1.0095 [0.9848, 1.0262] | 2.5841 [2.5038, 2.7103] |
| builder | 0.9952 [0.9731, 1.0085] | 1.6182 [1.5910, 1.7048] |
| immutable | 0.9887 [0.9332, 1.0807] | 8.1309 [7.3806, 9.4808] |

All five row-wise lower 95% Forge/Rust bounds exceed 1.10 on this host/run. Prime gains about 16.8% over the prior compiler; LCG also rises 3.6% in this run, while the scan/builder/immutable change intervals include no change. No causal attribution to the arithmetic pass is made for those other rows. This is representative local workload evidence, not a language-wide guarantee or proof of native macOS/Windows results. The unchanged-compiler native verification run [38513930496](https://github.com/forge-language/forge-benchmarks/actions/runs/38513930496) also passes all 30 native row-wise targets; see the [complete native report](bounded-modpow-native-cross-os-2026-10-14.md).

[All pairs, environment, source/SDK/toolchain hashes and commands](bounded-modpow-generic-full-60-2026-10-14.json); [frozen inputs, compilers, executables, disassembly and exact dimension source](bounded-modpow-generic-full-60-2026-10-14.raw.tar.gz), SHA-256 `1c8f14739b47dc7a27a205ee3d4597a31c7efda49b7093d4667b26ed04866223`. [Generic proof and six OMO reviews](bounded-modpow-lowering-2026-10-14.md).
