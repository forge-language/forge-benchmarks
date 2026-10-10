#!/usr/bin/env python3
"""Same-session paired comparison of frozen native stdlib caller snapshots."""
import argparse
import itertools
import json
import os
import platform
from pathlib import Path
import random
import statistics
import time

from cpu_compare import capture, confidence, reference, run_binary, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--dimensions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--pairs', type=int, default=18)
    parser.add_argument('--random-seed', type=int, default=20261010)
    args = parser.parse_args()
    if args.pairs < 12 or args.pairs % 6:
        parser.error('Choose >=12 pairs divisible by 6 for balanced three-way ordering')
    if args.cpu not in os.sched_getaffinity(0):
        parser.error('CPU must be in allowed affinity')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Report exists; choose a new output')
    builds = {name: json.loads((directory / 'build.json').read_text())
              for name, directory in [('baseline', args.baseline), ('candidate', args.candidate)]}
    for name, directory in [('baseline', args.baseline), ('candidate', args.candidate)]:
        for language in ['forge', 'rust']:
            if sha(directory / (language + '-cpu')) != builds[name]['executables'][language]['sha256']:
                raise RuntimeError('Frozen executable changed: ' + name + '/' + language)
    for artifact in ['compiler', 'runtime']:
        if builds['baseline']['artifacts'][artifact]['sha256'] != builds['candidate']['artifacts'][artifact]['sha256']:
            raise RuntimeError('Compiler/runtime must be identical for this isolated stdlib comparison')
    for name in ['kernels.fg', 'kernels.rs', 'kernels.c', 'clock.c']:
        if builds['baseline']['fixture_sha256'][name] != builds['candidate']['fixture_sha256'][name]:
            raise RuntimeError('Workload/timer fixture differs: ' + name)
    # Reuse exactly one preserved Rust executable for every triple. Rebuilding
    # identical Rust sources under another directory can change embedded paths.
    dimensions = json.loads(args.dimensions.read_text())
    binaries = {'baseline': args.baseline / 'forge-cpu', 'candidate': args.candidate / 'forge-cpu',
                'rust': args.baseline / 'rust-cpu'}
    rng = random.Random(args.random_seed)
    checks, warmups, measurements, summary = [], [], [], []
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for dimension in dimensions['summary']:
        mode, n, rounds = dimension['workload'], dimension['n'], dimension['rounds']
        for small_n, small_rounds, seed in [(1, 1, 1), (31, 3, 17), (127, 2, 719)]:
            expected = reference(mode, small_n, small_rounds, seed)
            for name, binary in binaries.items():
                row = run_binary(binary, mode, small_n, small_rounds, seed, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError('Correctness failure: ' + name + '/' + mode)
                checks.append({'implementation': name, 'workload': mode, 'n': small_n,
                               'rounds': small_rounds, 'seed': seed, **row})
        orders = list(itertools.permutations(binaries)) * (args.pairs // 6)
        rng.shuffle(orders)
        values = {name: [] for name in binaries}
        ratios = {'baseline_over_rust': [], 'candidate_over_rust': [], 'candidate_speedup': []}
        for pair, order in enumerate(orders):
            seed = rng.randint(1, 100000)
            expected = reference(mode, n, rounds, seed)
            paired = {}
            for position, name in enumerate(order):
                for kind in ['prewarm', 'measurement']:
                    row = run_binary(binaries[name], mode, n, rounds, seed, args.cpu)
                    if row['checksum'] != expected:
                        raise RuntimeError('Checksum failure: ' + name + '/' + mode + '/' + kind)
                    record = {'implementation': name, 'workload': mode, 'pair': pair, 'order': position,
                              'n': n, 'rounds': rounds, 'seed': seed, 'reference_checksum': expected, **row}
                    (warmups if kind == 'prewarm' else measurements).append(record)
                    if kind == 'measurement':
                        paired[name] = row['kernel_ns']
                        values[name].append(row['kernel_ns'])
            ratios['baseline_over_rust'].append(paired['rust'] / paired['baseline'])
            ratios['candidate_over_rust'].append(paired['rust'] / paired['candidate'])
            ratios['candidate_speedup'].append(paired['baseline'] / paired['candidate'])
        row = {'workload': mode, 'n': n, 'rounds': rounds, 'pairs': args.pairs,
               'median_ms': {name: statistics.median(samples) / 1e6 for name, samples in values.items()},
               'ratios': {name: {'samples': samples, 'median': statistics.median(samples),
                                 'ci95': confidence(samples, args.random_seed + index)}
                          for index, (name, samples) in enumerate(ratios.items())}}
        low, high = row['ratios']['candidate_over_rust']['ci95']
        row['target_status'] = 'supported for this case' if low >= 1.10 else 'below target' if high < 1.10 else 'inconclusive'
        summary.append(row)
        print(mode + ': candidate speedup=' + str(round(row['ratios']['candidate_speedup']['median'], 4)) +
              ', candidate/Rust=' + str(round(row['ratios']['candidate_over_rust']['median'], 4)), flush=True)
    report = {'started_at_utc': started, 'finished_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'method': {'same_session': True, 'pairs': args.pairs, 'cpu': args.cpu,
                         'random_seed': args.random_seed, 'order': 'All six three-way permutations equally represented, shuffled per workload',
                         'prewarm': 'One checked identical-input invocation immediately before each measured executable',
                         'confidence': '10000 paired-ratio median bootstrap resamples; percentile 95%; not family-wise confidence',
                         'candidate_speedup': 'baseline_kernel_ns / candidate_kernel_ns',
                         'throughput_over_rust': 'rust_kernel_ns / forge_kernel_ns',
                         'dimensions': {'path': str(args.dimensions), 'sha256': sha(args.dimensions)},
                         'limitations': 'One shared Linux host, finite inputs; process RSS includes setup/preexec and is not precise heap usage; no HTTP or safety claim'},
              'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                              'logical_cpus': os.cpu_count(), 'allowed_cpu_affinity': sorted(os.sched_getaffinity(0)),
                              'load_average_end': os.getloadavg(), 'lscpu': capture(['lscpu']),
                              'cpu_governor': Path(f'/sys/devices/system/cpu/cpu{args.cpu}/cpufreq/scaling_governor').read_text().strip() if Path(f'/sys/devices/system/cpu/cpu{args.cpu}/cpufreq/scaling_governor').exists() else None},
              'builds': builds, 'rust_control': builds['baseline']['executables']['rust'], 'correctness_checks': checks, 'warmups': warmups,
              'measurements': measurements, 'summary': summary}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Checked builder-byte inline fast path', '',
             f'Same-session measurement from `{started}` to `{report["finished_at_utc"]}`. Each workload has {args.pairs} randomized, order-balanced triples of baseline, candidate and Rust, with checked same-input prewarming. Compiler/runtime and workload/timer source hashes are identical. The baseline retains checked inline views; the candidate additionally inlines capacity-backed builder byte writes.', '',
             '| Workload | Baseline / Rust | Candidate / Rust (95% interval) | Candidate speedup (95% interval) | 1.10 target |',
             '| --- | ---: | --- | --- | --- |']
    for row in summary:
        b, c, s = (row['ratios'][name] for name in ['baseline_over_rust', 'candidate_over_rust', 'candidate_speedup'])
        lines.append(f'| {row["workload"]} | {b["median"]:.4f} | {c["median"]:.4f} [{c["ci95"][0]:.4f}, {c["ci95"][1]:.4f}] | {s["median"]:.4f} [{s["ci95"][0]:.4f}, {s["ci95"][1]:.4f}] | {row["target_status"]} |')
    if builds['baseline']['artifacts']['stdlib']['sha256'] == builds['candidate']['artifacts']['stdlib']['sha256']:
        lines += ['', 'The native stdlib archive is also byte-for-byte identical between these snapshots. This experiment isolates changes in the checked installed header when compiling callers; it reuses the preserved compiler/runtime rather than attributing concurrent compiler/runtime changes to this optimization.']
    lines += ['', 'Every correctness, prewarm and measured checksum matches an independent Python reference. All samples remain in the raw report. Confidence intervals describe these paired ratios on this host and are not simultaneous confidence over all workloads. The original and earlier different-date view-inline reports remain preserved separately.', '',
              'The fast path preserves exported builder-char symbols and the existing data/length/capacity layout. Invalid bytes and null handles fail, capacity subtraction avoids overflow, and growth delegates to the external ABI. Views/builders still require trusted live arena handles; this is not a general memory-safety guarantee. Snapshots remain immutable copies. Rust and Forge retain their documented allocation lifetime differences.', '',
              'Finite CPU kernels do not establish language-wide 110% throughput, HTTP/application performance, safe vector support, or cross-machine portability. Whole-process RSS is a diagnostic and can include the forked runner before exec.', '',
              f'Raw samples and source/artifact hashes: [{args.output.name}]({args.output.name}).', '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
