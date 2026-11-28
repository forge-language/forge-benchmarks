# Recovering long UTF-8 substring performance in generated JavaScript

The final CMake Release compiler reduced median elapsed time for 600 long-suffix calls from 153.65 ms to 103.48 ms on 65,536-byte mixed UTF-8 strings. The median paired change was −32.15% over 12 alternating pairs (interquartile range −32.82% to −31.99%). Against the original pre-substring compiler, a separate 10-pair run of the same emitted program measured −29.40% (−29.70% to −29.01%). [Final compiler](https://github.com/forge-language/forge/commit/addddb0fe2722fb804854190e9002a2c76a96142) · [Final release measurements](js-suffix-recovery-2026-11-28.raw/outlined-confirm.json.xz) · [Pre-substring comparison](js-suffix-recovery-2026-11-28.raw/outline-legacy.json.xz)

The previous substring change had increased elapsed time on this input by 4.0% (+3.6% to +4.8%) over 12 alternating pairs. In that reproduction, the long prefix and span still improved by 95.3% and 3.0%, respectively. [Previous study](js-substring-2026-11-28.md) · [Reproduction](js-suffix-recovery-2026-11-28.raw/reproduce.json.xz)

## Changes and trade-offs

The original mixed string repeats a 16-byte, 11-UTF-16-unit block 4,096 times. The final 16 bytes start at 65,520. Acquiring them still requires encoding up to the end of this 45,056-unit source. The new helper reuses a private Uint8Array for primitive strings with nonnegative BigInt arguments when the smaller of `3 × UTF-16 length` and `requested byte end + 3` is at most 196,608. Three spare bytes let a four-byte scalar crossing the requested end fit. The decoder receives exactly the bytes actually written within the requested range, including partial scalars that must raise TypeError. An ineligible capacity or missing `encodeInto` uses a fresh full encoding. The buffer starts on demand, grows geometrically when reused and retains at most 192 KiB, in addition to the existing 192-byte short buffer. The suffix fixture's first request allocates 65,539 bytes. At the intermediate V3 revision the generated program grew from 8,283 to 9,047 bytes, an increase of 764 bytes. [Prior compiler](https://github.com/forge-language/forge/commit/b9fa8dd03e5643b013072fbff150e10481e548fc) · [Intermediate V3 compiler](https://github.com/forge-language/forge/commit/64574006ce36e2e10eed4935fad247186823f3f5) · [Pre-substring compiler](https://github.com/forge-language/forge/commit/68569977a214578ca2a2c2993880958fe017a39b)

V1 passed the entire retained buffer to `encodeInto`. After a large request, slicing bytes [192, 208) took 134.00 ms per 800 calls, versus 6.92 ms with a fresh process and the same small request. V2 limited the destination view to the current request and reduced the primed case to 6.83 ms. Its numeric conversion in the out-of-bounds check cost +25.5% (+14.6% to +30.7%) over another 20 pairs. V3 kept the view limit and restored the original BigInt check. Two independent V3 runs on 160,000 out-of-bounds calls measured +2.8% (+1.0% to +9.8%) and -2.1% (-15.7% to +0.8%). The latter used a generated-code guard replacement verified byte-identical to V3. [v1-original](js-suffix-recovery-2026-11-28.raw/v1-original.json.xz) · [v1-controls](js-suffix-recovery-2026-11-28.raw/v1-controls.json.xz) · [v1-legacy](js-suffix-recovery-2026-11-28.raw/v1-legacy.json.xz) · [v2-original](js-suffix-recovery-2026-11-28.raw/v2-original.json.xz) · [v2-controls](js-suffix-recovery-2026-11-28.raw/v2-controls.json.xz) · [v2-legacy](js-suffix-recovery-2026-11-28.raw/v2-legacy.json.xz) · [v2-oob-confirm](js-suffix-recovery-2026-11-28.raw/v2-oob-confirm.json.xz) · [v2-bigint](js-suffix-recovery-2026-11-28.raw/v2-bigint.json.xz)

Exploratory edits to the generated program on CPU 4 compared three encoding options over five suffix pairs. Bounded web-standard encoder reuse took 34.1% less time, Node's `Buffer.from` took 1.0% more and a Node-specific `Buffer.byteLength` tail calculation took 69.2% less. The compiler selected the web-standard path for browser and Node output. These pilots establish suffix timings on that host. Their code and measurements are retained for replay. [pilot-scratch](js-suffix-recovery-2026-11-28.raw/pilot-scratch.json.xz) · [pilot-from](js-suffix-recovery-2026-11-28.raw/pilot-from.json.xz) · [pilot-node](js-suffix-recovery-2026-11-28.raw/pilot-node.json.xz)

## Original workloads

The columns give median milliseconds per process and median paired change with its inclusive interquartile range. Each of the eight alternating pairs used a fresh Node process for each compiler. The previous-release binary re-emitted the published v4 program byte for byte. [v3-original](js-suffix-recovery-2026-11-28.raw/v3-original.json.xz)

| Original case | Previous ms | V3 ms | Paired change | IQR |
| --- | ---: | ---: | ---: | ---: |
| repository | 23.03 | 23.78 | +4.1% | +3.3% to +5.7% |
| short_ascii | 5.19 | 5.02 | -2.1% | -8.2% to +4.9% |
| short_utf8 | 21.40 | 21.15 | -0.9% | -2.5% to +0.6% |
| short_late_utf8 | 19.73 | 20.44 | +3.6% | +1.1% to +6.6% |
| long_prefix | 6.93 | 7.27 | +3.2% | -1.8% to +7.3% |
| long_ascii_prefix | 5.67 | 2.65 | -35.4% | -55.3% to -3.1% |
| long_suffix | 148.53 | 101.13 | -32.0% | -32.2% to -31.8% |
| long_span | 86.62 | 65.15 | -24.9% | -25.2% to -24.6% |
| long_ascii_span | 50.70 | 36.78 | -27.7% | -27.8% to -27.1% |
| empty | 1.14 | 1.11 | -3.1% | -14.5% to -0.0% |
| out_of_bounds | 1.39 | 1.44 | +2.8% | -1.9% to +8.3% |
| ffi_numbers | 33.61 | 34.05 | -0.1% | -1.5% to +1.5% |

## Guard and input controls

The distinct case preconstructs 384 different flat 65,536-byte strings. Two 64-call warmups and the following 256 measured calls access disjoint strings. All sources end with their own 16-byte tag. The bridge checks the timed checksum and hashes the complete result vector after timing. Early slices cover bytes [192, 208) of the mixed source. The primed case first requests a capacity of 196,608 bytes. `small_190` requests [174, 190) on a 256-byte ASCII source. The two cap probes request 16 bytes on a 196,608-byte ASCII string, with exclusive ends 196,605 and 196,606. The over-cap suffix reads the last 16 bytes of a 262,144-byte mixed string. Fallback and hot controls disable `encodeInto`, start beyond the maximum possible source byte length, or normalize package URLs. The new runner generates these inputs and verifies completed output against Python UTF-8 byte slicing with strict decoding. [Runner](../../benchmark/compiler/js_suffix_controls.py) · [Node bridge](../../benchmark/compiler/js_suffix_controls.cjs) · [v3-controls](js-suffix-recovery-2026-11-28.raw/v3-controls.json.xz)

| Additional case | Previous ms | V3 ms | Paired change | IQR |
| --- | ---: | ---: | ---: | ---: |
| distinct_suffix | 59.42 | 40.28 | -32.1% | -32.8% to -31.6% |
| early | 197.72 | 6.89 | -96.6% | -97.1% to -96.4% |
| early_after_large | 199.69 | 6.41 | -96.7% | -97.5% to -96.4% |
| small_190 | 54.04 | 21.27 | -60.5% | -61.0% to -60.1% |
| cap_fit | 131.84 | 91.02 | -31.0% | -31.3% to -30.8% |
| cap_miss | 132.06 | 132.80 | +0.3% | -0.8% to +1.6% |
| over_cap_suffix | 172.93 | 172.57 | -0.2% | -1.2% to -0.0% |
| no_encode_into | 148.00 | 149.86 | +1.5% | +0.7% to +1.9% |
| out_of_bounds_hot | 5.21 | 5.31 | +2.8% | +1.0% to +9.8% |
| repository_hot | 100.50 | 102.15 | +1.4% | -1.7% to +2.8% |

## Interaction with string length

The subsequent compiler also uses the buffer for bounded string lengths. Against the previous release its suffix change was -32.0% (-32.6% to -31.5%). Against the pre-substring release it was -29.7% (-29.9% to -29.2%). Longer runs of the original application, short late-Unicode and prefix inputs used 192,000 calls for each short workload and 12,000 for each long prefix. Absolute prefix times varied substantially across processes. All four retained their gains over the pre-substring release. [Length study](js-length-recovery-2026-11-28.md) · [Combined compiler](https://github.com/forge-language/forge/commit/a5e1d9a592395f9285aed0092242b3d889016f8b) · [len-original](js-suffix-recovery-2026-11-28.raw/len-original.json.xz) · [len-legacy](js-suffix-recovery-2026-11-28.raw/len-legacy.json.xz) · [len-hot](js-suffix-recovery-2026-11-28.raw/len-hot.json.xz) · [len-legacy-hot](js-suffix-recovery-2026-11-28.raw/len-legacy-hot.json.xz)

| Longer workload | Previous ms | Combined ms | Paired change | IQR |
| --- | ---: | ---: | ---: | ---: |
| repository | 105.89 | 107.10 | +2.2% | +0.2% to +3.4% |
| short_late_utf8 | 65.85 | 68.60 | +4.4% | +3.6% to +5.0% |
| long_prefix | 12.62 | 14.17 | +10.6% | +1.8% to +25.4% |
| long_ascii_prefix | 8.35 | 8.88 | +7.9% | -52.5% to +37.1% |

## Short-input follow-up

Moving the long primitive and foreign-argument dispatch into a separate function reduced elapsed time for the warmed late-Unicode workload by -7.3% (-9.3% to -3.9%) relative to the combined compiler. The same direct comparison measured +0.6% (-1.5% to +1.9%) on repository URLs. The direct 10-pair suffix check measured +0.7% (+0.2% to +1.5%). A fresh comparison against the previous release measured -31.7% (-32.3% to -31.3%) for suffixes, +0.5% (-1.9% to +2.2%) for short late-Unicode strings and +5.1% (-0.6% to +5.7%) for foreign numbers. Against the pre-substring release the outlined suffix measured -29.4% (-29.7% to -29.0%). The previous and outlined programs both passed the cap, high-water and unique-input oracle. The archive includes the patch against the combined compiler and its emitted program. [outline-direct](js-suffix-recovery-2026-11-28.raw/outline-direct.json.xz) · [outline-guard](js-suffix-recovery-2026-11-28.raw/outline-guard.json.xz) · [outline-original](js-suffix-recovery-2026-11-28.raw/outline-original.json.xz) · [outline-hot](js-suffix-recovery-2026-11-28.raw/outline-hot.json.xz) · [outline-controls](js-suffix-recovery-2026-11-28.raw/outline-controls.json.xz) · [outline-legacy](js-suffix-recovery-2026-11-28.raw/outline-legacy.json.xz)

The final CMake Release build emitted the same outlined program byte for byte. Independent Node tests passed on the Release compiler, including partial four-byte scalars, BOM, stale storage after reuse and fallback without `encodeInto`. Two negative controls verified that dropping one spare byte or reading unwritten bytes makes the boundary test fail. [Final emitter](https://github.com/forge-language/forge/commit/addddb0fe2722fb804854190e9002a2c76a96142) · [Boundary regression](https://github.com/forge-language/forge/blob/addddb0fe2722fb804854190e9002a2c76a96142/tests/js_test.py#L23) · [Workspace proof](https://github.com/forge-language/forge/commit/ad2ec57fbc72f9a1a55b8dee9659d046d058a254)

In the final 12-pair comparison, short late-Unicode inputs measured -1.0% (-2.3% to +1.0%) and the 24,000-call repository workload measured -15.4% (-17.9% to -11.7%). Two additional generated-code trials on CPU 6 were rejected. Slicing the source before encoding raised warmed mixed-prefix time +28.6% (+15.6% to +62.6%) versus the previous release. Locating the first non-ASCII unit reduced late-Unicode time -63.6% (-63.9% to -62.2%) versus the combined compiler but raised repository time +3.4% (+1.1% to +5.2%). The replay archive includes each generated program, SHA-256 manifest and warmup adapter. [outlined-confirm](js-suffix-recovery-2026-11-28.raw/outlined-confirm.json.xz) · [cutprefix](js-suffix-recovery-2026-11-28.raw/cutprefix.json.xz) · [ascii-bound](js-suffix-recovery-2026-11-28.raw/ascii-bound.json.xz) · [Related byte-index trade-off](js-index-churn-2026-11-28.md)

## Reproduction

All primary measurements ran sequentially on logical CPU 14 of an Intel Core i5-13400F with Node v24.15.0. Each process performed two quarter-length warmups before timing the Forge-emitted callback. Program generation, Node startup, construction of fixture inputs and hashing fall outside the interval. Individual samples record nanoseconds, chronological order and validated checksums. The original runner also hashes every input's output before warming. The additional controls hash outputs after measurement so a distinct string first reaches the callback during its measured iteration. The extended original-case adapter in the replay archive only changes iteration counts.

The compiler used GCC 15.2.0, CMake 4.2.3, Release `-O3 -DNDEBUG` with LTO disabled, runtime `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and stdlib `6aa28667b83009a415ab2d7ac13ef6c675af7012`. The archive includes compiler, emitter and emitted-program SHA-256 values in `builds.json`, generated JS for each revision, and standalone V1–V3 patches against the previous release. The length patch applies after V3. The pre-substring and previous-release programs also match the original published archive. Run from the benchmark repository on a CPU in the process affinity mask. [Replay archive](js-suffix-recovery-2026-11-28.raw/replay.tar.xz)

```sh
work=$(mktemp -d)
tar -xJf docs/compiler/js-suffix-recovery-2026-11-28.raw/replay.tar.xz -C "$work"
(cd "$work" && sha256sum -c SHA256SUMS)
python3 -B benchmark/compiler/js_substring_bench.py --emitted \
  --baseline "$work/before.js" --candidate "$work/v3.js" \
  --cpu 14 --pairs 8 --output "$work/original.json"
python3 -B benchmark/compiler/js_suffix_controls.py \
  --baseline "$work/before.js" --candidate "$work/v3.js" \
  --cpu 14 --pairs 8 --output "$work/guards.json"
PYTHONPATH=benchmark/compiler python3 -B "$work/hot.py" --emitted \
  --baseline "$work/before.js" --candidate "$work/len.js" \
  --cpu 14 --pairs 12 --output "$work/hot.json"
```
