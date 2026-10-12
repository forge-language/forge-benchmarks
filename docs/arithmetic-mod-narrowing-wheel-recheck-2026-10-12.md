# Signed remainder narrowing with prime wheel kernel

The first narrowing candidates lost the trial-division kernel's initial
`d=3` strength reduction. This recheck paired the v1 signed-32-bit remainder
compiler candidate with the equivalent 6k±1 wheel kernel, which checks 2 and 3
separately and starts the dynamic loop at 5. Forge and Rust used the same wheel
source, dimensions (`n=2000`, `rounds=128`), timer, SDK archives and headers.
The candidate compiler was the only toolchain difference; a matched Rust wheel
binary served as the candidate control.

In 24 position-balanced pairs, baseline wheel Forge/Rust throughput was 1.0040
[1.0021, 1.0108]. Narrowing measured 0.9969 [0.9915, 1.0036] against its
source-matched Rust control. Paired candidate/baseline Forge throughput was
0.9953 [0.9918, 0.9984]. Every correctness, prewarm and measured checksum
matched the independent sieve reference. The wheel algorithm removes the
specific first-iteration `d=3` condition, but generic range guards still slow
this workload slightly and do not approach 1.10x Rust. The compiler candidate
remains discarded.

The JSON contains all paired samples, build commands, hashes, checks and the
executed comparison runner. The raw archive contains both frozen builds and
runner sources; SHA-256 `8497663e641bea4b1eebfaea1cbca4d8559f1a57c40e982613b51382f8a0d64a`. The wheel-source patch is recorded in
[cpu-prime-wheel-2026-10-12.patch](cpu-prime-wheel-2026-10-12.patch), and the
compiler patch is recorded in
[arithmetic-mod-narrowing-2026-10-12-v1.patch](arithmetic-mod-narrowing-2026-10-12-v1.patch).

[Machine-readable report](arithmetic-mod-narrowing-wheel-recheck-2026-10-12.json) · [Frozen builds](arithmetic-mod-narrowing-wheel-recheck-2026-10-12.raw.tar.gz)
