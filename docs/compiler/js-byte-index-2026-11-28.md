# Byte indexing in Forge-generated JavaScript

The fixture includes the unmodified `valid_digest` function from `forge-platform/vendor/forge-storage/storage.fg`, lines 7–12 at checkout `4a3982709bf02a73704cf68de019e0f023a224f0`. The original file had SHA-256 `62eedd4712af46b218a1a180dab6016c1176710804a6a3939ec000533b92a302`. The six lines in both files had SHA-256 `625669a0763a118ba9ca2bcad01787ff93d144b3d02080519e65c76006680080`. It tests for 64 UTF-8 bytes containing only lower-case hexadecimal digits. The fixtures exercise the validator in isolation from the storage service.

The short ASCII scan uses 64 digits. The short mixed scan repeats `aé界😀`, NUL and `z` four times. The 4096-byte scan repeats `a界😀` 512 times. The two 128 KiB probes read byte 0 or 130 of a single long ASCII prefix ending in `é`. The explicit view case creates a view for each scan, reads every byte with `str_view_at`, then resets the arena. Distinct inputs are prepared before the timing interval. For the distinct cases each measured read receives a different string from all previous calls in that process, including warmups. The common-prefix case shares 3756 initial bytes across all its strings.

## Measurement

CMake Release used GCC 15.2.0 with `-O3 -DNDEBUG` and LTO disabled. The SDK used runtime `dcbb1929b17c2f1d11fd367ecf80c7c87c58a274` and stdlib `6aa28667b83009a415ab2d7ac13ef6c675af7012`. Both compilers emitted the same Forge fixture to JavaScript. Each sample ran in a fresh Node v24.15.0 process pinned to logical CPU 14 on an Intel Core i5-13400F. Two calls with one quarter of the measured iteration count warmed the callback loop. The clock covered the loop, including callback dispatch and checksum addition. For the four stream cases the generated Forge loop fetched each input through an FFI callback, so a single loop saw the entire sequence. The other cases invoked a Forge callback once per input from a JavaScript loop. Compilation, process startup, JSON parsing and output verification happened outside the timer.

