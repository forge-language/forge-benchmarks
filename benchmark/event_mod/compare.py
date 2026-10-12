#!/usr/bin/env python3
"""Paired Linux event-loop modification benchmark for Forge runtime and Rust epoll."""
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
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(binary, operations, cpu):
    def pin():
        os.sched_setaffinity(0, {cpu})
    result = subprocess.run([str(binary), str(operations)], text=True,
                            capture_output=True, check=True, timeout=30,
                            preexec_fn=pin)
    fields = result.stdout.split()
    if len(fields) != 2 or int(fields[1]) != operations:
        raise RuntimeError(f"invalid benchmark output from {binary}: {result.stdout!r}")
    return int(fields[0])


def ci95(values, rng, resamples=10000):
    medians = [statistics.median(rng.choices(values, k=len(values)))
               for _ in range(resamples)]
    medians.sort()
    return [medians[int(.025 * resamples)], medians[int(.975 * resamples)]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-library', type=Path, required=True)
    parser.add_argument('--candidate-library', type=Path, required=True)
    parser.add_argument('--runtime-include', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--operations', type=int, default=100000)
    parser.add_argument('--pairs', type=int, default=48)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--seed', type=int, default=20261013)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('This comparison uses Linux eventfd and epoll')
    if args.cpu not in os.sched_getaffinity(0) or args.pairs < 12 or args.pairs % 3:
        parser.error('Choose an allowed CPU and >=12 pairs divisible by three')
    if not 1 <= args.operations <= 100000000:
        parser.error('--operations must be between 1 and 100000000')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Output exists; use a fresh output path')
    if args.build_dir.exists():
        parser.error('Build directory exists; use a fresh directory')

    args.build_dir.mkdir(parents=True)
    cc = shutil.which('cc') or 'cc'
    rustc = shutil.which('rustc') or 'rustc'
    forge_src = ROOT / 'benchmark/event_mod/forge.c'
    rust_src = ROOT / 'benchmark/event_mod/rust.rs'
    clock_src = ROOT / 'benchmark/cpu/clock.c'
    runtime_root = ROOT.parent / 'forge-runtime'
    runtime_sources = [runtime_root / 'CMakeLists.txt', runtime_root / 'src/event_loop.c',
                       runtime_root / 'tests/event_loop_test.c']
    clock_obj = args.build_dir / 'clock.o'
    subprocess.run([cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-c',
                    str(clock_src), '-o', str(clock_obj)], check=True)
    binaries = {}
    for name, library in [('base', args.baseline_library.resolve()),
                          ('candidate', args.candidate_library.resolve())]:
        binary = args.build_dir / name
        subprocess.run([cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native',
                        '-I', str(args.runtime_include.resolve()), str(forge_src),
                        str(clock_obj), str(library), '-pthread', '-o', str(binary)], check=True)
        binaries[name] = binary
    binaries['rust'] = args.build_dir / 'rust'
    subprocess.run([rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native',
                    '-C', 'overflow-checks=off', '-C', f'link-arg={clock_obj}',
                    str(rust_src), '-o', str(binaries['rust'])], check=True)

    order_rng = random.Random(args.seed)
    names = list(binaries)
    orders = [names[i:] + names[:i] for i in range(len(names))] * (args.pairs // len(names))
    order_rng.shuffle(orders)
    raw, warmups, pairs = [], [], []
    elapsed = {name: [] for name in names}
    throughput = {name: [] for name in ('base', 'candidate')}
    speedup = {name: [] for name in ('base', 'candidate')}
    for pair_id, order in enumerate(orders):
        samples = {}
        for position, name in enumerate(order):
            warm_ns = run(binaries[name], args.operations, args.cpu)
            sample_ns = run(binaries[name], args.operations, args.cpu)
            warmups.append(dict(implementation=name, pair=pair_id, position=position,
                                operations=args.operations, elapsed_ns=warm_ns))
            raw.append(dict(implementation=name, pair=pair_id, position=position,
                            operations=args.operations, elapsed_ns=sample_ns))
            samples[name] = sample_ns
            elapsed[name].append(sample_ns)
        pairs.append(samples)
        for name in ('base', 'candidate'):
            throughput[name].append(samples['rust'] / samples[name])
            speedup[name].append(samples['base'] / samples[name])

    ci_rng = random.Random(args.seed + 1)
    summary = {}
    for name in names:
        values = [args.operations * 1e9 / ns for ns in elapsed[name]]
        summary[name] = dict(median_ops_per_second=statistics.median(values),
                             median_elapsed_ns=statistics.median(elapsed[name]))
    relative = {}
    for name, values in throughput.items():
        relative[name] = dict(median=statistics.median(values), ci95=ci95(values, ci_rng))
    candidate_speedup = dict(median=statistics.median(speedup['candidate']),
                             ci95=ci95(speedup['candidate'], ci_rng))

    report = dict(description='Registered-fd FR_EVENT_READ modification throughput: Forge public event API versus direct Rust epoll_ctl(MOD).',
                  method=dict(operations=args.operations, pairs=args.pairs, cpu=args.cpu,
                              random_seed=args.seed, ordering='shuffled cyclic rotations balance ordinal positions',
                              warmup='one correctness-checked process per implementation per pair',
                              timing='shared CLOCK_MONOTONIC timer around only repeated MOD calls; setup and readiness validation excluded',
                              confidence='paired median bootstrap percentile 95% interval, per comparison'),
                  environment=dict(platform=platform.platform(), python=platform.python_version(),
                                   allowed_affinity=sorted(os.sched_getaffinity(0))),
                  artifacts={name: dict(path=str(path), sha256=sha(path)) for name, path in binaries.items()},
                  runner=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  source_sha256={str(path.relative_to(ROOT)): sha(path) for path in (forge_src, rust_src, clock_src)},
                  runtime_source_sha256={str(path): sha(path) for path in runtime_sources if path.exists()},
                  library_sha256={'baseline': sha(args.baseline_library), 'candidate': sha(args.candidate_library)},
                  results=summary, forge_over_rust=relative,
                  candidate_over_base=candidate_speedup, warmups=warmups, measurements=raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Forge event-loop modification benchmark', '', report['description'], '',
             f"{args.pairs} paired samples, {args.operations:,} successful updates per sample, pinned to CPU {args.cpu}.", '',
             '| Implementation | Median updates/s | Median time (ms) | Forge/Rust throughput |',
             '| --- | ---: | ---: | ---: |']
    for name in names:
        ratio = relative[name]['median'] if name in relative else 1.0
        lines.append(f"| {name} | {summary[name]['median_ops_per_second']:,.0f} | {summary[name]['median_elapsed_ns']/1e6:.3f} | {ratio:.4f}x |")
    lines += ['', f"Candidate/base paired speedup: {candidate_speedup['median']:.4f}x [{candidate_speedup['ci95'][0]:.4f}, {candidate_speedup['ci95'][1]:.4f}].",
              f"Forge/Rust paired throughput: base {relative['base']['median']:.4f}x [{relative['base']['ci95'][0]:.4f}, {relative['base']['ci95'][1]:.4f}], candidate {relative['candidate']['median']:.4f}x [{relative['candidate']['ci95'][0]:.4f}, {relative['candidate']['ci95'][1]:.4f}].", '',
              'This microbenchmark compares a registered-descriptor update API with raw Rust epoll_ctl(MOD); it measures syscall/API throughput, not scheduler or application throughput. The benchmark checks every update return code and validates final userdata via readiness delivery.', '',
              f"All samples and hashes: [{args.output.name}]({args.output.name}).", '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
