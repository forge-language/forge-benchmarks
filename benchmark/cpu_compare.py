#!/usr/bin/env python3
"""Correctness-checked paired native CPU measurements; never a universal speed claim.

Snapshots the compiler, native archives and headers before building. The runner
uses runtime arguments, a shared monotonic timer/one-shot optimization barrier,
warmup, seed-randomized paired execution, and bootstrap confidence intervals.
Requires Linux, Python3, GCC-compatible cc and rustc; it changes no source repo.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS = ROOT.parent
DEFAULTS = {'lcg': 250000, 'primes': 2000, 'scan': 131072, 'builder': 32768, 'immutable': 4096}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True, env=dict(os.environ, GIT_MASTER='1')).strip()


def source_state(root):
    if not (root / '.git').exists():
        return {'path': str(root), 'git': None}
    files = capture(['git', 'ls-files'], root).splitlines()
    hashes = {name: sha(root / name) for name in files
              if (root / name).is_file() and (name.endswith(('.c', '.h', '.fg', '.cmake')) or name.endswith('CMakeLists.txt'))}
    return {'path': str(root), 'head': capture(['git', 'rev-parse', 'HEAD'], root),
            'dirty': capture(['git', 'status', '--porcelain'], root).splitlines(),
            'tracked_source_sha256': hashes}


def stable_copy(source, destination):
    for _ in range(10):
        before = source.stat()
        data = source.read_bytes()
        after = source.stat()
        if (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            shutil.copymode(source, destination)
            return {'original': str(source), 'sha256': hashlib.sha256(data).hexdigest(),
                    'bytes': len(data), 'mtime_ns': before.st_mtime_ns}
        time.sleep(.1)
    raise RuntimeError('Artifact is being rebuilt; retry when builds are idle: ' + str(source))


def weighted_reference(n, seed, offset):
    period = sum((65 + (i + seed) % 26) * ((i + offset) % 13 + 1) for i in range(26))
    return (n // 26) * period + sum((65 + (i + seed) % 26) * ((i + offset) % 13 + 1) for i in range(n % 26))


def reference(mode, n, rounds, seed):
    if mode == 'lcg':
        return seed * pow(48271, n * rounds, 2147483647) % 2147483647
    if mode == 'scan':
        total = seed
        for _ in range(rounds):
            total += weighted_reference(n, seed, total % 13)
        return total
    if mode in ('builder', 'immutable'):
        return sum(weighted_reference(n, seed + r, r % 13) for r in range(rounds))
    if mode == 'primes':
        low = 1000001 + seed
        high = low + n * rounds
        sieve = bytearray(b'\x01') * high
        sieve[:2] = b'\x00\x00'
        for divisor in range(2, math.isqrt(high - 1) + 1):
            if sieve[divisor]:
                begin = divisor * divisor
                count = (high - 1 - begin) // divisor + 1
                sieve[begin:high:divisor] = b'\x00' * count
        return sum(index for index in range(low, high) if sieve[index])
    raise ValueError(mode)


def run_binary(binary, mode, n, rounds, seed, cpu):
    argv = [str(binary), mode, str(n), str(rounds), str(seed)]
    # wait4 supplies per-process RSS/CPU instead of cumulative child max RSS.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        tick = time.perf_counter_ns()
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                 preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
        deadline = time.monotonic() + 60
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            if time.monotonic() > deadline:
                child.kill()
                _, _, _ = os.wait4(child.pid, 0)
                child.returncode = -9
                raise RuntimeError('Timed out: ' + repr(argv))
            time.sleep(.002)
        wall = time.perf_counter_ns() - tick
        stdout.seek(0); output = stdout.read().decode()
        stderr.seek(0); error = stderr.read().decode()
        if child.returncode:
            raise RuntimeError(f'{argv} failed ({child.returncode}): {error} {output}')
        lines = output.strip().splitlines()
        if len(lines) != 2:
            raise RuntimeError('Unexpected benchmark output: ' + repr(output))
        checksum, elapsed = map(int, lines)
        if elapsed <= 0:
            raise RuntimeError('Timer did not advance')
        return {'checksum': checksum, 'kernel_ns': elapsed, 'process_wall_ns': wall,
                'process_user_seconds': usage.ru_utime, 'process_system_seconds': usage.ru_stime,
                'process_peak_rss_kib': usage.ru_maxrss}


def confidence(ratios, random_seed):
    rng = random.Random(random_seed)
    values = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(10000))
    return [values[int(.025 * len(values))], values[int(.975 * len(values))]]


def markdown(report):
    lines = ['# Native Forge / Rust CPU comparison', '',
             f"Recorded at `{report['recorded_at_utc']}`. Ratio = Rust elapsed / Forge elapsed for the same work; >=1.10 means at least 110% of Rust throughput on this case.", '',
             '| Workload | n × rounds | Forge median ms | Rust median ms | Paired ratio median | Bootstrap 95% interval | 1.10 threshold |',
             '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for row in report['summary']:
        low, high = row['paired_ratio_ci95']
        lines.append(f"| {row['workload']} | {row['n']} × {row['rounds']} | {row['forge_median_ms']:.3f} | {row['rust_median_ms']:.3f} | {row['paired_ratio_median']:.4f} | [{low:.4f}, {high:.4f}] | {row['target_status']} |")
    lines += ['', 'Each measured output matches an independent Python reference (modular exponentiation, sieve of Eratosthenes, or periodic weighted-sum formula). No checksum failure is excluded or silently retried.', '',
              'Both executables use identical runtime n/rounds/seed arguments and a common C monotonic-clock primitive plus one-shot input/output optimization barriers. There is no C implementation of a measured algorithm. The report preserves every paired sample, warmup, calibration choice, source/artifact hash, compiler command and environment detail.', '',
              'Builds use GCC -O3 and Rust opt-level=3, native CPU tuning and explicit LTO settings. Forge native runtime/stdlib archives are taken from the specified existing Release build; their non-LTO C functions may remain out of line, while Rust standard-library methods can inline. This comparison measures these implementations and supported public APIs rather than isolating a language syntax cost.', '',
              'String builder and immutable append create the same ASCII bytes and final weighted checksum. Rust builder output includes a final clone to match Forge\'s immutable snapshot. Forge arena allocation retains intermediate strings until the explicit reset; Rust drops obsolete owned strings earlier. Cleanup is inside the timed rounds for builder/immutable, outside timing for the prebuilt scan input. The process RSS includes setup, allocator retention and runtime startup.', '',
              'This small CPU suite does not cover typed arrays/vectors (not currently available in the tested Forge frontend), concurrency, HTTP, database I/O, safety guarantees, large applications or cross-machine portability. Shared host services and frequency scheduling remain sources of noise despite CPU affinity and paired randomized order. A bootstrap interval describes this run, not universal performance. Passing one row cannot establish a language-wide 110% guarantee.', '',
              'The repeated seeds are runtime inputs and output-dependent arithmetic prevents replacing the work with a printed constant. Timed instructions include mode dispatch and a few common observer calls; process startup, command parsing, output formatting and prebuilt scan input construction are excluded. Full process wall/CPU/RSS are separate diagnostics.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forge', type=Path, default=SIBLINGS / 'forge/build/bin/forge')
    parser.add_argument('--forge-root', type=Path, default=SIBLINGS / 'forge')
    parser.add_argument('--runtime-library', type=Path, default=SIBLINGS / 'forge/build/lib/libforge_runtime.a')
    parser.add_argument('--stdlib-library', type=Path, default=SIBLINGS / 'forge/build/lib/libforge_std.a')
    parser.add_argument('--runtime-root', type=Path, default=SIBLINGS / 'forge-runtime')
    parser.add_argument('--stdlib-root', type=Path, default=SIBLINGS / 'forge-stdlib')
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build-cpu-comparison')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/cpu-rust-forge-2026-10-09.json')
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--rustc', default='rustc')
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--pairs', type=int, default=15)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--min-fast-ms', type=float, default=50)
    parser.add_argument('--max-slow-ms', type=float, default=500)
    parser.add_argument('--random-seed', type=int, default=20261009)
    parser.add_argument('--workloads', nargs='+', choices=list(DEFAULTS), default=list(DEFAULTS))
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-snapshot', action='store_true')
    args = parser.parse_args()
    if args.cpu not in os.sched_getaffinity(0) or args.pairs < 7 or args.warmup < 1 or args.min_fast_ms <= 0 or args.max_slow_ms < args.min_fast_ms:
        parser.error('Choose an allowed CPU, >=7 pairs, >=1 warmup, and valid timing targets')
    directory = args.build_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / 'snapshot'
    metadata = directory / 'build.json'
    if not args.reuse_snapshot:
        if snapshot.exists():
            parser.error('Snapshot already exists; use a fresh --build-dir or --reuse-snapshot')
        (snapshot / 'include').mkdir(parents=True)
        artifacts = {'compiler': stable_copy(args.forge.resolve(), snapshot / 'forge'),
                     'runtime': stable_copy(args.runtime_library.resolve(), snapshot / 'libforge_runtime.a'),
                     'stdlib': stable_copy(args.stdlib_library.resolve(), snapshot / 'libforge_std.a')}
        for source in [args.runtime_root / 'include', args.stdlib_root / 'include']:
            shutil.copytree(source, snapshot / 'include', dirs_exist_ok=True)
        header_hashes = {str(file.relative_to(snapshot / 'include')): sha(file) for file in (snapshot / 'include').rglob('*') if file.is_file()}
        for name in ['kernels.fg', 'kernels.rs', 'clock.c']:
            shutil.copyfile(ROOT / 'benchmark/cpu' / name, snapshot / name)
        commands = [
            [str(snapshot / 'forge'), str(snapshot / 'kernels.fg'), '--emit-c', '-o', str(snapshot / 'kernels.c'), '--forge-root', str(snapshot)],
            [args.cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto', '-I', str(snapshot / 'include'), str(snapshot / 'kernels.c'), str(snapshot / 'clock.c'), '-Wl,--start-group', str(snapshot / 'libforge_std.a'), str(snapshot / 'libforge_runtime.a'), '-Wl,--end-group', '-lpthread', '-lm', '-o', str(directory / 'forge-cpu')],
            [args.cc, '-std=gnu11', '-O3', '-march=native', '-c', str(snapshot / 'clock.c'), '-o', str(snapshot / 'clock.o')],
            [args.rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'lto=thin', '-C', 'codegen-units=1', '-C', 'overflow-checks=off', '-C', 'link-arg=' + str(snapshot / 'clock.o'), str(snapshot / 'kernels.rs'), '-o', str(directory / 'rust-cpu')],
        ]
        for command in commands:
            subprocess.run(command, check=True)
        build = {'artifacts': artifacts, 'header_sha256': header_hashes, 'commands': commands,
                 'source_state': {name: source_state(root) for name, root in [('forge', args.forge_root), ('runtime', args.runtime_root), ('stdlib', args.stdlib_root)]},
                 'fixture_sha256': {name: sha(snapshot / name) for name in ['kernels.fg', 'kernels.rs', 'kernels.c', 'clock.c']},
                 'executables': {language: {'path': str(directory / (language + '-cpu')), 'sha256': sha(directory / (language + '-cpu'))} for language in ['forge', 'rust']},
                 'cc_version': capture([args.cc, '--version']).splitlines()[0], 'rust_version': capture([args.rustc, '--version'])}
        metadata.write_text(json.dumps(build, indent=2) + '\n')
    else:
        build = json.loads(metadata.read_text())
        for language in ['forge', 'rust']:
            if sha(directory / (language + '-cpu')) != build['executables'][language]['sha256']:
                raise RuntimeError('Snapshot executable changed')
    if args.build_only:
        print('Immutable benchmark snapshot built: ' + str(directory))
        return
    binaries = {name: directory / (name + '-cpu') for name in ['forge', 'rust']}
    correctness = []
    for mode in args.workloads:
        for n, rounds, seed in [(1, 1, 1), (31, 3, 17), (127, 2, 719)]:
            expected = reference(mode, n, rounds, seed)
            for name, binary in binaries.items():
                row = run_binary(binary, mode, n, rounds, seed, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError(f'Correctness mismatch {name}/{mode}: {row} expected {expected}')
                correctness.append({'implementation': name, 'workload': mode, 'n': n, 'rounds': rounds, 'seed': seed, **row})
    rng = random.Random(args.random_seed)
    measurements, calibration, warmups, summary = [], [], [], []
    for mode in args.workloads:
        n = DEFAULTS[mode]
        rounds = 1
        while True:
            trial = {name: run_binary(binary, mode, n, rounds, 719, args.cpu) for name, binary in binaries.items()}
            expected = reference(mode, n, rounds, 719)
            if any(row['checksum'] != expected for row in trial.values()):
                raise RuntimeError('Calibration checksum mismatch')
            calibration.append({'workload': mode, 'n': n, 'rounds': rounds, 'samples': trial})
            fastest = min(row['kernel_ns'] for row in trial.values()) / 1e6
            slowest = max(row['kernel_ns'] for row in trial.values()) / 1e6
            if fastest >= args.min_fast_ms or slowest >= args.max_slow_ms or rounds >= 4096 or (mode == 'primes' and n * rounds >= 2000000):
                break
            rounds *= 2
        for index in range(args.warmup):
            order = ['forge', 'rust']; rng.shuffle(order)
            for name in order:
                row = run_binary(binaries[name], mode, n, rounds, 719, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError('Warmup checksum mismatch')
                warmups.append({'implementation': name, 'workload': mode, 'index': index, 'n': n, 'rounds': rounds, 'seed': 719, **row})
        ratios, forge_ns, rust_ns = [], [], []
        for pair in range(args.pairs):
            seed = rng.randint(1, 100000)
            expected = reference(mode, n, rounds, seed)
            order = ['forge', 'rust']; rng.shuffle(order)
            paired = {}
            for position, name in enumerate(order):
                row = run_binary(binaries[name], mode, n, rounds, seed, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError(f'Measured checksum mismatch {name}/{mode}: {row} expected {expected}')
                paired[name] = row['kernel_ns']
                measurements.append({'implementation': name, 'workload': mode, 'pair': pair, 'order': position, 'n': n, 'rounds': rounds, 'seed': seed, 'reference_checksum': expected, **row})
            ratio = paired['rust'] / paired['forge']
            ratios.append(ratio); forge_ns.append(paired['forge']); rust_ns.append(paired['rust'])
        interval = confidence(ratios, args.random_seed + len(summary))
        summary.append({'workload': mode, 'n': n, 'rounds': rounds, 'pairs': args.pairs,
                        'forge_median_ms': statistics.median(forge_ns) / 1e6, 'rust_median_ms': statistics.median(rust_ns) / 1e6,
                        'paired_ratios': ratios, 'paired_ratio_median': statistics.median(ratios), 'paired_ratio_ci95': interval,
                        'target_status': 'supported for this case' if interval[0] >= 1.10 else 'below target' if interval[1] < 1.10 else 'inconclusive',
                        'fastest_calibration_ms': fastest, 'slowest_calibration_ms': slowest})
        print(mode + ': paired median Forge/Rust throughput=' + str(round(summary[-1]['paired_ratio_median'], 4)), flush=True)
    report = {'recorded_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'build': build,
              'environment': {'platform': platform.platform(), 'python': platform.python_version(), 'logical_cpus': os.cpu_count(), 'cpu_affinity': args.cpu,
                              'allowed_cpu_affinity': sorted(os.sched_getaffinity(0)), 'load_average_end': os.getloadavg(),
                              'lscpu': capture(['lscpu']), 'cpu_governor': Path(f'/sys/devices/system/cpu/cpu{args.cpu}/cpufreq/scaling_governor').read_text().strip() if Path(f'/sys/devices/system/cpu/cpu{args.cpu}/cpufreq/scaling_governor').exists() else None},
              'method': {'throughput_ratio': 'rust_kernel_ns / forge_kernel_ns', 'target_ratio': 1.10, 'pairs': args.pairs, 'warmup_per_language': args.warmup,
                         'random_seed': args.random_seed, 'confidence': '10000 paired-ratio bootstrap resamples; median percentile interval; not family-wise confidence',
                         'timing': 'shared CLOCK_MONOTONIC C primitive; one-shot input/output optimization barriers; no per-operation black_box',
                         'calibration': {'min_fast_ms': args.min_fast_ms, 'max_slow_ms': args.max_slow_ms},
                         'missing_coverage': ['typed arrays/vectors', 'concurrency', 'HTTP', 'database I/O', 'cross-machine stability', 'safety guarantees']},
              'correctness_checks': correctness, 'calibration': calibration, 'warmups': warmups, 'measurements': measurements, 'summary': summary}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    args.output.with_suffix('.md').write_text(markdown(report))
    print('Raw report: ' + str(args.output))


if __name__ == '__main__':
    main()
