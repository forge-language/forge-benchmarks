# Small-prime prefilter experiment

The Forge-only benchmark fixture checks divisibility by 3 and 5 before its
existing Miller–Rabin / trial-division decision path. It handles `value < 2`
and primes 2, 3 and 5 first. For every other integer divisible by either
small prime, the value is composite; values not divisible by either continue
through the original path unchanged. The Rust fixture remains the base-2/3
Miller–Rabin control. This changes the algorithm in the Forge fixture and does
not measure compiler-only or language-wide performance.

The 120-pair prime-only run measured 1.6869 Rust/Forge throughput
[1.6657, 1.7010] at n=2000, rounds=128. The 120-pair full-suite run measured
1.6915 [1.6685, 1.7038] for primes, with LCG 1.5083 [1.5030, 1.5142], scan
1.9388 [1.9276, 1.9478], builder 1.0966 [1.0663, 1.1539], and immutable
append 18.7241 [11.0113, 19.5311]. The builder interval crosses 1.10 and is
inconclusive in the suite; its focused 120-pair result was 1.1990
[1.1087, 1.2786]. Do not generalize these workload-specific results to other
programs or machines.

The runner checked 30 direct reference cases, 1230 warmups and 1200 measured
outputs in the full suite. An additional 175 cases (including negatives,
small-prime boundaries, the Miller–Rabin cutoff and randomized batches)
matched the independent sieve reference in both executables. Full source
hashes, commands, environment and paired observations are in the linked JSON
reports: [focused primes](cpu-prime-mr-smallprime-120-2026-10-12.json),
[full suite](cpu-prime-mr-smallprime-full-120-2026-10-12.json), and [focused
builder](cpu-prime-mr-smallprime-builder-120-2026-10-12.json).
