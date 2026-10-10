#!/usr/bin/env python3
"""Complete-lifecycle Forge coroutine / pinned Tokio async comparison.

The generated-C adapter changes only main's worker configuration and measurement
boundaries. FG/Rust implement the same recurrence and logical explicit yields.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import tempfile
import time

from cpu_compare import capture, confidence, sha, source_state, stable_copy
from thread_compare import physical_cpus

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS = ROOT.parent
CASES = {'scheduler-heavy': (4000, 128, 1), 'mixed-cpu': (4000, 64, 256), 'budget-crossing': (256, 4096, 1)}


def adapt_main(source):
    # Exact, single-use anchors prevent silent timer scope or workload changes
    # when compiler generation evolves. The coroutine functions stay unchanged.
    anchors = {
        '    fr_os_set_args(argc, argv);\n':
        '    fr_os_set_args(argc, argv);\n    bench_config(argc, (const char *const *)argv);\n    int64_t bench_started = bench_clock_ns();\n    bench_prepare();\n',
        '    fr_scheduler_t *sched = fr_scheduler_create(0);\n':
        '    fr_scheduler_t *sched = fr_scheduler_create((int)bench_arg(0));\n    if (!sched || fr_scheduler_worker_count(sched) != bench_arg(0)) abort();\n',
        '    fr_scheduler_destroy(sched);\n    return 0;\n':
        '    fr_scheduler_destroy(sched);\n    return bench_finish(bench_started);\n',
    }
    start = source.rfind('int main(int argc, char **argv) {\n')
    if start < 0:
        raise RuntimeError('Generated main signature changed')
    prefix, main = source[:start], source[start:]
    for old, new in anchors.items():
        if main.count(old) != 1:
            raise RuntimeError('Generated main anchor changed: ' + repr(old))
        main = main.replace(old, new)
    return '#include "observer.h"\n' + prefix + main


def run(binary, workers, tasks, rounds, chunk, seed, cpus):
    argv = [str(binary), *map(str, [workers, tasks, rounds, chunk, seed])]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        tick = time.perf_counter_ns()
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                 preexec_fn=lambda: os.sched_setaffinity(0, set(cpus)))
        deadline = time.monotonic() + 90
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            if time.monotonic() > deadline:
                child.kill(); os.wait4(child.pid, 0); child.returncode = -9
                raise RuntimeError('Timeout: ' + repr(argv))
            time.sleep(.002)
        wall = time.perf_counter_ns() - tick
        stdout.seek(0); output = stdout.read().decode()
        stderr.seek(0); error = stderr.read().decode()
        if child.returncode:
            raise RuntimeError(f'{argv} failed ({child.returncode}): {error} {output[:200]}')
    lines = output.strip().splitlines()
    if len(lines) != 3:
        raise RuntimeError('Unexpected benchmark output')
    checksum, elapsed = map(int, lines[:2])
    values = list(map(int, lines[2].split(',')))
    factor = pow(48271, rounds * chunk, 2147483647)
    expected = [(seed + id) * factor % 2147483647 for id in range(tasks)]
    if elapsed <= 0 or len(values) != tasks or values != expected or checksum != sum(expected):
        raise RuntimeError('Per-task reference/completion failure: ' + repr(argv))
    return {'checksum': checksum, 'kernel_ns': elapsed, 'completed_tasks': tasks,
            'every_task_reference_matches': True,
            'result_vector_sha256': hashlib.sha256(lines[2].encode()).hexdigest(),
            'process_wall_ns': wall, 'process_user_seconds': usage.ru_utime,
            'process_system_seconds': usage.ru_stime, 'process_peak_rss_kib': usage.ru_maxrss}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True, help='Immutable validated SDK prefix: include/ and lib/')
    parser.add_argument('--forge', type=Path, help='Defaults to sdk/bin/forge')
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--cargo', default='cargo')
    parser.add_argument('--pairs', type=int, default=16)
    parser.add_argument('--workers', type=int, nargs='+', default=[1, 2, 4])
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-build', action='store_true')
    args = parser.parse_args()
    measurement_source = Path(__file__).read_text()
    if not args.build_only and (args.output.exists() or args.output.with_suffix('.md').exists()):
        parser.error('Output exists; preserve evidence and choose a new output')
    cpus = physical_cpus()
    if args.pairs < 8 or args.pairs % 2 or any(w not in (1, 2, 4) or w > len(cpus) for w in args.workers):
        parser.error('Use even >=8 pairs and supported 1/2/4 physical workers')
    directory = args.build_dir.resolve()
    snapshot = directory / 'snapshot'
    if not args.reuse_build:
        if directory.exists():
            parser.error('Build exists; choose a fresh directory or --reuse-build')
        snapshot.mkdir(parents=True)
        artifacts = {'compiler': stable_copy((args.forge or args.sdk / 'bin/forge').resolve(), snapshot / 'forge'),
                     'runtime': stable_copy((args.sdk / 'lib/libforge_runtime.a').resolve(), snapshot / 'libforge_runtime.a'),
                     'stdlib': stable_copy((args.sdk / 'lib/libforge_std.a').resolve(), snapshot / 'libforge_std.a')}
        shutil.copytree(args.sdk / 'include', snapshot / 'include')
        fixture = ROOT / 'benchmark/coroutine'
        for name in ['kernels.fg', 'observer.c', 'observer.h', 'Cargo.toml', 'Cargo.lock']:
            shutil.copyfile(fixture / name, snapshot / name)
        shutil.copytree(fixture / 'src', snapshot / 'src')
        commands = [[str(snapshot / 'forge'), str(snapshot / 'kernels.fg'), '--emit-c',
                     '-o', str(snapshot / 'generated-original.c'), '--forge-root', str(snapshot)]]
        subprocess.run(commands[0], check=True, capture_output=True, text=True)
        original = (snapshot / 'generated-original.c').read_text()
        (snapshot / 'generated-adapted.c').write_text(adapt_main(original))
        commands += [
            [args.cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto',
             '-I', str(snapshot / 'include'), '-I', str(snapshot), str(snapshot / 'generated-adapted.c'),
             str(snapshot / 'observer.c'), '-Wl,--start-group', str(snapshot / 'libforge_std.a'),
             str(snapshot / 'libforge_runtime.a'), '-Wl,--end-group', '-lpthread', '-lm', '-o', str(directory / 'forge-coro')],
            [args.cc, '-std=gnu11', '-O3', '-march=native', '-I', str(snapshot), '-c',
             str(snapshot / 'observer.c'), '-o', str(snapshot / 'observer.o')],
            [args.cargo, 'build', '--release', '--locked', '--manifest-path', str(snapshot / 'Cargo.toml'),
             '--target-dir', str(directory / 'rust-target')],
        ]
        rustflags = '-C target-cpu=native -C overflow-checks=off -C link-arg=' + str(snapshot / 'observer.o')
        for command in commands[1:]:
            env = dict(os.environ, RUSTFLAGS=rustflags) if command[0] == args.cargo else None
            subprocess.run(command, check=True, capture_output=True, text=True, env=env, timeout=180)
        shutil.copy2(directory / 'rust-target/release/forge-coroutine-control', directory / 'rust-coro')
        build = {'artifacts': artifacts, 'commands': commands, 'rustflags': rustflags,
                 'cc_version': capture([args.cc, '--version']), 'rust_version': capture(['rustc', '-Vv']),
                 'source_state_observation': {name: source_state(SIBLINGS / name) for name in ['forge', 'forge-runtime', 'forge-stdlib']},
                 'fixture_sha256': {str(p.relative_to(snapshot)): sha(p) for p in snapshot.rglob('*') if p.is_file()},
                 'runner_sha256': sha(Path(__file__)),
                 'binary_sha256': {name: sha(directory / (name + '-coro')) for name in ['forge', 'rust']}}
        (directory / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
    else:
        build = json.loads((directory / 'build.json').read_text())
        for name in ['forge', 'rust']:
            if sha(directory / (name + '-coro')) != build['binary_sha256'][name]:
                raise RuntimeError('Frozen executable changed')
    if args.build_only:
        print('Built immutable coroutine snapshot: ' + str(directory))
        return
    # The package lock identifies the exact downloaded primary policy sources.
    cargo_metadata = json.loads(capture([args.cargo, 'metadata', '--locked', '--offline',
                                        '--format-version', '1', '--manifest-path', str(snapshot / 'Cargo.toml')]))
    tokio_package = next(p for p in cargo_metadata['packages'] if p['name'] == 'tokio')
    tokio_root = Path(tokio_package['manifest_path']).parent
    policies = {'tokio_version': tokio_package['version'],
                'tokio_source_sha256': {name: sha(tokio_root / name) for name in
                                       ['src/task/yield_now.rs', 'src/runtime/builder.rs']},
                'forge_runtime_scheduler_source_sha256_observed': sha(SIBLINGS / 'forge-runtime/src/scheduler.c'),
                'forge_reduction_budget_observed': 2000,
                'native_policy_note': 'Sibling runtime policy source observation; SDK binary artifact hashes remain authoritative'}
    if tokio_package['version'] != '1.53.0':
        raise RuntimeError('Pinned Tokio version changed')
    binaries = {name: directory / (name + '-coro') for name in ['forge', 'rust']}
    checks, warmups, measurements, summary = [], [], [], []
    for workers in args.workers:
        for tasks, rounds, chunk in [(1, 1, 1), (workers + 1, 3, 7), (137, 11, 17)]:
            for name, binary in binaries.items():
                row = run(binary, workers, tasks, rounds, chunk, 71, cpus[:workers])
                checks.append({'language': name, 'workers': workers, 'tasks': tasks,
                               'rounds': rounds, 'chunk': chunk, 'seed': 71, **row})
    rng = random.Random(20261010)
    cases = [(case, workers) for case in CASES for workers in args.workers]
    orders = {key: [False, True] * (args.pairs // 2) for key in cases}
    for order in orders.values(): rng.shuffle(order)
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for pair in range(args.pairs):
        sequence = cases.copy(); rng.shuffle(sequence)
        for case, workers in sequence:
            tasks, rounds, chunk = CASES[case]
            seed = rng.randint(1, 100000)
            order = ['forge', 'rust'] if orders[(case, workers)][pair] else ['rust', 'forge']
            for position, name in enumerate(order):
                for kind in ['prewarm', 'measurement']:
                    row = run(binaries[name], workers, tasks, rounds, chunk, seed, cpus[:workers])
                    record = {'case': case, 'workers': workers, 'pair': pair, 'order': position,
                              'language': name, 'tasks': tasks, 'rounds': rounds, 'chunk': chunk,
                              'seed': seed, **row}
                    (warmups if kind == 'prewarm' else measurements).append(record)
        print('Completed paired iteration ' + str(pair + 1), flush=True)
    for case, workers in cases:
        samples = [r for r in measurements if r['case'] == case and r['workers'] == workers]
        ratios = []
        for pair in range(args.pairs):
            rows = {r['language']: r for r in samples if r['pair'] == pair}
            ratios.append(rows['rust']['kernel_ns'] / rows['forge']['kernel_ns'])
        interval = confidence(ratios, 20261010 + workers)
        summary.append({'case': case, 'workers': workers, 'affinity': cpus[:workers],
                        'tasks': CASES[case][0], 'rounds': CASES[case][1], 'chunk': CASES[case][2],
                        'forge_median_ms': statistics.median(r['kernel_ns'] for r in samples if r['language'] == 'forge') / 1e6,
                        'rust_median_ms': statistics.median(r['kernel_ns'] for r in samples if r['language'] == 'rust') / 1e6,
                        'paired_ratios': ratios, 'paired_ratio_median': statistics.median(ratios), 'ci95': interval,
                        'target_status': 'supported for this configuration' if interval[0] >= 1.10 else 'below target' if interval[1] < 1.10 else 'inconclusive'})
    report = {'started_at_utc': started, 'finished_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'build': build, 'policy_sources': policies, 'measurement_runner_sha256': hashlib.sha256(measurement_source.encode()).hexdigest(), 'measurement_runner_source': measurement_source, 'environment': {'platform': platform.platform(), 'lscpu': capture(['lscpu']),
              'physical_cpu_sets': {str(w): cpus[:w] for w in args.workers}, 'load_average_end': os.getloadavg()},
              'method': {'pairs': args.pairs, 'random_seed': 20261010, 'timing': 'observer allocation + runtime creation + spawn + complete + shutdown + unique-ID validation; excludes parsing/output/observer buffer free',
              'yield_semantics': 'Same explicit yield count; Forge reduction-budget continuation policy and Tokio yield_now are different; no equal context-switch claim',
              'topology': 'Both create exact 1/2/4 OS worker threads restricted to identical physical CPU sets; Both spawn drivers execute on main thread; Forge generated main_init queues tasks before scheduler_run starts workers, Tokio workers start at builder.build before spawning',
              'confidence': '10000 paired-ratio median percentile bootstrap 95%; not family-wise; whole-process RSS can include preexec forked runner',
              'references': ['https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html', 'https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html'],
              'missing_coverage': ['mailbox', 'HTTP', 'I/O readiness', 'cross-machine stability', 'safety guarantees']},
              'correctness_checks': checks, 'warmups': warmups, 'measurements': measurements, 'summary': summary}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Complete-lifecycle coroutine comparison', '',
             'Forge coroutines versus Tokio 1.53.0, measured from observer/runtime creation through spawning, all task completion and runtime shutdown. Every task ID appears exactly once and every final value matches independent Python modular exponentiation. Printing and argument parsing are outside timing.', '',
             '| Case | Physical workers | Forge median ms | Tokio median ms | Throughput ratio (95% interval) | 1.10 target |',
             '| --- | ---: | ---: | ---: | --- | --- |']
    for row in summary:
        lo, hi = row['ci95']; lines.append(f'| {row["case"]} | {row["workers"]} | {row["forge_median_ms"]:.3f} | {row["rust_median_ms"]:.3f} | {row["paired_ratio_median"]:.4f} [{lo:.4f}, {hi:.4f}] | {row["target_status"]} |')
    lines += ['', f'Ratio = Tokio elapsed / Forge elapsed for the same logical work. The ratio column is the median of within-pair ratios, which can differ from dividing the displayed independent medians. Each configuration has {args.pairs} order-balanced paired repetitions with randomized dynamic seeds and checked same-input prewarming. No checksum failure or timing outlier is excluded.', '',
              'Both runtimes use 1/2/4 OS worker threads pinned to the same distinct physical cores. Both spawning drivers run on the main thread. Forge queues tasks in generated main_init before scheduler_run starts its workers; Tokio starts workers during runtime creation, before block_on spawns tasks. The exact generated-C adapter changes only worker count and lifecycle timer boundaries; original/adapted C and hashes are preserved. C provides config, timer and observer storage only; recurrence and logical yields live in FG/Rust.', '',
              'Explicit yields are not equal context switches: Forge can continue within its reduction budget before requeue, while Tokio yield_now has its own cooperative scheduling and [non-guarantees](https://docs.rs/tokio/1.53.0/tokio/task/fn.yield_now.html). Worker configuration uses the [Tokio builder](https://docs.rs/tokio/1.53.0/tokio/runtime/struct.Builder.html). These measure supported scheduler policies and their complete lifecycle, not equivalent dispatch counts or a language-wide performance guarantee.', '',
              'The scheduler-heavy case has 4,000 tasks × 128 yield rounds × 1 recurrence step. Mixed CPU has 4,000 tasks × 64 yield rounds × 256 steps. Budget crossing has 256 tasks × 4,096 yield rounds × 1 step, exceeding the observed Forge reduction budget of 2,000; the first two cases fit within that budget. Integer products remain bounded below signed 64-bit overflow. Results do not cover mailbox throughput, HTTP, I/O readiness or other machines. Shared-host services/frequency and runtime task-allocation differences remain relevant. RSS is a whole-process diagnostic, potentially including the forked Python runner footprint.', '',
              f'Raw samples, source/adapter/lock hashes and flags: [{args.output.name}]({args.output.name}).', '']
    lines += ['', f'Validated SDK input prefix: `{args.sdk}`. Actual compiler/archive/header hashes identify the measured inputs; sibling source observations can postdate their build.', '',
              'Reproduce with that validated SDK and fresh paths:', '', '```sh',
              f'python3 benchmark/coroutine_compare.py --sdk {args.sdk} --build-dir {args.build_dir}-reproduction --output {args.output.with_name(args.output.stem + "-reproduction.json")}',
              '```', '',
              f'Original and adapted C remain in the immutable local `{snapshot}`; the runner regenerates them and validates exact adapter anchors. Original SHA256: `{build["fixture_sha256"]["generated-original.c"]}`. Adapted SHA256: `{build["fixture_sha256"]["generated-adapted.c"]}`.', '',
              'The raw report retains the executed measurement-runner source/hash separately from later documentation edits.', '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__': main()
