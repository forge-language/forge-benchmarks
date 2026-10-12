#!/usr/bin/env python3
"""Paired same-algorithm LCG loop-unroll probe across Forge and Rust."""
import argparse
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import time

from cpu_compare import capture, confidence, reference, run_binary, sha

ROOT = Path(__file__).resolve().parents[1]


def compile_fixture(snapshot, source, language, output, cc, rustc):
    if language == 'forge':
        c_source = output.with_suffix('.c')
        subprocess_run([str(snapshot / 'forge'), str(source), '--emit-c', '-o', str(c_source),
                        '--forge-root', str(snapshot)])
        command = [cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto',
                   '-I', str(snapshot / 'include'), str(c_source), str(snapshot / 'clock.c'),
                   '-Wl,--start-group', str(snapshot / 'libforge_std.a'),
                   str(snapshot / 'libforge_runtime.a'), '-Wl,--end-group', '-lpthread', '-lm',
                   '-o', str(output)]
    else:
        clock_object = output.parent / 'clock.o'
        if not clock_object.exists():
            subprocess_run([cc, '-std=gnu11', '-O3', '-march=native', '-c',
                            str(snapshot / 'clock.c'), '-o', str(clock_object)])
        command = [rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'lto=thin',
                   '-C', 'codegen-units=1', '-C', 'overflow-checks=off',
                   '-C', 'link-arg=' + str(clock_object), str(source), '-o', str(output)]
    subprocess_run(command)
    return command


def subprocess_run(command):
    import subprocess
    subprocess.run(command, check=True, capture_output=True, text=True)


