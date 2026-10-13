# OMO cross-OS read-only review

Session `ses_ecd609fc8ffeI1vKfscyOePybj`, Sisyphus-Junior. The audit inspected the compiler driver/CMake and runtime CMake, not the benchmark harness. It is not a portability or correctness certification.

The cross-OS runner uses --emit-c followed by its own explicit C compile/link commands, so driver.c automatic LTO policy does not determine the measured flags. Both Forge binaries get identical SDK archives and native tuning, C -O3/-flto and one Rust thin-LTO control. On ARM64 Apple Clang the runner uses -mcpu=native; the review recommendation of -march=native for Apple Clang applies to x86, not this ARM64 target. Unpinned scheduling, timer checks and independent reference checks are documented by the runner itself. Windows broader arithmetic/diagnostics tests remain incomplete; native CPU checks and temp-file regressions cover their stated scopes only. The worker's "no go" suggestion is a review opinion, not an approval requirement; authorized measurements continue and failures remain in the report.

## Original worker response

**Concrete blockers**

- `compiler/driver.c:75-79` + `:148` vs `:185-229`: `-flto` is injected only into the compile step (`compile_c_source`), never into `link_object`, and is wrapped in `#if !defined(FORGE_OS_WINDOWS)` so MinGW never gets it. Fix: emit the same LTO flag at link on all three OSes (gate on a compiler probe, not `#if OS`), or drop `-flto` everywhere. Risk: link failure or silent LTO loss when `FORGE_ENABLE_LTO` is set.
- Harness code is outside the authorized scope: none of `forge/CMakeLists.txt`, `compiler/driver.c`, `forge-runtime/CMakeLists.txt` contain a timer, Rust FFI, affinity API, `__int128`, or the Python driver. Those live under `../forge-benchmarks/benchmark/` (path confirmed by listing only, not read). Hazards (a),(b),(c),(d),(f),(g),(i) are UNVERIFIED — no go for the 3-OS run until they are audited.
- `forge/CMakeLists.txt:146-151` skips ownership/arithmetic/diagnostics/org_integration on non-UNIX; `forge-runtime/CMakeLists.txt:49-54` limits scheduler (UNIX) and event_loop (Linux). Fix: run at least arithmetic+diagnostics under MSYS2 or accept unverified Windows correctness.

**Fairness risks**

- LTO coverage diverges: `forge/CMakeLists.txt:11-19` gates IPO behind `FORGE_ENABLE_LTO` (default OFF, applies to `forge` only); `forge-runtime/CMakeLists.txt` has no LTO option; `driver.c:76` hard-excludes Windows. Fix: one explicit flag set, all targets, all OSes.
- Hardcoded `-O3` at `driver.c:71,147` and `CMakeLists.txt:87,107` (stage2/3) vs `CMAKE_BUILD_TYPE`-driven flags elsewhere (`CMakeLists.txt:8-10`). Fix: force `-DCMAKE_BUILD_TYPE=Release` and record `CMAKE_C_FLAGS`.
- No `-march/-mtune/-mcpu` anywhere in scope → default baselines differ per toolchain; acceptable only under a single stated policy.

**Recommended flags**

- Linux/MinGW GCC: C `-O3 -flto -DNDEBUG`; Rust `-C opt-level=3 -C lto=thin -C codegen-units=1`. Apple Clang: C `-O3 -flto`, Rust thin LTO.
- CPU tuning: either `-march=native -mtune=native` (GCC) + `-march=native` (Apple Clang) + Rust `-C target-cpu=native` on **all three**, or baseline ISA on all three — never native on one OS only.
- Windows: C `-static-libgcc` and Rust `-C target-feature=+crt-static`, matched both-or-neither (target `x86_64-pc-windows-gnu`).
- Not to use: MSVC `/GL /LTCG` (MinGW target), `-Ofast`/`-ffast-math`, empty build type, `lto=fat` on one side and `thin` on the other, or cross-language C↔Rust LTO — unsupported; LTO stays intra-language, the binaries meet only at the `extern "C"` boundary.

**Non-issues checked and cleared**

- `driver.c:15-22,100-102,220-224,283-301`: Windows/POSIX branches present (`_spawnvp`, `-lws2_32`, `GetModuleFileNameA`); `access(X_OK)` gated at `:232-253`.
- No `__int128`/`__uint128_t`; no affinity API in scope; archives MinGW-compatible (`driver.c:192-218`).
- `MSVC` branches (`CMakeLists.txt:20-24`, `:134-138`; runtime `:30-34`) inert under MinGW GCC; C11+`CMAKE_C_EXTENSIONS OFF` consistent (`CMakeLists.txt:5-7`, runtime `:5-7`).
- SDK assembly shared by both versions via one path (`CMakeLists.txt:32-44`).

No cross-OS performance claim may be made from Linux-only data; the timer, affinity, and run-order logic remain unaudited.
