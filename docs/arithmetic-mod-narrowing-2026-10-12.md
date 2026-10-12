# Signed 32-bit remainder fast-path experiment

Two compiler-only candidates attempted to use 32-bit signed `%` when both
runtime operands round-trip through `int32_t`, while keeping the existing
64-bit zero/overflow checks and full-width fallback. The call-site macro
passed `!__builtin_constant_p(b)` so syntactically constant divisors avoided
the new range guard. Candidate v2 additionally checked `b == 3` in an attempt
to preserve the first divisor in the prime loop.

A 24-pair, position-balanced comparison measured the same corrected five CPU
fixtures with the same native SDK and Rust sources. Every small-input,
prewarm, and measured checksum matched. Compared with baseline, candidate v1
changed Forge throughput by LCG 1.0037 [1.0003, 1.0084], primes 0.9863
[0.9814, 0.9884], scan 1.0021 [0.9910, 1.0100], builder 1.0408
[0.9480, 1.0583], immutable append 0.9514 [0.8994, 0.9748]. Candidate v2
changed those rows by 0.9967 [0.9878, 1.0060], 0.9860 [0.9838, 0.9895],
1.0042 [0.9903, 1.0179], 1.0002 [0.9073, 1.0476], and 0.9287
[0.8794, 1.0021], respectively. Neither candidate improved the Rust-relative
prime result: source-matched Forge/Rust was 0.9980 [0.9939, 1.0010] for v1
and 0.9985 [0.9976, 1.0007] for v2. The baseline was 1.0107
[1.0090, 1.0117].

Disassembly of candidate v2 still shows hardware divisions for both paths:
64-bit `idiv` at `0x2808`/`0x2817` and 32-bit `idiv` at `0x284c`/`0x2e42`.
The explicit `b == 3` case did not restore reciprocal-multiply lowering; the
extra runtime checks also affect dynamic modulo in string workloads. Both
candidates are rejected and the compiler source was restored. Existing
arithmetic tests passed under UBSan at `-O0` and `-O3`; an extra dynamic
`INT32_MIN / -1` and remainder boundary now has regression coverage in Forge
commit `10e05d1`.

This is evidence against generic runtime narrowing for the current codegen
shape. It does not rule out a later proof-based optimization that can preserve
constant-divisor code generation without per-operation guards.

| Artifact | Purpose |
| --- | --- |
| [arithmetic-mod-narrowing-2026-10-12.json](arithmetic-mod-narrowing-2026-10-12.json) | Full samples, matched Rust controls, source/build hashes, and captured comparison runner |
| [arithmetic-mod-narrowing-2026-10-12-v1.patch](arithmetic-mod-narrowing-2026-10-12-v1.patch) | Signed narrowing guard without the divisor-3 branch |
| [arithmetic-mod-narrowing-2026-10-12-v2.patch](arithmetic-mod-narrowing-2026-10-12-v2.patch) | Same guard plus the divisor-3 attempt |
| [arithmetic-mod-narrowing-2026-10-12.raw.tar.gz](arithmetic-mod-narrowing-2026-10-12.raw.tar.gz) | Frozen baseline and candidate builds plus runner scripts; SHA-256 `1df38a7d63985125879bdff33a5c1c7ee85d5a1aabade88885dab6a784d4204e` |
