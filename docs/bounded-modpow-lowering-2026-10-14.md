# Generic bounded modular exponentiation

Compiler `a750b60923bcc71adda025596664dd9a0413f80b` recognizes a complete pure binary-exponentiation function by AST structure and binding, independent of function/local/parameter names. All parameters and locals are int64; the body has three initial lets, an exact bit-test/product/square/halving loop, and returns only its result. Extra operations, calls, observers, escaping factor/power state, shadowing and suspended-coroutine bodies are excluded. Parameter-role aliases are allowed; the source bindings remain fixed. The prefix is emitted for ordinary, module and exported library functions before invariant descriptors.

With int128, nonnegative base/exponent and modulus in [2,2^21], every product is below d² and fits signed i64. ceil(2^64/d) produces the exact quotient for those products, so no correction is required. The first multiply by one and final dead square/modulo are safely omitted. All other inputs retain the original checked/wrapping body and its initial modulo trap, including zero or negative exponents with invalid divisors. No-int128 targets retain that body. The bound is sufficient rather than maximal. [Detailed math and prototype screening](tight-pow-prototype-cross-os-2026-10-13.md).

The matcher uses the existing per-function scan budget, charges parameter scans, caps synthetic-name retries at 64, checks label-counter headroom, and declines malformed expression shapes without emitting a partial prefix. No public API, ABI, allocation lifetime or JavaScript arithmetic implementation changes.

Final validation: all 22 CTest suites pass. Named logs additionally show 40 compiler and 36 arithmetic tests passing. The full-width matrix has 928 nontrapping vectors plus six initial-trap cases, tested at O0/O3 UBSan and JS; ordinary no128/forced-ARM builds cover the vector, and exported-library trapping is also checked with combined no128/ARM macros. Library/module tests cover big positive/negative 64-bit arguments/results, qualified-call disambiguation and base/exponent role aliases. Matcher tests cover 12 rejected shapes, commuted bit/product operands, live and unused name collisions, bounded 64-collision fallback, and a suspended coroutine retaining the checked body. Forced macros are local semantic checks, not real ARM speed evidence.

Six actual OMO-delegated child sessions completed independent arithmetic, matcher, C portability, test coverage, HTTP and cross-OS evidence reviews. Initial task launches failed because the configured deep model was not registered; the coordinator retried and created 13 child sessions in total. The original six requested sessions were resumed with the working session-local `opencode/mimo-v2.6-flash-free` model and `Sisyphus-Junior` agent. Only those six completed reviews are credited below; routing failures, coordinator messages and original child relationships are preserved.

| Completed OMO child | Scope |
| --- | --- |
| `ses_ec76b6ef1ffeWXHBUo2p3mCezo` | Audit tight-pow arithmetic proofs |
| `ses_ec76b3fd8ffeKE06xfpejJmvPR` | Audit AST matcher soundness |
| `ses_ec76b178affedPKJS86hKRJDQH` | Audit generated C portability |
| `ses_ec76ae032ffexOsgBVCJzauguo` | Audit tight-pow test coverage |
| `ses_ec76abf27ffeRzyLrhddjXgjzy` | Audit HTTP v2/v33 measurement |
| `ses_ec76a9997ffenBzr83QqFJ76fM` | Audit cross-OS prototype evidence |

Review findings and resolution: no arithmetic or accepted-but-inequivalent matcher counterexample was found. The coverage review prompted stronger big-value ABI, live-collision, coroutine and exported-trap cases and named final logs. The matcher review’s codegraph “no tests found” result is superseded by the actual CLI test sources and executions. Nullable-expression concerns prompted defensive shape checks; normal frontend parsing supplies expression nodes. The C header review’s stdint uncertainty is resolved by the actual runtime header including <stdint.h>; Windows proof uses MinGW GCC, with no MSVC claim. GNU fallback syntax is retained. HTTP footer/clock/ratio wording was clarified without altering samples. The cross-OS review confirmed prototype counts, balanced orders and 30 row-wise target passes; old ledger counts are now explicitly historical. Compiler producer hashes can vary between Windows builds and SDK hashes between macOS runs; shared inputs are guaranteed within each comparison, not byte identity across machines/jobs.

**Actual unchanged-compiler CPU performance gates now pass.** The [local suite](bounded-modpow-generic-full-60-2026-10-14.md) and [six native jobs](bounded-modpow-native-cross-os-2026-10-14.md) use this exact clean commit without a generated-C probe. All five local and all 30 native Forge/Rust row-wise lower 95% bounds exceed 1.10. The earlier prototype remains separately labeled and preserved.

[All executed-source snapshots, validation logs, six complete child histories/final reports, routing evidence and generated C](bounded-modpow-lowering-2026-10-14.raw.tar.gz), SHA-256 `1f4c37d9c652304a0982cd78f41560673e7f00966a93433b9091ad6e21b5f461`.
