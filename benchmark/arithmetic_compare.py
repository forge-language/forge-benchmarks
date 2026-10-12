#!/usr/bin/env python3
"""Paired dynamic-divisor distributions: frozen Forge, candidate Forge, Rust.

All three use the same runtime arguments, C clock and one-shot barriers. The
Forge variants link the same frozen SDK, isolating the compiler change. This
microbenchmark diagnoses division guard tradeoffs; it is not representative
application coverage or a universal language speed claim.
"""
import argparse
import itertools
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

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTIONS = {
    'unsigned32': (0, 1, 0), 'negative32': (0, -1, 0), 'mixed32': (0, 1, 1),
    'positive64': (1 << 40, 1, 0), 'negative64': (1 << 40, -1, 0),
    'mixed64': (1 << 40, 1, 1), 'affine_lcg': (1, 1, 2),
}
NAMES = ['baseline', 'candidate', 'rust']


def arguments(mode, n, seed):
    offset, sign, alternate = DISTRIBUTIONS[mode]
    return [n, offset + seed, seed % 65521 + 1, sign, alternate]


def reference(values):
    n, a, b, sign, alternate = values
    if alternate == 2:
        if n <= 0:
            return a
        # Exponentiate the affine map f(x)=48271*x+1 modulo 2^31-1.
        result_mul, result_add = 1, 0
        base_mul, base_add = 48271, 1
        steps = n
        while steps:
            if steps & 1:
                result_add = (base_mul * result_add + base_add) % 2147483647
                result_mul = (base_mul * result_mul) % 2147483647
            base_add = (base_mul * base_add + base_add) % 2147483647
            base_mul = (base_mul * base_mul) % 2147483647
            steps >>= 1
        return (result_mul * (a % 2147483647) + result_add) % 2147483647
    total = 0
    for _ in range(n):
        # Independent integer oracle: abs/floor plus explicit sign implements
        # truncation toward zero, including the negative remainder contract.
        value = a * sign
        quotient = abs(value) // b * (-1 if value < 0 else 1)
        total += quotient + value - quotient * b
        a += 17
        b = (b + 11) % 65521 + 1
        if alternate:
            sign = -sign
    return (total + (1 << 63)) % (1 << 64) - (1 << 63)


def run(binary, values, cpu):
    command = [str(binary), *map(str, values)]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        tick = time.perf_counter_ns()
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
        deadline = time.monotonic() + 60
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            if time.monotonic() > deadline:
                child.kill(); os.wait4(child.pid, 0); child.returncode = -9
                raise RuntimeError('Timed out: ' + repr(command))
            time.sleep(.002)
        elapsed = time.perf_counter_ns() - tick
        stdout.seek(0); output = stdout.read().decode()
        stderr.seek(0); error = stderr.read().decode()
        if child.returncode:
            raise RuntimeError(f'{command} failed ({child.returncode}): {error} {output}')
        lines = output.strip().splitlines()
        if len(lines) != 2:
            raise RuntimeError('Unexpected output: ' + repr(output))
        checksum, kernel_ns = map(int, lines)
        if kernel_ns <= 0:
            raise RuntimeError('Timer did not advance')
        return {'checksum': checksum, 'kernel_ns': kernel_ns,
                'process_wall_ns': elapsed, 'process_user_seconds': usage.ru_utime,
                'process_system_seconds': usage.ru_stime, 'process_peak_rss_kib': usage.ru_maxrss}