def summarize(values, seed):
    return {'median': statistics.median(values), 'ci95': confidence(values, seed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True,
                        help='immutable cpu_compare snapshot containing compiler, libraries and headers')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=120)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--random-seed', type=int, default=20261012)
    parser.add_argument('--cc', default='gcc')
    parser.add_argument('--rustc', default='rustc')
    args = parser.parse_args()
    if args.pairs < 24 or args.pairs % 24:
        parser.error('--pairs must be a multiple of 24 and at least 24')
    if args.cpu not in os.sched_getaffinity(0):
        parser.error('--cpu is outside the current affinity set')
    snapshot = args.snapshot.resolve()
    for name in ['forge', 'kernels.fg', 'kernels.rs', 'clock.c', 'libforge_std.a',
                 'libforge_runtime.a']:
        if not (snapshot / name).is_file():
            parser.error('missing snapshot file: ' + str(snapshot / name))
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('output exists; choose a fresh path')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.with_suffix('.artifacts')
    artifacts.mkdir(parents=True)
    fixtures = {
        'forge_base': ('forge', snapshot / 'kernels.fg'),
        'forge_unroll4': ('forge', ROOT / 'benchmark/cpu/kernels_lcg_unroll4.fg'),
        'rust_base': ('rust', snapshot / 'kernels.rs'),
        'rust_unroll4': ('rust', ROOT / 'benchmark/cpu/kernels_lcg_unroll4.rs'),
    }
    binaries = {}
    commands = {}
    for name, (language, source) in fixtures.items():
        binary = artifacts / name
        commands[name] = compile_fixture(snapshot, source, language, binary, args.cc, args.rustc)
        binaries[name] = binary

    cases = []
    limits = [-(1 << 63), -(1 << 63) + 1, -1, 0, 1, 2147483646, (1 << 63) - 1]
    for n in (-7, 0, 1, 2, 3, 4, 5, 31, 250000):
        for rounds in (-2, 0, 1, 3):
            for seed in limits:
                cases.append((n, rounds, seed))
    checks = []
    for n, rounds, seed in cases:
        expected = reference('lcg', n, rounds, seed)
        for name, binary in binaries.items():
            observed = run_binary(binary, 'lcg', n, rounds, seed, args.cpu)
            if observed['checksum'] != expected:
                raise RuntimeError(f'correctness mismatch {name}/{n}/{rounds}/{seed}: {observed}')
        checks.append({'n': n, 'rounds': rounds, 'seed': seed, 'expected_checksum': expected})

    names = list(binaries)
    orders = list(itertools.permutations(names)) * (args.pairs // 24)
    rng = random.Random(args.random_seed)
    rng.shuffle(orders)
    measurements = []
    warmups = []
    ratio_baseline = []
    ratio_candidate = []
    forge_speedups = []
    rust_speedups = []
    for pair, order in enumerate(orders):
        seed = rng.randint(-1000000000, 1000000000)
        elapsed = {}
        for position, name in enumerate(order):
            warm = run_binary(binaries[name], 'lcg', 250000, 64, seed, args.cpu)
            expected = reference('lcg', 250000, 64, seed)
            if warm['checksum'] != expected:
                raise RuntimeError('warmup checksum mismatch: ' + name)
            warmups.append({'pair': pair, 'order': position, 'variant': name,
                            'seed': seed, **warm})
            result = run_binary(binaries[name], 'lcg', 250000, 64, seed, args.cpu)
            if result['checksum'] != expected:
                raise RuntimeError('measurement checksum mismatch: ' + name)
            elapsed[name] = result['kernel_ns']
            measurements.append({'pair': pair, 'order': position, 'variant': name,
                                 'seed': seed, 'n': 250000, 'rounds': 64,
                                 'expected_checksum': expected, **result})
        ratio_baseline.append(elapsed['rust_base'] / elapsed['forge_base'])
        ratio_candidate.append(elapsed['rust_unroll4'] / elapsed['forge_unroll4'])
        forge_speedups.append(elapsed['forge_base'] / elapsed['forge_unroll4'])
        rust_speedups.append(elapsed['rust_base'] / elapsed['rust_unroll4'])

    ratio_of_ratios = [candidate / baseline for candidate, baseline in
                        zip(ratio_candidate, ratio_baseline)]
    forge_speed = summarize(forge_speedups, args.random_seed + 1)
    rust_speed = summarize(rust_speedups, args.random_seed + 2)
    baseline_ratio = summarize(ratio_baseline, args.random_seed + 3)
    candidate_ratio = summarize(ratio_candidate, args.random_seed + 4)
    relative_change = summarize(ratio_of_ratios, args.random_seed + 5)
    report = {
        'status': 'completed',
        'recorded_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'method': {'pairs': args.pairs, 'cpu': args.cpu,
                   'dimensions': {'n': 250000, 'rounds': 64},
                   'ordering': 'balanced randomized permutations of all four Forge/Rust baseline/unroll variants',
                   'prewarming': 'same-input checked warmup immediately before each measurement',
                   'correctness_reference': 'independent modular-exponentiation LCG reference with signed i64 wrapping',
                   'unroll_factor': 4,
                   'claim_scope': 'same recurrence and semantics; source loop-control change only'},
        'sources': {name: {'path': str(source), 'sha256': sha(source)}
                    for name, (_, source) in fixtures.items()},
        'build': {'snapshot': str(snapshot), 'snapshot_files': {
            name: sha(snapshot / name) for name in ['forge', 'kernels.fg', 'kernels.rs',
                                                   'clock.c', 'libforge_std.a', 'libforge_runtime.a']},
            'commands': commands,
            'compiler_versions': {'gcc': capture([args.cc, '--version']).splitlines()[0],
                                  'rustc': capture([args.rustc, '--version'])},
            'compiled_binaries': {name: {'path': str(binary), 'sha256': sha(binary)}
                                  for name, binary in binaries.items()}},
        'correctness_cases': checks, 'warmups': warmups, 'measurements': measurements,
        'summary': {'baseline_rust_over_forge': baseline_ratio,
                    'unroll4_rust_over_forge': candidate_ratio,
                    'forge_baseline_over_unroll4': forge_speed,
                    'rust_baseline_over_unroll4': rust_speed,
                    'rust_relative_ratio_of_ratios': relative_change},
        'runner_sha256': sha(Path(__file__)),
        'runner_source': Path(__file__).read_text(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    summary = report['summary']
    print(json.dumps(summary, indent=2))
    print(f"correctness={len(checks)} prewarms={len(warmups)} measurements={len(measurements)}")
    lines = ['# LCG factor-4 loop-unroll comparison', '',
             f"Recorded at `{report['recorded_at_utc']}`. Forge and Rust retain the same recurrence and wrapping semantics; only the inner loop is manually unrolled by four with a scalar tail.", '',
             '| Metric | Median | Bootstrap 95% interval |', '| --- | ---: | ---: |']
    for label, key in [('Baseline Rust / Forge throughput', 'baseline_rust_over_forge'),
                       ('Unroll-4 Rust / Forge throughput', 'unroll4_rust_over_forge'),
                       ('Forge baseline / unroll-4 speedup', 'forge_baseline_over_unroll4'),
                       ('Rust baseline / unroll-4 speedup', 'rust_baseline_over_unroll4'),
                       ('Unroll-4 relative Rust/Forge change', 'rust_relative_ratio_of_ratios')]:
        value = summary[key]
        lines.append(f"| {label} | {value['median']:.4f} | [{value['ci95'][0]:.4f}, {value['ci95'][1]:.4f}] |")
    lines += ['', f"All {len(checks)} direct edge/reference checks, {len(warmups)} prewarms and {len(measurements)} timed measurements passed. Source and binary hashes, every sample and the exact runner are preserved in [{args.output.name}]({args.output.name}).", '',
              'The result applies only to this LCG workload, host, toolchain and build snapshot; it does not establish language-wide performance. A relative interval crossing 1.0 or no Forge absolute speedup is not evidence of a gain.']
    args.output.with_suffix('.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
