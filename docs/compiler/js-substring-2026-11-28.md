# UTF-8 substring operations in Forge-generated JavaScript

Normalizing 24,000 repository URLs took a median 54.49 ms with the baseline compiler and 24.04 ms with the selected compiler (v4). The median paired reduction was 56.2% across eight pairs on Node v24.15.0. For a 64 KiB mixed UTF-8 string, a 12-byte prefix took 95.0% less time and a provably out-of-bounds slice took 99.2% less time. Reading the last 16 bytes took 3.0% longer.

## Workloads

The Forge fixture adapts the package manager’s `canonical_repo`. It lowercases the URL, takes its UTF-8 byte length, reads its last four bytes, and strips a matching `.git` suffix. The host’s lowercase function and Forge’s string equality implement the same operations as the platform’s JavaScript bridge. The 32 inputs combine ASCII and accented paths with `.git`, `.GIT`, a missing suffix and `.gitx`. The timing covers the complete normalization function in isolation from package installation, network requests and Git. [Platform function](https://github.com/forge-language/forge-platform/blob/4a3982709bf02a73704cf68de019e0f023a224f0/cli/src/manager.fg#L81-L84) · [Platform bridge](https://github.com/forge-language/forge-platform/blob/4a3982709bf02a73704cf68de019e0f023a224f0/workers/src/web.ts#L69-L70) · [Forge fixture](../../benchmark/compiler/js_substring.fg)

The short ASCII case varies the offset across package paths. The short UTF-8 slice includes two-, three- and four-byte scalars and NUL. A second short string ends in a multibyte character outside the requested prefix. The long cases cycle over 16 strings of 65,536 UTF-8 bytes. Prefixes take 12 bytes, the suffix takes the last 16, and spans take 57,344 bytes starting at 1,024. The empty control asks for zero bytes starting at four and the out-of-bounds control starts at 1,048,576. A JavaScript number supplied as the string argument exercises host coercion. All inputs are prepared before the timer and reused across warmup and measurement. [Inputs and Python oracle](../../benchmark/compiler/js_substring_bench.py) · [Timing bridge](../../benchmark/compiler/js_substring.cjs)

## Compiler changes

The baseline encodes the source, copies the requested byte slice and constructs a fatal UTF-8 decoder for each call. The first trial (v1) uses a view of the fresh encoding and reuses a private fatal decoder. The second (v2) adds direct JavaScript slicing for primitive ASCII strings of at most 64 UTF-16 units when both indices are BigInts. The third (v3) also handles zero-length requests directly for primitive strings with nonnegative BigInt arguments. It uses the existing 192-byte encoding buffer for other short strings and for requests ending within the first 189 bytes of a longer string. Beyond those bounds, it still encodes the full string. The fourth (v4) adds an out-of-bounds check on the remaining primitive-string path. Three times the UTF-16 length is an upper bound on its UTF-8 byte length, so a larger or equal starting offset yields an empty string. The source patches in the replay archive all apply directly to the baseline. [Baseline compiler](https://github.com/forge-language/forge/commit/68569977a214578ca2a2c2993880958fe017a39b) · [Selected compiler](https://github.com/forge-language/forge/commit/fe71d767842e73d12d15cbab2df43b0abe4a0bcc) · [Patches and generated programs](js-substring-2026-11-28.raw/replay.tar.xz)

## Results

Each stage used a fresh baseline comparison. The first used four alternating pairs per workload. The later trials each used eight. The percentage is the median of `100 × (candidate_ns / baseline_ns − 1)` over those pairs. Each millisecond column is a separate median for the fourth comparison. The final column gives its inclusive 25th and 75th percentiles. [v1 raw timings](js-substring-2026-11-28.raw/v1.json.xz) · [v2 raw timings](js-substring-2026-11-28.raw/v2.json.xz) · [v3 raw timings](js-substring-2026-11-28.raw/v3.json.xz) · [v4 raw timings](js-substring-2026-11-28.raw/v4.json.xz)

| Workload | v1 paired | v2 paired | v3 paired | Baseline ms | v4 ms | v4 paired | Paired IQR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| repository | -9.1% | -35.5% | -63.9% | 54.489 | 24.035 | -56.2% | -56.9% to -55.6% |
| short_ascii | -11.1% | -88.3% | -89.1% | 49.073 | 4.944 | -89.9% | -90.3% to -89.6% |
| short_utf8 | -8.0% | -2.3% | -63.8% | 57.455 | 21.507 | -62.5% | -62.7% to -62.1% |
| short_late_utf8 | -9.3% | +4.1% | -62.9% | 51.563 | 19.723 | -62.0% | -62.3% to -61.2% |
| long_prefix | +2.1% | +3.3% | -95.2% | 145.007 | 7.291 | -95.0% | -96.0% to -94.7% |
| long_ascii_prefix | -1.9% | -1.8% | -96.2% | 128.471 | 4.569 | -96.4% | -97.6% to -95.3% |
| long_suffix | +2.4% | +3.0% | +2.7% | 147.559 | 150.748 | +3.0% | +2.0% to +3.5% |
| long_span | -2.0% | -2.4% | -2.7% | 89.424 | 87.886 | -2.3% | -2.8% to -0.8% |
| long_ascii_span | -10.9% | -8.1% | -8.7% | 56.083 | 52.292 | -6.7% | -7.5% to -4.9% |
| empty | +8.7% | +7.5% | -99.4% | 161.176 | 1.102 | -99.3% | -99.5% to -99.2% |
| out_of_bounds | +8.1% | +7.3% | +5.4% | 161.865 | 1.224 | -99.2% | -99.4% to -99.0% |
| ffi_numbers | -13.1% | -12.0% | -12.6% | 39.352 | 34.905 | -12.6% | -14.6% to -9.2% |

The selected v4 avoids encoding and allocating in proportion to source size for a provably impossible starting offset. The earlier v3 was faster on the repository workload. A direct comparison ran the two back to back for eight alternating pairs. Relative to v3, v4 took 11.3% longer for repository normalization (IQR +1.5% to +21.0%), 0.04% longer for long suffixes (−0.9% to +0.7%), and 99.0% less time for out-of-bounds slices (−99.1% to −99.0%). [Direct comparison](js-substring-2026-11-28.raw/v3-v4.json.xz)

## Measurement and replay

Each sample ran the compiler’s actual output in a fresh Node process on logical CPU 14 of an Intel Core i5-13400F. The bridge called each generated callback with every input and hashed its complete output vector. Python independently checked that digest using byte slices and strict UTF-8 decoding. After two warmups at one quarter of the iteration count, Node timed the callback loop and accumulated UTF-16 lengths and the first and last code units of every result. Python checked the sum for each timed execution. Startup, compilation, input parsing and digest verification fell outside the timed interval. The raw files record chronological pair order, nanoseconds, iteration counts, result and configuration digests, host versions, and SHA-256 hashes for the input files, Node, compilers and emitted programs.

The compilers used GCC 15.2.0, CMake Release, `-O3 -DNDEBUG`, LTO disabled. The SDK used runtime `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and stdlib `6aa28667b83009a415ab2d7ac13ef6c675af7012`. Run these commands from the benchmark repository. Choose a CPU in your process’s allowed affinity mask.

```bash
work=$(mktemp -d)
tar -xJf docs/compiler/js-substring-2026-11-28.raw/replay.tar.xz -C "$work"
(cd "$work" && sha256sum -c SHA256SUMS)
python3 -B benchmark/compiler/js_substring_bench.py --emitted \
  --baseline "$work/baseline.js" --candidate "$work/v4.js" \
  --cpu 14 --pairs 8 --output "$work/replay.json"
```

Substitute v1, v2 or v3 to replay earlier programs. To rebuild a trial, start with the baseline Forge checkout above, apply its archived patch with `patch -p1`, and build the Release compiler. Pass the baseline and rebuilt compiler paths to the same runner, replace `--emitted` with `--root PATH_TO_SDK`, and compare the resulting `emitted_sha256` with the raw file. Use `--case repository` to select the application workload alone.
