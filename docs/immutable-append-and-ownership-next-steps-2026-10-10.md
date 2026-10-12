# Immutable append and ownership: next implementation gates

The Rust 110% throughput objective remains open. Checked view and builder-byte
inlining improved supported native string paths, but the immutable-append row
still runs at approximately 23% of Rust throughput on this host. Scheduler-oriented
coroutine cases exceed 1.10 under their supported scheduling policies; mixed CPU
coroutines do not establish that target. Neither result proves a language-wide
performance guarantee, and the available measurements do not justify declaring
further improvement impossible.

## What the implementation actually does

At stdlib checkpoint `bd89481`, `src/string.c:190–197` implements
`fr_str_append` by calling `strlen`, allocating a fresh arena string, copying its
entire previous prefix, and writing the appended byte and NUL terminator.
`fr_str_append_str` delegates to concatenation, which likewise measures and
copies its inputs. These are immutable snapshots: existing strings and borrowed
views must continue to observe their earlier contents.

Runtime `ddeba40`, `src/arena.c:66–106`, allocates monotonically within blocks.
Individual strings are not reclaimed. Reset rewinds block positions and retains
blocks for reuse; allocations remain valid until reset or destruction. The
thread arena starts with a 4 MiB block, and a coroutine can use its own arena.
Thus changing a local string binding does not reclaim its preceding snapshot.

Building a length-n string with repeated immutable byte append performs n
logical arena allocations (underlying block mallocs are a separate count). Each
of the length scans and prefix copies processes approximately n(n−1)/2 prefix
bytes.
Live arena storage accumulated before reset is also O(n²), even when source
bindings stop referring to old strings. At n=4,096, one benchmark round copies
8,386,560 prefix bytes, just under 8 MiB; 512 rounds copy just under 4 GiB.
Reset allows arena-block reuse between rounds, so the retained process memory
is not the sum over all 512 rounds.

The Rust fixture deliberately also creates a fresh string and copies the prefix
on every append. It drops the preceding owned buffer immediately, however,
keeping live prefix storage O(n) and allowing allocator/cache reuse. Both
algorithms are O(n²) in bytes copied; their allocation lifetime and cache
footprints differ. The throughput gap is measured, but its precise division
between repeated length scans, allocation bookkeeping, copies and cache effects
has not been profiled. Whole-process `wait4` RSS, including possible pre-exec
runner footprint, is not sufficient evidence for that attribution.

