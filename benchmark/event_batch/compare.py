#!/usr/bin/env python3
"""Paired burst-drain benchmark for Forge event-loop and Rust epoll batches."""
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

ROOT = Path(__file__).resolve().parents[2]
BASE_CAPACITY = 64


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(binary, arguments, expected_events, cpu):
    def pin():
        os.sched_setaffinity(0, {cpu})
    result = subprocess.run([str(binary), *map(str, arguments)], text=True,
                            capture_output=True, check=True, timeout=30,
                            preexec_fn=pin)
    fields = result.stdout.split()
    if len(fields) != 3 or int(fields[1]) <= 0 or int(fields[2]) != expected_events:
        raise RuntimeError(f"invalid event-drain result from {binary}: {result.stdout!r}")
    return dict(elapsed_ns=int(fields[0]), poll_calls=int(fields[1]),
                events_seen=int(fields[2]))


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
    parser.add_argument('--candidate-capacity', type=int, required=True)
    parser.add_argument('--rust-capacity', type=int, default=1024)
    parser.add_argument('--event-counts', nargs='+', type=int, default=[64, 256, 1024, 4096])
    parser.add_argument('--pairs', type=int, default=48)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--seed', type=int, default=20261013)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('This comparison uses Linux eventfd and epoll')
    if args.cpu not in os.sched_getaffinity(0) or args.pairs < 12 or args.pairs % 3:
        parser.error('Choose an allowed CPU and >=12 pairs divisible by three')
    if any(n < 1 or n > 65536 for n in args.event_counts):
        parser.error('Each event count must be in [1, 65536]')
    if not 1 <= args.candidate_capacity <= 65536 or not 1 <= args.rust_capacity <= 65536:
        parser.error('Batch capacities must be in [1, 65536]')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Output exists; choose a fresh report path')
    if args.build_dir.exists():
        parser.error('Build directory exists; choose a fresh directory')

    args.build_dir.mkdir(parents=True)
    cc = shutil.which('cc') or 'cc'
    rustc = shutil.which('rustc') or 'rustc'
    forge_src = ROOT / 'benchmark/event_batch/forge.c'
    rust_src = ROOT / 'benchmark/event_batch/rust.rs'
    clock_src = ROOT / 'benchmark/cpu/clock.c'
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

    capacities = dict(base=BASE_CAPACITY, candidate=args.candidate_capacity,
                      rust=args.rust_capacity)
    order_rng = random.Random(args.seed)
    raw, warmups, summary = [], [], []
    for count_index, event_count in enumerate(args.event_counts):
        names = list(binaries)
        orders = [names[i:] + names[:i] for i in range(3)] * (args.pairs // 3)
        order_rng.shuffle(orders)
        pairs, ratios, speedups = [], {n: [] for n in ('base', 'candidate')}, []
        elapsed_by_name = {n: [] for n in names}
        calls_by_name = {n: [] for n in names}
        for pair_id, order in enumerate(orders):
            samples = {}
            for position, name in enumerate(order):
                arguments = [event_count] if name != 'rust' else [event_count, capacities['rust']]
                warm = run(binaries[name], arguments, event_count, args.cpu)
                sample = run(binaries[name], arguments, event_count, args.cpu)
                warmups.append(dict(implementation=name, event_count=event_count,
                                    pair=pair_id, position=position, **warm))
                raw.append(dict(implementation=name, event_count=event_count,
                                pair=pair_id, position=position, **sample))
                samples[name] = sample
                elapsed_by_name[name].append(sample['elapsed_ns'])
                calls_by_name[name].append(sample['poll_calls'])
            pairs.append(samples)
            for name in ('base', 'candidate'):
                ratios[name].append(samples['rust']['elapsed_ns'] / samples[name]['elapsed_ns'])
                if name == 'candidate':
                    speedups.append(samples['base']['elapsed_ns'] / samples[name]['elapsed_ns'])
        ci_rng = random.Random(args.seed + count_index)
        candidate_relative = dict(median=statistics.median(ratios['candidate']),
                                  ci95=ci95(ratios['candidate'], ci_rng))
        target_status = ('supported for this burst size' if candidate_relative['ci95'][0] >= 1.10
                         else 'below target' if candidate_relative['ci95'][1] < 1.10
                         else 'inconclusive')
        summary.append(dict(event_count=event_count, pairs=args.pairs,
                            median_drain_ns={n: statistics.median(v) for n, v in elapsed_by_name.items()},
                            median_poll_calls={n: statistics.median(v) for n, v in calls_by_name.items()},
                            forge_over_rust={n: dict(median=statistics.median(v), ci95=ci95(v, ci_rng))
                                             for n, v in ratios.items()},
                            target_1_10_status=target_status,
                            candidate_over_base=dict(median=statistics.median(speedups),
                                                     ci95=ci95(speedups, ci_rng))))

    runtime_root = ROOT.parent / 'forge-runtime'
    runtime_sources = [runtime_root / 'CMakeLists.txt', runtime_root / 'src/event_loop.c',
                       runtime_root / 'tests/event_loop_test.c']
    report = dict(description='One burst of simultaneously-ready eventfds drained through Forge callbacks and direct Rust epoll_wait.',
                  method=dict(base_batch_capacity=BASE_CAPACITY,
                              candidate_batch_capacity=args.candidate_capacity,
                              rust_batch_capacity=args.rust_capacity, event_counts=args.event_counts,
                              pairs=args.pairs, cpu=args.cpu, random_seed=args.seed,
                              timing='sum of drain durations; descriptor creation, registration and signaling are outside the timer',
                              warmup='one checked run per implementation and pair',
                              confidence='paired median bootstrap percentile 95% interval, per row'),
                  environment=dict(platform=platform.platform(), python=platform.python_version(),
                                   allowed_affinity=sorted(os.sched_getaffinity(0))),
                  artifacts={name: dict(path=str(path), sha256=sha(path)) for name, path in binaries.items()},
                  runner=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  source_sha256={str(path.relative_to(ROOT)): sha(path) for path in (forge_src, rust_src, clock_src)},
                  runtime_source_sha256={str(path): sha(path) for path in runtime_sources if path.exists()},
                  library_sha256={'baseline': sha(args.baseline_library), 'candidate': sha(args.candidate_library)},
                  results=summary, warmups=warmups, measurements=raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Forge event-loop burst drain benchmark', '', report['description'], '',
             f"{args.pairs} paired samples per event count, pinned to CPU {args.cpu}. Rust uses batch capacity {args.rust_capacity}.", '',
             '| Ready eventfds | Implementation | Median drain (us) | Poll calls | Forge/Rust throughput | Candidate/base speedup |',
             '| ---: | --- | ---: | ---: | ---: | ---: |']
    for row in summary:
        count = row['event_count']
        for name in binaries:
            ratio = row['forge_over_rust'][name]['median'] if name != 'rust' else 1.0
            speed = row['candidate_over_base']['median'] if name == 'candidate' else 1.0
            lines.append(f"| {count} | {name} | {row['median_drain_ns'][name]/1000:.2f} | {row['median_poll_calls'][name]:.1f} | {ratio:.4f}x | {speed:.4f}x |")
    lines += ['', 'All event IDs were observed once before the timer stopped; setup/signaling are excluded from the timed drain. Confidence intervals are paired and per row.',
              'This event-loop microbenchmark measures burst-drain behavior, not application or scheduler throughput. Forge dispatches through the public C callback API; Rust calls epoll_wait directly, a strict lower-level control.', '',
              'Rust-relative candidate results (median paired throughput and 95% interval):', '']
    for row in summary:
        ratio = row['forge_over_rust']['candidate']
        speed = row['candidate_over_base']
        lines.append(f"- {row['event_count']} ready descriptors: Forge/Rust {ratio['median']:.4f}x [{ratio['ci95'][0]:.4f}, {ratio['ci95'][1]:.4f}], candidate/base {speed['median']:.4f}x [{speed['ci95'][0]:.4f}, {speed['ci95'][1]:.4f}], 1.10 status: {row['target_1_10_status']}.")
    lines += ['',
              f"All samples and provenance: [{args.output.name}]({args.output.name}).", '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
