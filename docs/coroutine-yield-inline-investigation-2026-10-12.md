# Coroutine yield-call inlining investigation

The four-worker `mixed-cpu` coroutine workload remains below the Rust control
(0.9024 [0.8191, 1.0535] in the latest complete-lifecycle comparison). The
generated coroutine calls `fr_coro_inline_yield` at each logical yield. This
investigation tested whether cross-translation-unit LTO or forcing that call
inline closes the gap. Both candidates used the current Forge compiler and
stdlib; neither changed the fixture or scheduler semantics.

First, a Release runtime archive built with CMake IPO/LTO was compared against
the regular runtime in 16 paired groups per case/worker count. The linked LTO
binary specialized `fr_coro_inline_yield` but retained a call from the
coroutine. No case established a 10% improvement. For mixed CPU, candidate /
baseline was 0.9994 [0.9974, 1.0011] at one worker, 1.0132 [0.9960, 1.0883]
at two, and 1.0472 [0.9903, 1.1503] at four. The four-worker interval includes
both directions and does not establish a gain. [All paired samples and build
hashes](coroutine-runtime-lto-2026-10-12.json).

Second, two LTO runtimes were built with identical GCC 13.3.0
`-O3 -DNDEBUG -march=native` flags. The candidate added a forced-inline
attribute to `fr_coro_inline_yield`; disassembly confirmed the call disappeared
from generated coroutine code. The 16-pair comparison still found no
established improvement. Mixed CPU candidate / baseline was 1.0001
[0.9965, 1.0064] at one worker, 0.8855 [0.8289, 0.9873] at two, and 0.9815
[0.8764, 1.1539] at four. The candidate was not adopted. [All paired samples,
artifact hashes and exact commands](coroutine-yield-always-inline-2026-10-12.json).

Both LTO runtime builds passed all three runtime CTest suites. In each paired
run, 27 direct correctness checks, 288 same-input prewarms and 288 measured
executions matched every task result and completion count. These results show
that removing the yield call alone does not explain the multi-worker gap; they
do not rule out queue contention, worker balance or other runtime costs.

OMO delegation could not run: the configured `llm.seohu.xyz` endpoint timed
out, and prior OMO requests to both configured models ended with the same API
connection error. No OMO findings are claimed.
