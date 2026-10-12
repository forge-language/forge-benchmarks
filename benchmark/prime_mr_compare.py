#!/usr/bin/env python3
"""Compare a bounded Miller-Rabin Forge kernel with baseline Forge and Rust."""
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
    parser.add_argument('--candidate-rust', type=Path, required=True)
    parser.add_argument('--candidate-rust-source', type=Path, required=True)
    parser.add_argument('--candidate-source', type=Path, required=True)
    parser.add_argument('--baseline-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=60)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.pairs < 24 or args.pairs % 24:
        parser.error('--pairs must be a multiple of 24 and at least 24')
    if args.cpu not in os.sched_getaffinity(0):
        parser.error('--cpu must be in the current affinity set')
    if args.output.exists() and not args.overwrite:
        parser.error('output exists; choose another path or pass --overwrite')
    for path in (args.baseline_forge, args.candidate_forge, args.rust,
                 args.candidate_source, args.candidate_rust, args.candidate_rust_source, args.baseline_report):
        if not path.is_file():
            parser.error('file not found: ' + str(path))

    binaries = {'baseline_forge': args.baseline_forge,
                'candidate_forge': args.candidate_forge, 'rust': args.rust,
                'candidate_rust': args.candidate_rust}
    rng = random.Random(20261013)
    dimensions = [(0, 5), (1, 1), (2, 1), (3, 2), (31, 4), (127, 5)]
    seeds = [-1000100, -1000001, -1000000, -999999, -999998,
             -1, 0, 1, 719, 100000]
    cases = [(n, rounds, seed) for n, rounds in dimensions for seed in seeds]
    cases += [(rng.randint(0, 40), rng.randint(1, 4),
               rng.randint(-1000100, 100000)) for _ in range(100)]
    cases += [(1, 1, value - 1000001) for value in
              (-1, 0, 1, 2, 3, 4, 1373652, 1373653, 1373654,
               1373655, 1373657, 1500000, 1500001, 2000003, 10000019)]
    checks = []
    for n, rounds, seed in cases:
        expected = reference('primes', n, rounds, seed)
        for name, binary in binaries.items():
            row = run_binary(binary, 'primes', n, rounds, seed, args.cpu)
            if row['checksum'] != expected:
                raise RuntimeError(f'correctness mismatch {name}/{n}/{rounds}/{seed}: {row} != {expected}')
        checks.append({'n': n, 'rounds': rounds, 'seed': seed,
                       'expected_checksum': expected})

    n, rounds = 2000, 128
    permutations = list(itertools.permutations(binaries)) * (args.pairs // 24)
    rng.shuffle(permutations)
    initial_warmups = []
    for name, binary in binaries.items():
        for seed in (719, 720, 721):
            row = run_binary(binary, 'primes', n, rounds, seed, args.cpu)
            if row['checksum'] != reference('primes', n, rounds, seed):
                raise RuntimeError('initial warmup mismatch')
            initial_warmups.append({'language': name, 'seed': seed, **row})

    measured, per_input_warmups = [], []
    ratios = {'baseline_forge_over_candidate_forge': [],
              'rust_baseline_over_candidate_forge': [],
              'candidate_rust_over_candidate_forge': [],
              'candidate_rust_over_rust_baseline': [],
              'rust_baseline_over_candidate_rust': [],
              'rust_baseline_over_forge_baseline': []}
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for pair, order in enumerate(permutations):
        seed = rng.randint(1, 100000)
        expected = reference('primes', n, rounds, seed)
        elapsed = {}
        for position, name in enumerate(order):
            warm = run_binary(binaries[name], 'primes', n, rounds, seed, args.cpu)
            if warm['checksum'] != expected:
                raise RuntimeError('per-input warmup mismatch')
            per_input_warmups.append({'pair': pair, 'order': position,
                                      'language': name, 'seed': seed, **warm})
            row = run_binary(binaries[name], 'primes', n, rounds, seed, args.cpu)
            if row['checksum'] != expected:
                raise RuntimeError('measurement mismatch')
            elapsed[name] = row['kernel_ns']
            measured.append({'pair': pair, 'order': position, 'language': name,
                             'n': n, 'rounds': rounds, 'seed': seed,
                             'expected_checksum': expected, **row})
        ratios['baseline_forge_over_candidate_forge'].append(elapsed['baseline_forge'] / elapsed['candidate_forge'])
        ratios['rust_baseline_over_candidate_forge'].append(elapsed['rust'] / elapsed['candidate_forge'])
        ratios['candidate_rust_over_candidate_forge'].append(elapsed['candidate_rust'] / elapsed['candidate_forge'])
        ratios['candidate_rust_over_rust_baseline'].append(elapsed['candidate_rust'] / elapsed['rust'])
        ratios['rust_baseline_over_candidate_rust'].append(elapsed['rust'] / elapsed['candidate_rust'])
        ratios['rust_baseline_over_forge_baseline'].append(elapsed['rust'] / elapsed['baseline_forge'])

    summary = {name: {'median': statistics.median(values),
                      'ci95': confidence(values, 20261013 + index)}
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
            'scope': 'matched bounded Miller-Rabin algorithm comparison across Forge and Rust; this does not isolate compiler quality',
            'rust_control': 'unchanged benchmark/cpu/kernels.rs from current HEAD',
            'matched_rust_candidate_source': str(args.candidate_rust_source),
            'matched_rust_candidate_source_sha256': sha(args.candidate_rust_source),
        },
        'candidate': {
            'source': str(args.candidate_source),
            'source_sha256': sha(args.candidate_source),
            'binary_sha256': sha(args.candidate_forge),
            'baseline_binary_sha256': sha(args.baseline_forge),
            'rust_binary_sha256': sha(args.rust),
            'candidate_rust_source_sha256': sha(args.candidate_rust_source),
            'candidate_rust_binary_sha256': sha(args.candidate_rust),
            'baseline_report': str(args.baseline_report),
            'baseline_report_sha256': sha(args.baseline_report),
            'build_artifacts': base['build']['artifacts'],
            'header_sha256': base['build']['header_sha256'],
            'compile_flags': '-std=gnu11 -O3 -DNDEBUG -march=native -flto',
            'rust_flags': '-C opt-level=3 -C target-cpu=native -C lto=thin -C codegen-units=1 -C overflow-checks=off',
        },
        'correctness_cases': checks,
        'initial_warmups': initial_warmups,
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
