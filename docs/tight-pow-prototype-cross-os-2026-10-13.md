# Exact bounded modular power: native prototype evidence

This is explicit generated-C screening, not evidence from the new generic compiler implementation. Run [38358078838](https://github.com/forge-language/forge-benchmarks/actions/runs/38358078838) compares the same shipped compiler `420d66f` against its generated C with a bounded modular-power prefix. Rust controls, algorithms, shared SDK and native build flags are unchanged. Six native jobs completed; 720 direct checks, 5,400 prewarms and 5,400 measured executions match independent references. Each job uses 60 balanced three-way groups per workload.

| Native job | Workload | Candidate/current Forge ratio (95% interval) | Candidate/Rust ratio (95% interval) | Target |
| --- | --- | --- | --- | --- |
| [macos-15-0](cross-os-38358078838-macos-15-0.json) | lcg | 0.9975 [0.9358, 1.0230] | 1.6499 [1.5907, 1.6863] | supported for this case |
| [macos-15-0](cross-os-38358078838-macos-15-0.json) | primes | 1.3220 [1.2866, 1.3567] | 1.2334 [1.2154, 1.2503] | supported for this case |
| [macos-15-0](cross-os-38358078838-macos-15-0.json) | scan | 0.9900 [0.9542, 1.0194] | 8.7952 [8.5363, 9.0711] | supported for this case |
| [macos-15-0](cross-os-38358078838-macos-15-0.json) | builder | 1.0021 [0.9832, 1.0312] | 3.3018 [3.2256, 3.3494] | supported for this case |
| [macos-15-0](cross-os-38358078838-macos-15-0.json) | immutable | 0.9954 [0.9725, 1.0038] | 23.2267 [22.6948, 23.7237] | supported for this case |
| [macos-15-1](cross-os-38358078838-macos-15-1.json) | lcg | 0.9982 [0.9816, 1.0068] | 1.6205 [1.6023, 1.6473] | supported for this case |
| [macos-15-1](cross-os-38358078838-macos-15-1.json) | primes | 1.3467 [1.2911, 1.4141] | 1.2325 [1.2069, 1.2947] | supported for this case |
| [macos-15-1](cross-os-38358078838-macos-15-1.json) | scan | 0.9992 [0.9904, 1.0175] | 8.9343 [8.8509, 9.3346] | supported for this case |
| [macos-15-1](cross-os-38358078838-macos-15-1.json) | builder | 0.9967 [0.9726, 1.0290] | 3.2824 [3.2319, 3.3251] | supported for this case |
| [macos-15-1](cross-os-38358078838-macos-15-1.json) | immutable | 0.9970 [0.9800, 1.0269] | 24.2647 [23.4357, 24.9607] | supported for this case |
| [ubuntu-24.04-0](cross-os-38358078838-ubuntu-24.04-0.json) | lcg | 1.0000 [0.9996, 1.0003] | 1.8551 [1.8544, 1.8556] | supported for this case |
| [ubuntu-24.04-0](cross-os-38358078838-ubuntu-24.04-0.json) | primes | 1.3627 [1.3603, 1.3649] | 1.3864 [1.3850, 1.3878] | supported for this case |
| [ubuntu-24.04-0](cross-os-38358078838-ubuntu-24.04-0.json) | scan | 1.0011 [0.9884, 1.0086] | 2.4148 [2.4025, 2.4383] | supported for this case |
| [ubuntu-24.04-0](cross-os-38358078838-ubuntu-24.04-0.json) | builder | 0.9996 [0.9976, 1.0015] | 1.7212 [1.7181, 1.7237] | supported for this case |
| [ubuntu-24.04-0](cross-os-38358078838-ubuntu-24.04-0.json) | immutable | 1.0030 [1.0000, 1.0058] | 21.8516 [21.7965, 21.9385] | supported for this case |
| [ubuntu-24.04-1](cross-os-38358078838-ubuntu-24.04-1.json) | lcg | 0.9999 [0.9994, 1.0005] | 1.8541 [1.8534, 1.8547] | supported for this case |
| [ubuntu-24.04-1](cross-os-38358078838-ubuntu-24.04-1.json) | primes | 1.3648 [1.3601, 1.3687] | 1.3793 [1.3777, 1.3816] | supported for this case |
| [ubuntu-24.04-1](cross-os-38358078838-ubuntu-24.04-1.json) | scan | 0.9994 [0.9986, 1.0001] | 2.4280 [2.4262, 2.4329] | supported for this case |
| [ubuntu-24.04-1](cross-os-38358078838-ubuntu-24.04-1.json) | builder | 0.9856 [0.9749, 0.9944] | 1.5534 [1.5367, 1.5690] | supported for this case |
| [ubuntu-24.04-1](cross-os-38358078838-ubuntu-24.04-1.json) | immutable | 1.0004 [0.9979, 1.0021] | 26.2971 [26.2395, 26.3563] | supported for this case |
| [windows-2022-0](cross-os-38358078838-windows-2022-0.json) | lcg | 1.0001 [0.9997, 1.0004] | 1.8580 [1.8575, 1.8585] | supported for this case |
| [windows-2022-0](cross-os-38358078838-windows-2022-0.json) | primes | 1.1068 [1.1059, 1.1095] | 1.3828 [1.3818, 1.3850] | supported for this case |
| [windows-2022-0](cross-os-38358078838-windows-2022-0.json) | scan | 0.9998 [0.9992, 1.0003] | 2.3539 [2.3518, 2.3567] | supported for this case |
| [windows-2022-0](cross-os-38358078838-windows-2022-0.json) | builder | 1.0084 [1.0058, 1.0102] | 1.5522 [1.5507, 1.5541] | supported for this case |
| [windows-2022-0](cross-os-38358078838-windows-2022-0.json) | immutable | 1.0001 [0.9977, 1.0026] | 78.2362 [77.9907, 78.5239] | supported for this case |
| [windows-2022-1](cross-os-38358078838-windows-2022-1.json) | lcg | 0.9999 [0.9993, 1.0005] | 1.8571 [1.8558, 1.8581] | supported for this case |
| [windows-2022-1](cross-os-38358078838-windows-2022-1.json) | primes | 1.1293 [1.1072, 1.1669] | 1.3798 [1.3613, 1.3943] | supported for this case |
| [windows-2022-1](cross-os-38358078838-windows-2022-1.json) | scan | 0.9993 [0.9985, 1.0015] | 2.4915 [2.4299, 2.5372] | supported for this case |
| [windows-2022-1](cross-os-38358078838-windows-2022-1.json) | builder | 1.0026 [0.9934, 1.0067] | 1.6497 [1.6407, 1.6661] | supported for this case |
| [windows-2022-1](cross-os-38358078838-windows-2022-1.json) | immutable | 0.9730 [0.9610, 0.9939] | 78.4333 [77.4215, 79.6627] | supported for this case |

All 30 candidate/Rust row-wise lower 95% bounds exceed 1.10 in these jobs. Prime improves current Forge by 1.32–1.35× on macOS, 1.36× on Linux and 1.11–1.13× on Windows. Prime/Rust reaches about 1.23×, 1.38× and 1.38× respectively. This resolves the prototype suite threshold on the tested machines; it does not prove a language-wide bound, future hardware results, or the pending actual-compiler release gate. OS, CPU, virtualization and C/Rust backend versions differ, so causal OS effects cannot be isolated.

The prefix applies only with int128, nonnegative base/exponent and modulus d in [2, 2^21]. For B=2^64, R=ceil(B/d), e=dR-B in [0,d), and positive n<d², n*e<n*d<2^63<B. With r=n%d, B<=(d-r)B, so floor(nR/B)=floor(n/d). n=0 is immediate. Every factor/result stays below d, hence each product is below d² and fits signed i64; quotient correction is unnecessary. The 2^21 bound is sufficient, not asserted maximal. First-bit peeling removes a multiplication by one, and the final dead square/remainder can be skipped because it is pure and nontrapping with nonzero d. All out-of-domain inputs retain the unchanged original checked/wrapping body.

Independent original/candidate arithmetic, signed wrapping and trap oracles passed 713 cases at O0/O3 UBSan with native int128 and forced no-int128: 5,704 executions. Boundary moduli include 2^21-1, 2^21 and 2^21+1; MAX/MIN inputs, negative/zero exponents and fallback traps are covered. The OMO child proof review found no blocker and accepted the HTTP per-request failure-path correction. Its prose has minor precision issues: strict n*e<n*d excludes n=0 (handled separately); the guard is conservative; the candidate has a peeled first bit and fewer literal while iterations; the omitted original modulo is nontrapping because d is nonzero. Complete raw review prose is preserved.

[All native sources, binaries, disassembly, oracle source/logs and OMO review](tight-pow-prototype-cross-os-2026-10-13.raw.tar.gz), SHA-256 `21910d8fd1d5bc0cdf8e24c9033cecaccdddc514e7afb75505fff20642654083`. The subsequent generic compiler matcher must independently pass regression, semantic review and unchanged-compiler performance gates before these gains are reported as shipped behavior.
