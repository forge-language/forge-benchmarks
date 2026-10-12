#!/usr/bin/env python3
"""Paired baseline/candidate comparison for generated coroutine code and runtime."""
import argparse
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import time

from cpu_compare import capture, confidence, sha, stable_copy
from coroutine_compare import CASES, adapt_main, run
from thread_compare import physical_cpus

ROOT = Path(__file__).resolve().parents[1]


def copy_sdk(source, destination):
    source = source.resolve()
    destination.mkdir(parents=True)
    artifacts = {}
    for name, path in {
        'compiler': source / 'bin/forge',
        'runtime': source / 'lib/libforge_runtime.a',
        'stdlib': source / 'lib/libforge_std.a',
    }.items():
        artifacts[name] = stable_copy(path, destination / ('forge' if name == 'compiler' else path.name))
    shutil.copytree(source / 'include', destination / 'include')
    artifacts['headers'] = {str(p.relative_to(destination / 'include')): sha(p)
                            for p in (destination / 'include').rglob('*') if p.is_file()}
    return artifacts


def build_variant(name, sdk, snapshot, directory, cc):
    directory.mkdir(parents=True)
    original = directory / 'generated-original.c'
    adapted = directory / 'generated-adapted.c'
    command = [str(sdk / 'forge'), str(snapshot / 'kernels.fg'), '--emit-c', '-o', str(original),
               '--forge-root', str(sdk)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    adapted.write_text(adapt_main(original.read_text()))
    binary = directory / 'forge-coro'
    link = [cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto',
            '-I', str(sdk / 'include'), '-I', str(snapshot), str(adapted), str(snapshot / 'observer.c'),
            '-Wl,--start-group', str(sdk / 'libforge_std.a'), str(sdk / 'libforge_runtime.a'),
            '-Wl,--end-group', '-lpthread', '-lm', '-o', str(binary)]
    subprocess.run(link, check=True, capture_output=True, text=True, timeout=180)
    return {'compiler_command': command, 'c_command': link,
            'generated_c_sha256': sha(original), 'adapted_c_sha256': sha(adapted),
            'binary_sha256': sha(binary)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-sdk', type=Path, required=True)
    parser.add_argument('--candidate-sdk', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--cargo', default='cargo')
    parser.add_argument('--pairs', type=int, default=16)
    parser.add_argument('--workers', type=int, nargs='+', default=[1, 2, 4])
    args = parser.parse_args()
    if args.pairs < 8 or args.pairs % 2:
        parser.error('Use an even number of at least 8 paired groups')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Report exists; preserve it and choose a new output path')
    cpus = physical_cpus()
    if any(w not in (1, 2, 4) or w > len(cpus) for w in args.workers):
        parser.error('Supported worker counts are 1, 2, and 4 physical CPUs')
    directory = args.build_dir.resolve()
    if directory.exists():
        parser.error('Build directory exists; choose a fresh path')
    snapshot = directory / 'snapshot'
    snapshot.mkdir(parents=True)
    fixtures = ROOT / 'benchmark/coroutine'
    for file in ['kernels.fg', 'observer.c', 'observer.h', 'Cargo.toml', 'Cargo.lock']:
        shutil.copyfile(fixtures / file, snapshot / file)
    shutil.copytree(fixtures / 'src', snapshot / 'src')
    sdks = {}
    artifacts = {}
    build = {}
    for name, source in [('baseline', args.baseline_sdk), ('candidate', args.candidate_sdk)]:
        sdks[name] = snapshot / (name + '-sdk')
        artifacts[name] = copy_sdk(source, sdks[name])
        build[name] = build_variant(name, sdks[name], snapshot, directory / name, args.cc)
    if artifacts['baseline']['stdlib']['sha256'] != artifacts['candidate']['stdlib']['sha256']:
        raise RuntimeError('Stdlib archives differ; this comparison would conflate changes')

    rustflags = '-C target-cpu=native -C overflow-checks=off -C link-arg=' + str(snapshot / 'observer.o')
    observer_command = [args.cc, '-std=gnu11', '-O3', '-march=native', '-I', str(snapshot), '-c',
                        str(snapshot / 'observer.c'), '-o', str(snapshot / 'observer.o')]
    subprocess.run(observer_command, check=True, capture_output=True, text=True)
    rust_command = [args.cargo, 'build', '--release', '--locked', '--manifest-path',
                    str(snapshot / 'Cargo.toml'), '--target-dir', str(directory / 'rust-target')]
    env = dict(os.environ, RUSTFLAGS=rustflags)
    subprocess.run(rust_command, check=True, capture_output=True, text=True, env=env, timeout=180)
    rust_binary = directory / 'rust-coro'
    shutil.copy2(directory / 'rust-target/release/forge-coroutine-control', rust_binary)
    binaries = {name: directory / name / 'forge-coro' for name in ('baseline', 'candidate')}
    binaries['rust'] = rust_binary
    build['observer_command'] = observer_command
    build['rust_command'] = rust_command
    build['rustflags'] = rustflags
    build['rust_binary_sha256'] = sha(rust_binary)
    build['cc_version'] = capture([args.cc, '--version'])
    build['rust_version'] = capture(['rustc', '-Vv'])
    build['fixture_sha256'] = {str(p.relative_to(snapshot)): sha(p)
                               for p in snapshot.rglob('*') if p.is_file()}

    checks = []
    for workers in args.workers:
        for tasks, rounds, chunk in [(1, 1, 1), (workers + 1, 3, 7), (137, 11, 17)]:
            for name, binary in binaries.items():
                row = run(binary, workers, tasks, rounds, chunk, 71, cpus[:workers])
                checks.append({'implementation': name, 'workers': workers, 'tasks': tasks,
                               'rounds': rounds, 'chunk': chunk, 'seed': 71, **row})

    rng = random.Random(20261012)
    orders = {key: [False, True] * (args.pairs // 2)
              for key in [(case, workers) for case in CASES for workers in args.workers]}
    for order in orders.values():
        rng.shuffle(order)
    measurements, warmups, summary = [], [], []
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for case, workers in [(case, workers) for case in CASES for workers in args.workers]:
        tasks, rounds, chunk = CASES[case]
        ratios = []
        for pair in range(args.pairs):
            seed = rng.randint(1, 100000)
            sequence = ['candidate', 'baseline'] if orders[(case, workers)][pair] else ['baseline', 'candidate']
            pair_elapsed = {}
            for position, name in enumerate(sequence):
                for kind in ('prewarm', 'measurement'):
                    row = run(binaries[name], workers, tasks, rounds, chunk, seed, cpus[:workers])
                    record = {'case': case, 'workers': workers, 'pair': pair, 'order': position,
                              'seed': seed, 'kind': kind, 'language': name, **row}
                    (warmups if kind == 'prewarm' else measurements).append(record)
                    if kind == 'measurement':
                        pair_elapsed[name] = row['kernel_ns']
            ratios.append(pair_elapsed['baseline'] / pair_elapsed['candidate'])
        summary.append({'case': case, 'workers': workers, 'pairs': args.pairs,
                        'baseline_median_ms': statistics.median(
                            r['kernel_ns'] for r in measurements if r['case'] == case and
                            r['workers'] == workers and r['language'] == 'baseline') / 1e6,
                        'candidate_median_ms': statistics.median(
                            r['kernel_ns'] for r in measurements if r['case'] == case and
                            r['workers'] == workers and r['language'] == 'candidate') / 1e6,
                        'paired_speedup_samples': ratios,
                        'paired_speedup_median': statistics.median(ratios),
                        'ci95': confidence(ratios, 20261012 + workers + len(case))})

    report = {'started_at_utc': started, 'finished_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'method': {'pairs': args.pairs, 'ratio': 'baseline kernel_ns / candidate kernel_ns',
                         'ordering': 'balanced randomized paired order per workload and worker count',
                         'prewarming': 'same-input prewarm before each measured binary',
                         'correctness': 'all measured runs checked against independent Python modular exponentiation; every task value and completion count validated',
                         'timing_scope': 'observer setup, runtime creation, spawn, completion, shutdown, and unique-ID validation',
                         'physical_cpus': {str(w): cpus[:w] for w in args.workers}},
              'build': build, 'sdk_artifacts': artifacts, 'checks': checks, 'warmups': warmups,
              'measurements': measurements, 'summary': summary,
              'measurement_runner_source': Path(__file__).read_text(),
              'measurement_runner_sha256': sha(Path(__file__))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Paired coroutine codegen/runtime comparison', '',
             'Each pair uses the same task count, rounds, chunk, seed, observer, Rust control, compiler flags, and per-input prewarm. The baseline and candidate differ only in the compiler/runtime SDK artifacts; both use the same stdlib archive.', '',
             '| Case | Workers | Baseline ms | Candidate ms | Paired speedup (95% interval) | 1.10 improvement |',
             '| --- | ---: | ---: | ---: | --- | --- |']
    for row in summary:
        lo, hi = row['ci95']
        status = 'supported' if lo >= 1.10 else 'below' if hi < 1.10 else 'inconclusive'
        lines.append(f'| {row["case"]} | {row["workers"]} | {row["baseline_median_ms"]:.3f} | {row["candidate_median_ms"]:.3f} | {row["paired_speedup_median"]:.4f} [{lo:.4f}, {hi:.4f}] | {status} |')
    lines += ['', 'The 1.10 improvement column tests whether the candidate is at least 10% faster than the old Forge SDK on this workload; it does not claim 1.10x Rust performance. Raw samples, artifact hashes, compiler commands, and this runner source are retained in the JSON.', '',
              'Rust 1.53.0 uses the pinned fixture control and is used as a same-input correctness/measurement control, not as the ratio denominator in this report.', '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))
    print('Completed paired coroutine codegen/runtime comparison: ' + str(args.output))


if __name__ == '__main__':
    main()
