# LCG countdown-loop probe — no performance win

A source-level experiment tested whether expressing the LCG inner loop as a
countdown could remove the increment and comparison that appeared in the
Forge loop. The baseline used `i = 0; while (i < n) { ...; i = i + 1; }`. The
candidate used `remaining = n; while (remaining > 0) { ...; remaining =
remaining - 1; }`. For every signed `n`, both perform `max(n, 0)` iterations;
the countdown cannot underflow because it starts positive and stops at zero.

The two Forge fixtures were built from the same compiler, runtime/stdlib
archives, C flags, Rust fixture, timer and CPU. The Rust source stayed fixed as
the source-matched performance control. Both runs used the same 28 seeds,
prewarmed position-balanced protocol, 250,000 iterations × 64 rounds, CPU 0,
and independent Python checksum reference. All correctness checks,
prewarms and measured checksums passed. These are separate source variants;
the ratios below compare each Forge variant with the unchanged Rust control.

| Forge fixture | Forge median | Rust median | Rust / Forge throughput (95% interval) |
| --- | ---: | ---: | ---: |
| Incrementing baseline | 60.563 ms | 60.651 ms | 0.9977 [0.9954, 1.0046] |
| Countdown candidate | 60.595 ms | 61.066 ms | 1.0134 [1.0049, 1.0180] |

The candidate Forge time did not improve: its paired Forge baseline/candidate
speedup was 0.9997 [0.9951, 1.0082]. It remains well below the 1.10 Rust target.
The point-estimate ratio increase comes from the separate Rust control timing
in the second run, not from faster Forge execution.

Disassembly confirms why the source rewrite did not help. The baseline Forge
loop increments its induction variable before the remainder calculation, then
compares it with `n` and branches (`inc`, `cmp`, `jne`). The countdown version
decrements after the remainder calculation, moves the computed value into the
next iteration's input register, then branches (`dec`, `mov`, `jne`). Both
retain three loop-control/data-movement instructions, while the baseline can
overlap its increment with the remainder calculation. No compiler change is
justified by this probe. Raw reports and frozen executables are retained under
`/tmp/rust110-countdown-probe/` for local reproduction.
