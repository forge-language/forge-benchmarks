# Quotient-based trial-division loop bound — rejected

This source-level experiment replaced `d * d <= value` with
`d <= value / d` in the prime-search loop, and recomputed the quotient after
each increment of `d`, in both Forge and Rust. The change avoids squaring the
divisor, but it also adds a division to each loop iteration. It was measured
with 24 paired inputs, 2 warmups, CPU 0, the same random seed/order and build
artifacts for baseline and candidate. All checksum and runner correctness
checks passed.

| Variant | Forge median | Rust median | Forge/Rust throughput |
| --- | ---: | ---: | ---: |
| Original `d*d` bound | 74.651 ms | 75.672 ms | 1.0104 [1.0032, 1.0184] |
| Quotient bound | 75.055 ms | 149.342 ms | 1.9925 [1.9884, 2.0045] |

The larger Forge/Rust ratio is caused by the Rust candidate becoming about
1.97x slower; Forge itself did not improve. In the same-seed paired comparison,
candidate/baseline Forge throughput was 0.9980 [0.9950, 1.0046], while Rust
throughput was 0.5072 [0.5058, 0.5088] (candidate kernel time was about 1.97x
baseline). Thus this is not evidence
of a Forge optimization, and the candidate is not adopted. The generated
Forge binary contains a hardware `idiv` in the prime loop (candidate
`objdump -d -Mintel`, address `0x2c82`); source-level quotient reuse did not
yield a shared quotient/remainder operation that improved the target workload.

The measurements cover the benchmark's generated positive values and do not
claim a general semantic proof for arbitrary signed inputs. Both versions
matched their checksums for the runner's correctness cases.

[Baseline samples](prime-quotient-loop-bound-baseline-2026-10-12.json),
[candidate samples](prime-quotient-loop-bound-candidate-2026-10-12.json).
