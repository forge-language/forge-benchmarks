#!/usr/bin/env python3
"""Compare frozen compiler/stdlib variants against one unchanged Rust control.

Every variant runs identical FG/Rust inputs, checked with the independent CPU
reference. Timing starts only after all snapshots have been built and validated.
"""
import argparse
import itertools
import json
import os
from pathlib import Path
import platform
import random
import statistics
import time

from cpu_compare import capture, confidence, reference, run_binary, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', action='append', required=True, metavar='NAME=BUILD_DIR')
    parser.add_argument('--baseline', required=True, help='One of the variant names')
    parser.add_argument('--dimensions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--pairs', type=int, default=20)
    parser.add_argument('--random-seed', type=int, default=20261012)
    args = parser.parse_args()
    directories = {}
    for value in args.variant:
        name, directory = value.split('=', 1)
        if name in directories or name == 'rust':
            parser.error('Variant names must be unique and cannot be rust')
        directories[name] = Path(directory).resolve()
    if args.baseline not in directories or args.cpu not in os.sched_getaffinity(0):
        parser.error('Choose a baseline variant and an allowed CPU')
    count = len(directories) + 1
    if args.pairs < 12 or args.pairs % count:
        parser.error('Use >=12 pairs divisible by implementation count for balanced positions')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Report exists; use a new output path')
    builds = {name: json.loads((directory / 'build.json').read_text())
              for name, directory in directories.items()}
    for name, directory in directories.items():
        for language in ('forge', 'rust'):
            if sha(directory / (language + '-cpu')) != builds[name]['executables'][language]['sha256']:
                raise RuntimeError('Frozen executable changed: ' + name + '/' + language)
        for fixture in ('kernels.fg', 'kernels.rs', 'clock.c'):
            if builds[name]['fixture_sha256'][fixture] != builds[args.baseline]['fixture_sha256'][fixture]:
                raise RuntimeError('Measured algorithm or timer changed: ' + name + '/' + fixture)
    binaries = {name: directory / 'forge-cpu' for name, directory in directories.items()}
    binaries['rust'] = directories[args.baseline] / 'rust-cpu'
    dimensions = json.loads(args.dimensions.read_text())['summary']
    rng = random.Random(args.random_seed)
    checks, warmups, measurements, summary = [], [], [], []
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for case in dimensions:
        mode, n, rounds = case['workload'], case['n'], case['rounds']
        for small_n, small_rounds, seed in ((1, 1, 1), (31, 3, 17), (127, 2, 719)):
            expected = reference(mode, small_n, small_rounds, seed)
            for name, binary in binaries.items():
                row = run_binary(binary, mode, small_n, small_rounds, seed, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError('Correctness failure: ' + name + '/' + mode)
                checks.append(dict(implementation=name, workload=mode, n=small_n,
                                   rounds=small_rounds, seed=seed, reference_checksum=expected, **row))
        # Each implementation occupies each ordinal position equally often.
        # Cyclic schedules do not balance every adjacency when count > 3.
        names = list(binaries)
        orders = [names[i:] + names[:i] for i in range(count)] * (args.pairs // count)
        rng.shuffle(orders)
        elapsed = {name: [] for name in binaries}
        over_rust = {name: [] for name in directories}
        speedup = {name: [] for name in directories}
        for pair, order in enumerate(orders):
            seed = rng.randint(1, 100000)
            expected = reference(mode, n, rounds, seed)
            paired = {}
            for position, name in enumerate(order):
                for kind in ('prewarm', 'measurement'):
                    row = run_binary(binaries[name], mode, n, rounds, seed, args.cpu)
                    if row['checksum'] != expected:
                        raise RuntimeError('Checksum failure: ' + name + '/' + mode + '/' + kind)
                    record = dict(implementation=name, workload=mode, pair=pair, order=position,
                                  n=n, rounds=rounds, seed=seed, reference_checksum=expected, **row)
                    (warmups if kind == 'prewarm' else measurements).append(record)
                    if kind == 'measurement':
                        paired[name] = row['kernel_ns']
                        elapsed[name].append(row['kernel_ns'])
            for name in directories:
                over_rust[name].append(paired['rust'] / paired[name])
                speedup[name].append(paired[args.baseline] / paired[name])
        def summarize(samples, offset):
            return dict(samples=samples, median=statistics.median(samples),
                        ci95=confidence(samples, args.random_seed + offset))
        row = dict(workload=mode, n=n, rounds=rounds, pairs=args.pairs,
                   median_ms={name: statistics.median(values) / 1e6 for name, values in elapsed.items()},
                   over_rust={name: summarize(values, i) for i, (name, values) in enumerate(over_rust.items())},
                   baseline_speedup={name: summarize(values, i + count) for i, (name, values) in enumerate(speedup.items())})
        summary.append(row)
        print(mode + ': ' + ', '.join(name + '/Rust=' + format(values['median'], '.4f')
                                     for name, values in row['over_rust'].items()), flush=True)
    report = dict(started_at_utc=started, finished_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  description=args.description, baseline=args.baseline, builds=builds,
                  rust_control=builds[args.baseline]['executables']['rust'],
                  runner=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  method=dict(pairs=args.pairs, cpu=args.cpu, random_seed=args.random_seed,
                              order='Position-balanced cyclic rotations, shuffled; adjacency is not fully balanced',
                              prewarm='One checked identical-input run before each sample',
                              confidence='10000 paired-ratio median bootstrap resamples; percentile 95%; not family-wise confidence',
                              throughput_over_rust='rust_kernel_ns / forge_kernel_ns',
                              baseline_speedup='baseline_kernel_ns / variant_kernel_ns',
                              dimensions=dict(path=str(args.dimensions), sha256=sha(args.dimensions)),
                              limitations='Shared Linux host, finite workloads, no timing outlier exclusion; RSS is whole-process not precise heap usage'),
                  environment=dict(platform=platform.platform(), python=platform.python_version(),
                                   allowed_affinity=sorted(os.sched_getaffinity(0)), load_average_end=os.getloadavg(),
                                   lscpu=capture(['lscpu'])), correctness_checks=checks, warmups=warmups,
                  measurements=measurements, summary=summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Frozen Forge optimization comparison', '', args.description, '',
             f'Measured `{started}` to `{report["finished_at_utc"]}` with {args.pairs} position-balanced pairs per workload. One preserved Rust binary is shared by every variant.', '',
             '| Workload | Variant | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |',
             '| --- | --- | ---: | ---: | --- |']
    for row in summary:
        for name in directories:
            ratio, gain = row['over_rust'][name], row['baseline_speedup'][name]
            low, high = ratio['ci95']
            status = 'supported for this case' if low >= 1.10 else 'below target' if high < 1.10 else 'inconclusive'
            lines.append(f'| {row["workload"]} | {name} | {ratio["median"]:.4f} [{low:.4f}, {high:.4f}] | {gain["median"]:.4f} [{gain["ci95"][0]:.4f}, {gain["ci95"][1]:.4f}] | {status} |')
    lines += ['', 'All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.', '',
              'Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.', '',
              'Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.', '',
              'These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.', '',
              f'Raw provenance and all samples: [{args.output.name}]({args.output.name}).', '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