The emitter files archived for the baseline, prefix trial and selected compiler match these commits byte for byte. [Baseline ee88fa8f](https://github.com/forge-language/forge/commit/ee88fa8f262c70e81ede274c096a07ae0097dc3c) · [Prefix f95aaabe](https://github.com/forge-language/forge/commit/f95aaabe46f9dff8d63e0c9622fdbe4d4579983a) · [Selected 68569977](https://github.com/forge-language/forge/commit/68569977a214578ca2a2c2993880958fe017a39b)

Python checked each sum using its UTF-8 encoder and a full-match hexadecimal regular expression. The raw observations retain the checksum, time in nanoseconds, chronological AB/BA order, input hashes, compiler and emitted-program hashes for every workload. A percentage is the median of eight paired differences in elapsed time, computed as `100 × (candidate / baseline − 1)`. Millisecond columns are separate medians. The lower and upper quartiles summarize within-case variation.

## Results

The prefix trial used a shared 192-byte UTF-8 scratch array for short strings and the first 189 byte positions of larger strings. At later positions it encoded the whole string. The loop trial retained one encoding per outermost indexed Forge loop after a late access to a string of 65 through 65536 UTF-16 units. Its first version created an empty object, so a JavaScript host’s inherited `text` or `data` properties could affect the cache. The selected compiler initializes both as own properties. [Prefix measurements](js-byte-index-2026-11-28.raw/prefix.json.xz) · [Initial loop measurements](js-byte-index-2026-11-28.raw/loop.json.xz) · [Selected compiler measurements](js-byte-index-2026-11-28.raw/final.json)

At most one encoded payload of 192 KiB is retained per eligible active loop, using the UTF-8 upper bound of three bytes per UTF-16 unit. The cache also holds its input string until replacement or loop exit. An engine may represent a slice using a larger backing string, so the total storage kept alive by that reference can exceed the payload bound. A refresh can temporarily hold the previous and new encodings.

The prefix trial’s original 3000-call early-return controls had wide variation. Its table values for short, Unicode 65-byte and early mismatch use an enlarged repeat with the same binaries. Each trial used a fresh paired baseline. Both millisecond columns and the IQR below describe the selected compiler comparison. An archive smoke check briefly shared the timing CPU during an earlier run of the selected compiler. Its measurements are preserved separately. The reported run began after that check finished. [Extended prefix controls](js-byte-index-2026-11-28.raw/prefix-controls.json.xz) · [Overlapping diagnostic run](js-byte-index-2026-11-28.raw/final-overlap.json.xz)

The selected compiler reduced elapsed time by 75.8% for valid digests, 99.1% for full 4096-byte `str_char_at` scans, and 98.2% for bracket scans. In a single Forge loop, the two shared-prefix streams changed the string on every iteration. The paired differences were +5.3% for distinct values and +2.9% for alternating values. The over-limit loop repeatedly read byte 65000 of a 65537-unit string (+0.5%).

| Workload | Prefix paired | First loop paired | Baseline ms | Selected ms | Selected paired | Selected paired IQR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `digest_valid` | -77.5% | -77.4% | 137.55 | 33.55 | -75.8% | -77.2% to -75.4% |
| `digest_late_bad` | -73.8% | -75.3% | 123.78 | 27.99 | -76.7% | -77.3% to -75.4% |
| `digest_early_bad` | -70.9% | -67.6% | 38.50 | 13.00 | -66.1% | -66.6% to -65.6% |
| `digest_short` | +0.7% | -0.8% | 16.88 | 17.00 | +0.4% | -0.4% to +1.9% |
| `digest_unicode_64_bytes` | -74.9% | -77.1% | 105.17 | 26.92 | -74.6% | -75.3% to -74.1% |
| `digest_unicode_65_bytes` | +0.3% | -0.4% | 17.65 | 18.20 | +0.9% | -0.6% to +2.6% |
| `chars_ascii` | -75.7% | -74.1% | 102.97 | 26.04 | -74.3% | -75.5% to -67.3% |
| `chars_unicode` | -68.4% | -67.8% | 87.16 | 28.67 | -66.5% | -68.1% to -65.3% |
| `chars_4k` | -4.0% | -98.2% | 452.66 | 4.26 | -99.1% | -99.2% to -98.5% |
| `brackets_ascii` | -75.1% | -75.4% | 89.98 | 23.79 | -74.3% | -75.0% to -72.6% |
| `brackets_unicode` | -67.3% | -68.1% | 86.47 | 26.96 | -68.5% | -69.0% to -68.0% |
| `brackets_4k` | -4.6% | -98.8% | 454.19 | 8.05 | -98.2% | -98.6% to -97.5% |
| `views_4k` | -2.2% | +0.0% | 49.93 | 40.39 | -12.4% | -22.0% to -4.2% |
| `at_128k_0` | -99.2% | -99.3% | 123.62 | 1.39 | -98.9% | -99.4% to -98.6% |
| `at_128k_130` | -97.3% | -99.1% | 124.15 | 1.75 | -98.6% | -98.9% to -98.5% |
| `at_4k_late` | -0.2% | -0.2% | 179.22 | 177.26 | -1.4% | -3.5% to -0.2% |
| `distinct_short` | -77.8% | -68.5% | 13.27 | 7.60 | -44.2% | -73.4% to -24.4% |
| `distinct_4k_front` | -93.0% | -91.9% | 26.51 | 2.21 | -91.6% | -91.8% to -91.4% |
| `distinct_4k_middle` | -92.9% | -92.0% | 26.53 | 2.18 | -91.8% | -91.9% to -91.3% |
| `distinct_4k_late` | +0.9% | -1.7% | 25.90 | 25.73 | -0.4% | -1.3% to +0.4% |
| `distinct_4k_common_prefix_late` | -0.2% | -0.7% | 26.33 | 26.15 | -0.8% | -1.8% to -0.4% |
| `loop_distinct_4k_common_prefix_late` | — | +5.6% | 25.59 | 26.84 | +5.3% | +3.0% to +6.0% |
| `loop_alternating_4k_common_prefix_late` | — | +4.0% | 56.13 | 57.75 | +2.9% | +2.4% to +4.1% |
| `loop_repeated_4k_late` | — | -97.0% | 169.36 | 5.62 | -96.7% | -97.2% to -95.5% |
| `loop_over_limit_late` | — | +0.7% | 89.10 | 89.09 | +0.5% | -0.5% to +0.8% |

## Reproduce

From the benchmark repository, run the command below with the chosen Release compilers and an SDK. Omit `--candidate` to check the baseline alone. The runner supports `--case` to select individual rows. The source archive contains the exact emitted JavaScript and emitter sources for each trial. [Replay sources](js-byte-index-2026-11-28.raw/replay.tar.xz)

```bash
python3 -B benchmark/compiler/js_byte_index_bench.py \
  --baseline /path/to/baseline/forge --candidate /path/to/candidate/forge \
  --root ../forge/build --cpu 14 --pairs 8 --output /tmp/js-byte-index.json \
  --build-note 'Release compiler identities and flags'
```

The replay archive labels the compilers `before`, `prefix`, `loop` and `final`. The `*-stream.js` programs include the four Forge-loop stream controls. The earlier fixture, bridge and runners are included for the prefix reports. The archive manifest lists each file’s SHA-256. The following commands run the selected emitted program with a valid digest and check the complete callback sum.

```bash
replay_dir=$(mktemp -d)
tar -xf docs/compiler/js-byte-index-2026-11-28.raw/replay.tar.xz -C "$replay_dir"
(cd "$replay_dir" && sha256sum -c SHA256SUMS)
python3 -B - "$replay_dir" <<'PYTHON'
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, "benchmark/compiler")
from js_byte_index_bench import BRIDGE, cases, oracle

work = Path(sys.argv[1])
_, operation, inputs, offset, count = next(case for case in cases() if case[0] == "digest_valid")
config = work / "digest.json"
config.write_text(json.dumps(dict(operation=operation, inputs=inputs, offset=offset, count=count)))
run = subprocess.run(["node", "--require", BRIDGE, work / "final-stream.js", config],
                     capture_output=True, check=True, text=True)
assert not run.stderr
result = json.loads(run.stdout)
assert result["result"] == oracle(operation, inputs, offset, count)
print(result)
PYTHON
```