def markdown(report):
    affine = any(row['distribution'] == 'affine_lcg' for row in report['summary'])
    lines = ['# Arithmetic compiler comparison', '',
             'Compiler diagnostic microbenchmark. Ratios are elapsed baseline / candidate and Rust / candidate for identical work. A value above 1 means faster candidate throughput.', '',
             '| Distribution | Baseline ms | Candidate ms | Rust ms | Baseline/candidate median [95% CI] | Rust/candidate median [95% CI] |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in report['summary']:
        improvement = row['baseline_candidate']; rust = row['rust_candidate']
        lines.append(f"| {row['distribution']} | {row['median_ms']['baseline']:.3f} | {row['median_ms']['candidate']:.3f} | {row['median_ms']['rust']:.3f} | {improvement['median']:.4f} [{improvement['ci95'][0]:.4f}, {improvement['ci95'][1]:.4f}] | {rust['median']:.4f} [{rust['ci95'][0]:.4f}, {rust['ci95'][1]:.4f}] |")
    if report.get('extra_variants'):
        lines += ['', '| Distribution | Prototype | Baseline speedup [95% CI] | Rust/prototype [95% CI] |',
                  '| --- | --- | ---: | ---: |']
        for row in report['summary']:
            for name in report['extra_variants']:
                gain, ratio = row['baseline_' + name], row['rust_' + name]
                lines.append(f'| {row["distribution"]} | {name} | {gain["median"]:.4f} [{gain["ci95"][0]:.4f}, {gain["ci95"][1]:.4f}] | {ratio["median"]:.4f} [{ratio["ci95"][0]:.4f}, {ratio["ci95"][1]:.4f}] |')
    lines += ['', f"{report['method']['iterations']} iterations per sample, {report['method']['pairs']} measured groups. Protocol: {report['method']['protocol']}. Every timed sample follows a same-input prewarm and matches the independent Python oracle. All raw samples, warmups, arguments, hashes and compiler commands are retained in the JSON report.", '',
              ('The affine_lcg workload applies value = (value * 48271 + 1) % 2147483647 for each iteration from a positive runtime seed. The candidate compiler lowers this source expression through a guarded Mersenne multiply-add fold, with the exact wrapping multiply-add and signed remainder as the fallback. Rust uses explicit wrapping multiplication and addition. The independent oracle exponentiates the affine map modulo 2^31-1, avoiding a second iterative implementation.' if affine else 'Each iteration calculates signed quotient and remainder of the same dynamic dividend/divisor, accumulates both, advances the dividend by 17 and updates the divisor with (b + 11) % 65521 + 1. Compilers can share quotient/remainder work. Divisors stay positive; negative and mixed distributions vary dividend sign. Narrow magnitudes fit uint32 for all allowed iteration counts; wide magnitudes exceed uint32. This diagnoses narrowing-guard cost and benefit; it does not cover independent divide-only/remainder-only workloads or every divisor distribution.'), '',
              'Both Forge compilers link exactly the same frozen native archives and headers. GCC -O3, native tuning and LTO are matched by Rust opt-level=3, native tuning, thin LTO and one codegen unit; Rust updates explicitly wrap to match Forge. Input/output barriers occur outside the loop. Parser, startup and output time are excluded from kernel timing. RSS is whole-process wait4 information, including possible pre-exec runner footprint; it is not a precise language heap measurement.', '',
              'Shared-host scheduling/frequency noise remains despite affinity and balanced order. Bootstrap intervals are per-row median estimates from this run and are not family-wise confidence or a universal 110% guarantee. No result is discarded or retried after a checksum failure.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forge-root', type=Path, default=ROOT.parent / 'forge')
    parser.add_argument('--forge', type=Path, default=ROOT.parent / 'forge/build/bin/forge')
    parser.add_argument('--baseline-snapshot', type=Path, default=ROOT / 'build-cpu-baseline-20261011/snapshot')
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build-arithmetic-comparison')
    parser.add_argument('--output', type=Path, default=ROOT / ('docs/arithmetic-rust-forge-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json'))
    parser.add_argument('--cc', default='cc'); parser.add_argument('--rustc', default='rustc')
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--pairs', type=int, default=12)
    parser.add_argument('--iterations', type=int, default=8000000)
    parser.add_argument('--random-seed', type=int, default=20261012)
    parser.add_argument('--workloads', nargs='+', choices=list(DISTRIBUTIONS), default=list(DISTRIBUTIONS))
    parser.add_argument('--extra-variant', action='append', default=[], metavar='NAME=BINARY',
                        help='Frozen diagnostic prototype with adjacent BINARY.json provenance')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--check-only', action='store_true', help='Validate small oracle cases without measured groups')
    parser.add_argument('--reuse-snapshot', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    names = NAMES.copy()
    extras = {}
    for value in args.extra_variant:
        name, path = value.split('=', 1)
        if name in names:
            parser.error('Extra names must be unique')
        binary = Path(path).resolve()
        metadata_path = binary.with_suffix('.json')
        extras[name] = {'path': str(binary), 'sha256': sha(binary),
                        'provenance': json.loads(metadata_path.read_text()),
                        'provenance_sha256': sha(metadata_path)}
        names.append(name)
    if args.cpu not in os.sched_getaffinity(0) or args.pairs < 6 or args.pairs % 6:
        parser.error('Choose an allowed CPU and >=6 pairs divisible by six')
    if extras and args.pairs % len(names):
        parser.error('Extra-variant comparisons require pairs divisible by implementation count')
    if not 1 <= args.iterations <= 100000000:
        parser.error('Iterations must be 1..100000000 (keeps narrow magnitudes in uint32)')
    if not args.build_only and not args.check_only and not args.overwrite and (args.output.exists() or args.output.with_suffix('.md').exists()):
        parser.error('Report exists; choose a new --output or explicitly use --overwrite')
    directory = args.build_dir.resolve(); directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / 'snapshot'; metadata = directory / 'build.json'
    if not args.reuse_snapshot:
        if snapshot.exists():
            parser.error('Snapshot exists; use a fresh --build-dir or --reuse-snapshot')
        snapshot.mkdir()
        original = args.baseline_snapshot.resolve()
        sdk_layout = (original / 'bin/forge').exists()
        baseline_compiler = original / ('bin/forge' if sdk_layout else 'forge')
        artifacts = {'baseline_compiler': stable_copy(baseline_compiler, snapshot / 'baseline-forge'),
                     'candidate_compiler': stable_copy(args.forge.resolve(), snapshot / 'candidate-forge')}
        for name in ('libforge_runtime.a', 'libforge_std.a'):
            artifacts[name] = stable_copy(original / ('lib' if sdk_layout else '') / name, snapshot / name)
        shutil.copytree(original / 'include', snapshot / 'include')
        for name in ('kernels.fg', 'kernels.rs', 'observer.c'):
            shutil.copyfile(ROOT / 'benchmark/arithmetic' / name, snapshot / name)
        commands = []
        for implementation in ('baseline', 'candidate'):
            source = snapshot / (implementation + '.c')
            commands += [[str(snapshot / (implementation + '-forge')), str(snapshot / 'kernels.fg'), '--emit-c', '-o', str(source), '--forge-root', str(snapshot)],
                         [args.cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto', '-I', str(snapshot / 'include'), str(source), str(snapshot / 'observer.c'), '-Wl,--start-group', str(snapshot / 'libforge_std.a'), str(snapshot / 'libforge_runtime.a'), '-Wl,--end-group', '-lpthread', '-lm', '-o', str(directory / implementation)]]
        commands += [[args.cc, '-std=gnu11', '-O3', '-march=native', '-c', str(snapshot / 'observer.c'), '-o', str(snapshot / 'observer.o')],
                     [args.rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'lto=thin', '-C', 'codegen-units=1', '-C', 'overflow-checks=off', '-C', 'link-arg=' + str(snapshot / 'observer.o'), str(snapshot / 'kernels.rs'), '-o', str(directory / 'rust')]]
        for command in commands:
            subprocess.run(command, check=True)
        frozen_metadata = original / 'provenance.json' if sdk_layout else original.parent / 'build.json'
        build = {'artifacts': artifacts, 'commands': commands,
                 'candidate_compiler_source_state': source_state(args.forge_root),
                 'baseline_build': json.loads(frozen_metadata.read_text()) if frozen_metadata.exists() else None,
                 'runner_sha256': sha(__file__),
                 'header_sha256': {str(file.relative_to(snapshot / 'include')): sha(file) for file in (snapshot / 'include').rglob('*') if file.is_file()},
                 'fixture_sha256': {name: sha(snapshot / name) for name in ('kernels.fg', 'kernels.rs', 'observer.c', 'baseline.c', 'candidate.c')},
                 'executables': {name: {'path': str(directory / name), 'sha256': sha(directory / name)} for name in NAMES},
                 'cc_version': capture([args.cc, '--version']).splitlines()[0], 'rust_version': capture([args.rustc, '--version'])}
        metadata.write_text(json.dumps(build, indent=2) + '\n')
    else:
        build = json.loads(metadata.read_text())
        for name in NAMES:
            if sha(directory / name) != build['executables'][name]['sha256']:
                raise RuntimeError('Snapshot executable changed: ' + name)
    if args.build_only:
        print('Immutable arithmetic snapshot built: ' + str(directory)); return
    binaries = {name: directory / name for name in NAMES}
    binaries.update({name: Path(data['path']) for name, data in extras.items()})
    checks = []; warmups = []; measurements = []; summary = []
    for mode in args.workloads:
        for n, seed in ((1, 1), (31, 17), (257, 719)):
            values = arguments(mode, n, seed); expected = reference(values)
            for name in names:
                result = run(binaries[name], values, args.cpu)
                if result['checksum'] != expected:
                    raise RuntimeError(f'Correctness mismatch: {mode}/{name}')
                checks.append({'distribution': mode, 'implementation': name, 'arguments': values, 'reference_checksum': expected, **result})
    if args.check_only:
        (directory / 'correctness.json').write_text(json.dumps(checks, indent=2) + '\n')
        print(f'{len(checks)} small oracle checks passed; no measured groups run'); return
    rng = random.Random(args.random_seed)
    for mode in args.workloads:
        if extras:
            orders = [names[i:] + names[:i] for i in range(len(names))] * (args.pairs // len(names))
        else:
            orders = list(itertools.permutations(NAMES)) * (args.pairs // 6)
        rng.shuffle(orders)
        times = {name: [] for name in names}
        candidates = ['candidate', *extras]
        ratios = {key: [] for name in candidates for key in ['baseline_' + name, 'rust_' + name]}
        for pair, order in enumerate(orders):
            seed = rng.randint(1, 100000); values = arguments(mode, args.iterations, seed)
            expected = reference(values); paired = {}
            for position, name in enumerate(order):
                prewarm = run(binaries[name], values, args.cpu)
                if prewarm['checksum'] != expected:
                    raise RuntimeError(f'Prewarm mismatch: {mode}/{name}/{pair}')
                warmups.append({'distribution': mode, 'implementation': name, 'pair': pair, 'order': position, 'arguments': values, 'reference_checksum': expected, **prewarm})
                result = run(binaries[name], values, args.cpu)
                if result['checksum'] != expected:
                    raise RuntimeError(f'Measured mismatch: {mode}/{name}/{pair}')
                paired[name] = result['kernel_ns']; times[name].append(result['kernel_ns'])
                measurements.append({'distribution': mode, 'implementation': name, 'pair': pair, 'order': position, 'arguments': values, 'reference_checksum': expected, **result})
            for name in candidates:
                ratios['baseline_' + name].append(paired['baseline'] / paired[name])
                ratios['rust_' + name].append(paired['rust'] / paired[name])
        row = {'distribution': mode, 'median_ms': {name: statistics.median(times[name]) / 1e6 for name in names}}
        for index, (name, values) in enumerate(ratios.items()):
            row[name] = {'ratios': values, 'median': statistics.median(values), 'ci95': confidence(values, args.random_seed + len(summary) * 2 + index)}
        summary.append(row)
        print(mode + ': baseline/candidate=' + str(round(row['baseline_candidate']['median'], 4)) + ' Rust/candidate=' + str(round(row['rust_candidate']['median'], 4)), flush=True)
    report = {'recorded_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'build': build,
              'extra_variants': extras, 'executed_runner_source': Path(__file__).read_text(),
              'environment': {'platform': platform.platform(), 'python': platform.python_version(), 'logical_cpus': os.cpu_count(), 'cpu_affinity': args.cpu, 'allowed_cpu_affinity': sorted(os.sched_getaffinity(0)), 'load_average_end': os.getloadavg(), 'lscpu': capture(['lscpu'])},
              'method': {'protocol': 'prewarmed position-balanced cyclic rotations; adjacency not fully balanced' if extras else 'three-way prewarmed balanced all permutations', 'iterations': args.iterations, 'pairs': args.pairs, 'random_seed': args.random_seed, 'target_ratio': 1.10, 'ratio': 'reference_kernel_ns / candidate_kernel_ns', 'confidence': '10000 median bootstrap resamples; per-row percentile interval', 'timing': 'shared CLOCK_MONOTONIC C primitive; one-shot barriers outside loop', 'frozen_native_sdk': str(args.baseline_snapshot), 'missing_coverage': ['divide-only', 'remainder-only', 'negative divisor distributions', 'cross-machine stability', 'application throughput']},
              'correctness_checks': checks, 'warmups': warmups, 'measurements': measurements, 'summary': summary}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n'); args.output.with_suffix('.md').write_text(markdown(report))
    print('Raw report: ' + str(args.output))


if __name__ == '__main__':
    main()
