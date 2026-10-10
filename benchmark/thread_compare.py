#!/usr/bin/env python3
"""Compare native thread APIs with fixed total work and verified completion.

Consumes an immutable CPU-harness SDK snapshot, never an in-flight build tree.
The C bridge supplies a common timer/counters only, not an algorithm.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess

from cpu_compare import confidence, run_binary, sha

ROOT = Path(__file__).resolve().parents[1]


def physical_cpus():
    available = os.sched_getaffinity(0)
    selected = {}
    for cpu in sorted(available):
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = ((topology / 'physical_package_id').read_text().strip(),
               (topology / 'core_id').read_text().strip())
        selected.setdefault(key, cpu)
    return list(selected.values())


def reference(n, rounds, seed, workers):
    return sum((seed + i) * pow(48271, (n // workers + int(i < n % workers)) * rounds,
                                2147483647) % 2147483647 for i in range(workers))


def require_checksum(run, n, rounds, seed, workers, language):
    expected = reference(n, rounds, seed, workers)
    if run['checksum'] != expected:
        raise RuntimeError(f'{language}: checksum {run["checksum"]} != {expected}; '
                           f'n={n}, rounds={rounds}, seed={seed}, workers={workers}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--rustc', default='rustc')
    parser.add_argument('--n', type=int, default=16000000)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--pairs', type=int, default=16)
    parser.add_argument('--workers', type=int, nargs='+', default=[1, 2, 4])
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-build', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new path to preserve raw evidence')
    if args.n < 1 or args.rounds < 1 or args.pairs < 4 or args.pairs % 2:
        parser.error('Positive dimensions and an even pair count >= 4 are required')
    cpus = physical_cpus()
    if not args.workers or any(w not in (1, 2, 4) or w > len(cpus) for w in args.workers):
        parser.error('Workers must be 1/2/4 and fit available physical cores')
    directory = args.build_dir.resolve()
    snapshot = directory / 'snapshot'
    commands = []
    if not args.reuse_build:
        if directory.exists():
            parser.error('Build directory exists; use a new path or --reuse-build')
        shutil.copytree(args.snapshot.resolve(), snapshot)
        for name in ('kernels.fg', 'kernels.rs', 'observer.c'):
            shutil.copyfile(ROOT / 'benchmark/thread' / name, snapshot / ('thread_' + name))
        shutil.copyfile(ROOT / 'benchmark/cpu/clock.c', snapshot / 'thread_clock.c')
        commands = [
            [str(snapshot / 'forge'), str(snapshot / 'thread_kernels.fg'), '--emit-c',
             '-o', str(snapshot / 'thread_kernels.c'), '--forge-root', str(snapshot)],
            [args.cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto',
             '-I', str(snapshot / 'include'), str(snapshot / 'thread_kernels.c'),
             str(snapshot / 'thread_observer.c'), str(snapshot / 'thread_clock.c'),
             '-Wl,--start-group', str(snapshot / 'libforge_std.a'), str(snapshot / 'libforge_runtime.a'),
             '-Wl,--end-group', '-lpthread', '-lm', '-o', str(directory / 'forge-thread')],
            [args.cc, '-std=gnu11', '-O3', '-march=native', '-c', str(snapshot / 'thread_observer.c'),
             '-o', str(snapshot / 'thread_observer.o')],
            [args.cc, '-std=gnu11', '-O3', '-march=native', '-c', str(snapshot / 'thread_clock.c'),
             '-o', str(snapshot / 'thread_clock.o')],
            [args.rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'lto=thin',
             '-C', 'codegen-units=1', '-C', 'overflow-checks=off',
             '-C', 'link-arg=' + str(snapshot / 'thread_observer.o'),
             '-C', 'link-arg=' + str(snapshot / 'thread_clock.o'),
             str(snapshot / 'thread_kernels.rs'), '-o', str(directory / 'rust-thread')],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
        build = {'commands': commands,
                 'cc_version': subprocess.check_output([args.cc, '--version'], text=True),
                 'rust_version': subprocess.check_output([args.rustc, '-Vv'], text=True),
                 'snapshot_sha256': {str(p.relative_to(snapshot)): sha(p)
                                     for p in snapshot.rglob('*') if p.is_file()},
                 'binary_sha256': {name: sha(directory / (name + '-thread')) for name in ('forge', 'rust')}}
        (directory / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    else:
        build = json.loads((directory / 'build.json').read_text())
        for name in ('forge', 'rust'):
            if sha(directory / (name + '-thread')) != build['binary_sha256'][name]:
                parser.error('Executable changed after snapshot build')
    if args.build_only:
        print('Built immutable native-thread snapshot: ' + str(directory))
        return
    records, checks = [], []
    for workers in args.workers:
        for n in (1, workers + 1, 137):
            for name in ('forge', 'rust'):
                run = run_binary(directory / (name + '-thread'), str(workers), n, 3, 71, cpus[:workers])
                require_checksum(run, n, 3, 71, workers, name)
                checks.append({'language': name, 'workers': workers, 'n': n, **run})
    rng = random.Random(20261009)
    orders = {w: [False, True] * (args.pairs // 2) for w in args.workers}
    for order in orders.values():
        rng.shuffle(order)
    for pair in range(args.pairs):
        sequence = args.workers.copy()
        rng.shuffle(sequence)
        for workers in sequence:
            seed = 73 + pair % 5
            samples = {}
            order = ['forge', 'rust'] if orders[workers][pair] else ['rust', 'forge']
            for name in order:
                # Prewarm the identical input immediately before each sample.
                for kind in ('prewarm', 'measured'):
                    run = run_binary(directory / (name + '-thread'), str(workers),
                                     args.n, args.rounds, seed, cpus[:workers])
                    require_checksum(run, args.n, args.rounds, seed, workers, name)
                    samples[name + '_' + kind] = run
            records.append({'pair': pair, 'workers': workers, 'cpus': cpus[:workers],
                            'seed': seed, 'order': order, **samples})
    summary = {}
    for workers in args.workers:
        rows = [r for r in records if r['workers'] == workers]
        ratios = [r['rust_measured']['kernel_ns'] / r['forge_measured']['kernel_ns'] for r in rows]
        summary[str(workers)] = {'paired_ratio_median': statistics.median(ratios),
                                'bootstrap_95': confidence(ratios, 20261009),
                                **{name + '_median_ns': statistics.median(r[name + '_measured']['kernel_ns'] for r in rows)
                                   for name in ('forge', 'rust')}}
    report = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'build': build,
              'method': {'n_total_per_round': args.n, 'rounds': args.rounds, 'pairs': args.pairs,
                         'physical_cpu_candidates': cpus, 'prewarm': 'identical input before each sample',
                         'scope': 'native OS threads, startup/join and worker argument parsing inside timer; no coroutine/queue/HTTP comparison'},
              'correctness_checks': checks, 'measurements': records, 'summary': summary}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
