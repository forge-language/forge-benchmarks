#!/usr/bin/env python3
"""Paired comparison for a range-guarded single-fold LCG candidate."""
import argparse
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

from cpu_compare import confidence, reference, run_binary, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-forge', type=Path, required=True)
    parser.add_argument('--candidate-forge', type=Path, required=True)
    parser.add_argument('--rust', type=Path, required=True)
    parser.add_argument('--candidate-source', type=Path, required=True)
    parser.add_argument('--baseline-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--pairs', type=int, default=60)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if args.pairs < 12 or args.pairs % 6:
        parser.error('--pairs must be a multiple of six and at least 12')
    if args.cpu not in os.sched_getaffinity(0):
        parser.error('--cpu must be in the current affinity set')
    if args.output.exists() and not args.overwrite:
        parser.error('output exists; choose another path or pass --overwrite')
    for path in (args.baseline_forge, args.candidate_forge, args.rust,
                 args.candidate_source, args.baseline_report):
        if not path.is_file():
            parser.error('file not found: ' + str(path))

    binaries = {'baseline_forge': args.baseline_forge,
                'candidate_forge': args.candidate_forge, 'rust': args.rust}
    checks = []
    rng = random.Random(20261012)
    seeds = [-(1 << 63), -(1 << 63) + 1, -2147483648, -2147483647,
             -2147483646, -1, 0, 1, 2147483645, 2147483646,
             2147483647, (1 << 63) - 1]
    dimensions = [(1, 1), (2, 1), (1, 2), (3, 4), (0, 10), (-1, 3), (7, -2)]
    cases = [(n, rounds, seed) for seed in seeds for n, rounds in dimensions]
    cases += [(rng.randint(-10, 80), rng.randint(-5, 30),
               rng.randint(-(1 << 63), (1 << 63) - 1)) for _ in range(500)]
    for n, rounds, seed in cases:
        expected = reference('lcg', n, rounds, seed)
        for name, binary in binaries.items():
            row = run_binary(binary, 'lcg', n, rounds, seed, args.cpu)
            if row['checksum'] != expected:
                raise RuntimeError(f'correctness mismatch {name}/{n}/{rounds}/{seed}: {row} != {expected}')
        checks.append({'n': n, 'rounds': rounds, 'seed': seed,
                       'expected_checksum': expected})

    n, rounds = 250000, 64
    permutations = list(itertools.permutations(binaries)) * (args.pairs // 6)
    rng.shuffle(permutations)
    warmups = []
    for name, binary in binaries.items():
        for seed in (719, 720, 721):
            row = run_binary(binary, 'lcg', n, rounds, seed, args.cpu)
            if row['checksum'] != reference('lcg', n, rounds, seed):
                raise RuntimeError('initial warmup mismatch')
            warmups.append({'language': name, 'seed': seed, **row})

    measured, per_input_warmups = [], []
    ratios = {'baseline_forge_over_candidate': [],
              'rust_over_candidate': [], 'rust_over_baseline_forge': []}
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for pair, order in enumerate(permutations):
        seed = rng.randint(1, 100000)
        expected = reference('lcg', n, rounds, seed)
        elapsed = {}
        for position, name in enumerate(order):
            warm = run_binary(binaries[name], 'lcg', n, rounds, seed, args.cpu)
            if warm['checksum'] != expected:
                raise RuntimeError('per-input warmup mismatch')
            per_input_warmups.append({'pair': pair, 'order': position,
                                      'language': name, 'seed': seed, **warm})
            row = run_binary(binaries[name], 'lcg', n, rounds, seed, args.cpu)
            if row['checksum'] != expected:
                raise RuntimeError('measurement mismatch')
            elapsed[name] = row['kernel_ns']
            measured.append({'pair': pair, 'order': position, 'language': name,
                             'n': n, 'rounds': rounds, 'seed': seed,
                             'expected_checksum': expected, **row})
        ratios['baseline_forge_over_candidate'].append(
            elapsed['baseline_forge'] / elapsed['candidate_forge'])
        ratios['rust_over_candidate'].append(elapsed['rust'] / elapsed['candidate_forge'])
        ratios['rust_over_baseline_forge'].append(elapsed['rust'] / elapsed['baseline_forge'])

    summary = {name: {'median': statistics.median(values),
                      'ci95': confidence(values, 20261012 + index)}
               for index, (name, values) in enumerate(ratios.items())}
    base = json.loads(args.baseline_report.read_text())
    report = {
        'started_at_utc': started,
        'finished_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'method': {
            'pairs': args.pairs, 'cpu': args.cpu, 'n': n, 'rounds': rounds,
            'ordering': 'balanced randomized six-permutation paired order',
            'prewarming': 'same-input prewarm immediately before every measurement',
            'ratio': 'numerator kernel_ns / denominator kernel_ns',
            'scope': 'algorithm-level Forge optimization against the unchanged Forge and Rust LCG controls; no language/compiler-wide claim',
            'rust_control': 'unchanged benchmark/cpu/kernels.rs from current HEAD',
        },
        'candidate': {
            'source': str(args.candidate_source),
            'source_sha256': sha(args.candidate_source),
            'binary_sha256': sha(args.candidate_forge),
            'baseline_binary_sha256': sha(args.baseline_forge),
            'rust_binary_sha256': sha(args.rust),
            'baseline_report': str(args.baseline_report),
            'baseline_report_sha256': sha(args.baseline_report),
            'build_artifacts': base['build']['artifacts'],
            'header_sha256': base['build']['header_sha256'],
            'compile_flags': '-std=gnu11 -O3 -DNDEBUG -march=native -flto',
            'rust_flags': '-C opt-level=3 -C target-cpu=native -C lto=thin -C codegen-units=1 -C overflow-checks=off',
        },
        'correctness_cases': checks,
        'initial_warmups': warmups,
        'per_input_warmups': per_input_warmups,
        'measurements': measured,
        'summary': summary,
        'runner_source': Path(__file__).read_text(),
        'runner_sha256': sha(Path(__file__)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print(f"correctness={len(checks)} prewarms={len(per_input_warmups)} measurements={len(measured)}")
    print('raw report: ' + str(args.output))


if __name__ == '__main__':
    main()