Source references: [stdlib string implementation](https://github.com/forge-language/forge-stdlib/blob/bd89481e5b9afd1ac05ce7daf938e3060ce8ca40/src/string.c),
[runtime arena implementation](https://github.com/forge-language/forge-runtime/blob/ddeba40e8c57b4e8bc46f273c519a4c497fe2a56/src/arena.c).
Measurement references: [paired builder optimization](builder-byte-inline-2026-10-10.md),
[coroutine policies and lifecycle](coroutine-rust-forge-2026-10-10.md).

## Gate 1: profile before selecting another optimization

Use the same correctness-checked immutable fixture and immutable SDK snapshot.
Collect requested arena bytes, live block capacity, allocation count and reset
count for several lengths, alongside CPU profiles of `strlen`, `memcpy`, arena
allocation and generated code. Compare both the ordinary immutable path and the
explicit builder path. Preserve all profiles, source/flags, dimensions and
independent result checks. Instrumented profiling results must remain separate
from ordinary paired throughput measurements.

Read-only inspection on this host found `/usr/bin/perf`, no `valgrind` on PATH,
`perf_event_paranoid=4`, `kptr_restrict=1`, and no effective `CAP_PERFMON` or
`CAP_SYS_ADMIN` for UID 1000. These settings restrict profiling access; an actual
hardware-event permission probe has not been run while other builds are active.
No kernel settings were changed. Check event access in an agreed idle window
before promising hardware counters. If unavailable, use a permitted dedicated
runner, software sampling, or a separately instrumented diagnostic build.
Function/arena counters can establish allocation behavior without claiming
hardware cache measurements.

Acceptance requires a reproducible bottleneck attribution and an ordinary,
non-instrumented paired improvement with unchanged outputs. Report O(n²) copying
as O(n²) even if constant factors improve.

## Gate 2: a separate cached-length immutable API

Design an explicit operation conceptually equivalent to
`snapshot_append_byte(view, byte) -> new_view`, plus access to the resulting
immutable bytes. A trusted live view supplies its cached length, avoiding another
`strlen`. The operation still allocates a new snapshot and copies the prefix;
old strings and views remain unchanged. No hidden in-place change to legacy
`str_append` is authorized.

The implemented API's contract covers invalid/zero handles, full `int64_t`
input narrowing according to the target's legacy append behavior, visible NUL
handling, overflow, allocation failure, backend-specific UTF-8 behavior,
source/arena lifetime, and returned-view validity. Legacy
`fr_str_append` remains unchanged. Constructing a new view by scanning the
returned string after every append would defeat the cached-length objective,
so the implementation carries the known length. Direct C tests cover snapshots
and byte boundaries; JS tests cover UTF-8 encoding and NUL visibility.

Keep existing exported C symbols and raw string ABI. Do not expose arbitrary
caller-supplied lengths as a safe API or claim stale integer handles become safe.
Regression gates include aliases, earlier views and snapshots, empty/null
sources, boundary lengths, byte/NUL/UTF-8 cases, reset invalidation and explicit
allocation-failure signaling. Metadata and snapshot share one allocation to
avoid doubling per-append arena allocations. This remains an O(n²) snapshot
operation; the measured benefit is a constant-factor change.

## Gate 3: true owned heap values and typed cleanup

Current ownership checking is a binding initialization/move restriction, not
proof that a string buffer is uniquely owned. `compiler/semantic.c` tracks
`initialized` and `owned`, while ordinary string assignments can alias the same
bytes. `compiler/codegen.c` clones a string into heap storage before owned send,
then clears the source binding. That protects literal/arena-backed strings from
being passed directly to a consuming heap API, but does not establish general
borrow checking, object uniqueness or automatic destruction.

Introduce a reviewed, explicit owned heap-string value with buffer, length and
capacity, distinguished from arena/literal strings and borrowed views. The
existing `owned` spelling alone cannot be treated as proof of this new storage
contract. Preserve existing raw C ABI through deliberate conversion/borrowing
boundaries. Unknown FFI calls require conservative escape handling or explicit
unsafe contracts.

Before capacity reuse, require all of these implementation gates:

- CFG-aware move and alias/borrow analysis across branches, loops, returns,
  nested scopes, closures and coroutine captures. Track allocation provenance,
  owner identity and live borrows; a valid binding is not enough.
- Deterministic drops on scope exit, reassignment, return, break and continue,
  including any exceptional/cancellation paths. Returning ownership transfers
  the value instead of dropping it locally.
- Moved bindings can be reinitialized safely. Cleanup tracks which fields are
  live so that reinitialization, early exits and destruction neither leak nor
  double-free.
- Coroutine state has typed cleanup callbacks for live heap fields, including
  completed tasks, cancellation, errors and process destruction. The current
  generic `free(state)`/arena destruction does not encode those typed drops.
- Borrowed bytes cannot outlive their owner or an arena reset. Shared aliases
  require immutable sharing or cloning; cross-process sharing and FFI ownership
  transfer need explicit lifetime/threading contracts.
- Direct send transfer is permitted only for proven compatible, uniquely owned
  heap storage. Literal, arena-backed or shared strings retain the appropriate
  clone/conversion path.

Only then can an unborrowed, uniquely owned buffer append in place or grow
geometrically without altering earlier observable values. Snapshot/freeze
operations must preserve their immutable contract, using copies or reviewed
sharing semantics. Safe typed vectors and other resource-owning values should
reuse the same lifetime/drop machinery rather than reconstructing integer
addresses.

## Gate 4: narrow compiler lowering after ownership is proven

A dead-temporary chain such as `text = str_append(text, byte)` might eventually
lower to a builder/owned-buffer path when analysis proves there are no aliases,
views, pointer observations, captures or escaping FFI calls. The result must
retain byte/NUL semantics, observable snapshots, error signaling and backend
behavior. Changing the overwritten terminator of a legacy aliased string would
change what older aliases observe and is therefore invalid.

Require positive and negative compiler tests for aliasing, borrows, shadowing,
branch joins, moved reinitialization, loop exits, returns, yields/cancellation,
unknown extern calls and injected allocation failures. Run semantic tests under
sanitizers and backend parity checks. Preserve the old slow path whenever proof
is unavailable. Benchmark both optimized and intentionally aliased workloads;
never remove an alias to manufacture a speedup.

The cached-length API proposed here is now implemented additively as
`str_view_append_byte(view, value)`. Native code puts the new view metadata and
immutable string snapshot in one arena allocation, carries the resulting
length, and leaves the legacy `str_append` symbol and snapshots untouched. The
JavaScript implementation follows its existing `String.fromCharCode` append
behavior and stores the result as a UTF-8 byte view. This API is not yet used by
an automatic compiler rewrite, and no ownership representation was added.

## Compiler/backend audit: current lowering is not safe

The current compiler has no string ownership or alias proof for this
transformation. `compiler/optimize.c` folds arithmetic expressions but does not
rewrite statement-level string loops. `compiler/semantic.c` tracks whether a
local is initialized and whether an explicit owned binding was moved; it does
not track string aliases, live views, or escaping references. Code generation
maps `str_append` directly to the legacy runtime symbol.

The existing builder API is not a drop-in replacement. Native
`fr_str_append` narrows an arbitrary integer to `char`, including zero, while
`fr_str_builder_char` accepts only bytes 1 through 255. The JavaScript backend
implements append with `String.fromCharCode`, whereas builder bytes are decoded
as UTF-8. The new view append API preserves each backend's legacy append
behavior; bytes above ASCII therefore do not have identical native and JS
representations, matching the existing `str_append` boundary. A source-level
builder rewrite still needs to prove its byte range and preserve previous
snapshots and failure behavior, and cannot cross an arena reset or an unknown
call that may observe the current string.

The existing immutable fixture uses only ASCII bytes, so it does not cover
these semantic boundaries. Before compiler lowering, prove the binding is a
dead-temporary chain with no aliases, views, captures, resets, or unknown
escaping calls. Preserve the legacy path whenever any proof is missing.
Required negative tests include aliased prior snapshots, NUL and out-of-range
byte values, backend-specific UTF-8 behavior, allocation failure, and
reset/coroutine boundaries. The first API benchmark shows a constant-factor
improvement but leaves the Rust 1.10 target open; see the [paired results](immutable-view-append-2026-10-12.md).
