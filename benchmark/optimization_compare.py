#!/usr/bin/env python3
"""Compare frozen Forge builds against Rust controls with paired checks.

Every variant runs runtime inputs checked with the independent CPU reference.
Source variants are rejected unless equivalent-workload mode is explicit and
each changed variant has a provenance-matched Rust control. Timing starts only
after all snapshots have been built and validated.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import random
import statistics
import time

from cpu_compare import capture, confidence, reference, run_binary, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', action='append', required=True, metavar='NAME=BUILD_DIR')
    parser.add_argument('--baseline', required=True, help='One of the variant names')
    parser.add_argument('--dimensions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--rust-control', action='append', default=[], metavar='NAME=BINARY',
                        help='Additional frozen Rust control with parent build.json provenance')
    parser.add_argument('--allow-equivalent-workload-rewrites', action='store_true',
                        help='Allow changed workload sources only when each nonbaseline variant has a matching rust_<variant> control and all outputs match the independent reference')
    parser.add_argument('--workloads', nargs='+', help='Select explicit rows from the dimension report')
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--pairs', type=int, default=20)
    parser.add_argument('--random-seed', type=int, default=20261012)
    args = parser.parse_args()
    directories = {}
    for value in args.variant:
        name, directory = value.split('=', 1)
        if name in directories or name == 'rust':
            parser.error('Variant names must be unique and cannot be rust')
        directories[name] = Path(directory).resolve()
    if args.baseline not in directories or args.cpu not in os.sched_getaffinity(0):
        parser.error('Choose a baseline variant and an allowed CPU')
    controls = {}
    for value in args.rust_control:
        name, path = value.split('=', 1)
        if name in directories or name == 'rust' or name in controls:
            parser.error('Rust control names must be unique')
        binary = Path(path).resolve()
        metadata_path = binary.parent / 'build.json'
        controls[name] = dict(path=str(binary), sha256=sha(binary),
                              provenance=json.loads(metadata_path.read_text()),
                              provenance_sha256=sha(metadata_path))
    count = len(directories) + 1 + len(controls)
    if args.pairs < 12 or args.pairs % count:
        parser.error('Use >=12 pairs divisible by implementation count for balanced positions')
    if args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Report exists; use a new output path')
    builds = {name: json.loads((directory / 'build.json').read_text())
              for name, directory in directories.items()}
    for name, directory in directories.items():
        for language in ('forge', 'rust'):
            if sha(directory / (language + '-cpu')) != builds[name]['executables'][language]['sha256']:
                raise RuntimeError('Frozen executable changed: ' + name + '/' + language)
        fixtures = ('clock.c',) if args.allow_equivalent_workload_rewrites else (
            'kernels.fg', 'kernels.rs', 'clock.c')
        for fixture in fixtures:
            if builds[name]['fixture_sha256'][fixture] != builds[args.baseline]['fixture_sha256'][fixture]:
                raise RuntimeError('Measured algorithm or timer changed: ' + name + '/' + fixture)
    if args.allow_equivalent_workload_rewrites:
        required_controls = {f'rust_{name}' for name in directories if name != args.baseline}
        missing_controls = required_controls - controls.keys()
        if missing_controls:
            parser.error('Equivalent workload rewrites require matching controls: ' +
                         ', '.join(sorted(missing_controls)))
        baseline_build = builds[args.baseline]
        for name in directories:
            build = builds[name]
            for artifact in ('compiler', 'runtime', 'stdlib'):
                if build['artifacts'][artifact]['sha256'] != baseline_build['artifacts'][artifact]['sha256']:
                    raise RuntimeError('Equivalent workload rewrite changed SDK artifact: ' + name + '/' + artifact)
            if build['header_sha256'] != baseline_build['header_sha256']:
                raise RuntimeError('Equivalent workload rewrite changed SDK headers: ' + name)
            if name == args.baseline:
                continue
            control = controls[f'rust_{name}']
            if control['sha256'] != build['executables']['rust']['sha256']:
                raise RuntimeError('Rust control binary does not match variant: ' + name)
            if control['provenance']['fixture_sha256'] != build['fixture_sha256']:
                raise RuntimeError('Rust control workload provenance does not match variant: ' + name)
    binaries = {name: directory / 'forge-cpu' for name, directory in directories.items()}
    binaries['rust'] = directories[args.baseline] / 'rust-cpu'
    binaries.update({name: Path(data['path']) for name, data in controls.items()})
    rust_names = ['rust', *controls]
    dimensions = json.loads(args.dimensions.read_text())['summary']
    if args.workloads:
        if set(args.workloads) - {row['workload'] for row in dimensions}:
            parser.error('Selected workload missing from dimension report')
        dimensions = [row for row in dimensions if row['workload'] in args.workloads]
    rng = random.Random(args.random_seed)
    checks, warmups, measurements, summary = [], [], [], []
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for case in dimensions:
        mode, n, rounds = case['workload'], case['n'], case['rounds']
        edge_cases = ((1, 1, 1), (31, 3, 17), (127, 2, 719),
                      (1, 2, -719), (13, 3, -100000))
        if mode in ('lcg', 'scan', 'builder', 'immutable', 'immutable_view'):
            edge_cases += ((13, 3, -(1 << 63)), (13, 3, (1 << 63) - 1))
        for small_n, small_rounds, seed in edge_cases:
            expected = reference(mode, small_n, small_rounds, seed)
            for name, binary in binaries.items():
                row = run_binary(binary, mode, small_n, small_rounds, seed, args.cpu)
                if row['checksum'] != expected:
                    raise RuntimeError('Correctness failure: ' + name + '/' + mode)
                checks.append(dict(implementation=name, workload=mode, n=small_n,
                                   rounds=small_rounds, seed=seed, reference_checksum=expected, **row))
        # Each implementation occupies each ordinal position equally often.
        # Cyclic schedules do not balance every adjacency when count > 3.
        names = list(binaries)
        orders = [names[i:] + names[:i] for i in range(count)] * (args.pairs // count)
        rng.shuffle(orders)
        elapsed = {name: [] for name in binaries}
        over_rust = {name: [] for name in directories}
        over_controls = {control: {name: [] for name in directories} for control in rust_names}
        speedup = {name: [] for name in directories}
        for pair, order in enumerate(orders):
            seed = rng.randint(1, 100000)
            expected = reference(mode, n, rounds, seed)
            paired = {}
            for position, name in enumerate(order):
                for kind in ('prewarm', 'measurement'):
                    row = run_binary(binaries[name], mode, n, rounds, seed, args.cpu)
                    if row['checksum'] != expected:
                        raise RuntimeError('Checksum failure: ' + name + '/' + mode + '/' + kind)
                    record = dict(implementation=name, workload=mode, pair=pair, order=position,
                                  n=n, rounds=rounds, seed=seed, reference_checksum=expected, **row)
                    (warmups if kind == 'prewarm' else measurements).append(record)
                    if kind == 'measurement':
                        paired[name] = row['kernel_ns']
                        elapsed[name].append(row['kernel_ns'])
            for name in directories:
                over_rust[name].append(paired['rust'] / paired[name])
                for control in rust_names:
                    over_controls[control][name].append(paired[control] / paired[name])
                speedup[name].append(paired[args.baseline] / paired[name])
        def summarize(samples, offset):
            return dict(samples=samples, median=statistics.median(samples),
                        ci95=confidence(samples, args.random_seed + offset))
        row = dict(workload=mode, n=n, rounds=rounds, pairs=args.pairs,
                   median_ms={name: statistics.median(values) / 1e6 for name, values in elapsed.items()},
                   over_rust={name: summarize(values, i) for i, (name, values) in enumerate(over_rust.items())},
                   over_rust_controls={control: {name: summarize(values, i) for i, (name, values) in enumerate(data.items())}
                                       for control, data in over_controls.items()},
                   baseline_speedup={name: summarize(values, i + count) for i, (name, values) in enumerate(speedup.items())})
        summary.append(row)
        print(mode + ': ' + ', '.join(name + '/' + control + '=' + format(values['median'], '.4f')
                                     for control, data in row['over_rust_controls'].items()
                                     for name, values in data.items()), flush=True)
    report = dict(started_at_utc=started, finished_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  description=args.description, baseline=args.baseline, builds=builds,
                  rust_control=builds[args.baseline]['executables']['rust'],
                  extra_rust_controls=controls, executed_runner_source=Path(__file__).read_text(),
                  runner=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  method=dict(pairs=args.pairs, cpu=args.cpu, random_seed=args.random_seed,
                              order='Position-balanced cyclic rotations, shuffled; adjacency is not fully balanced',
                              prewarm='One checked identical-input run before each sample',
                              allow_equivalent_workload_rewrites=args.allow_equivalent_workload_rewrites,
                              confidence='10000 paired-ratio median bootstrap resamples; percentile 95%; not family-wise confidence',
                              throughput_over_rust='rust_kernel_ns / forge_kernel_ns',
                              baseline_speedup='baseline_kernel_ns / variant_kernel_ns',
                              dimensions=dict(path=str(args.dimensions), sha256=sha(args.dimensions)),
                              limitations='Shared Linux host, finite workloads, no timing outlier exclusion; RSS is whole-process not precise heap usage'),
                  environment=dict(platform=platform.platform(), python=platform.python_version(),
                                   allowed_affinity=sorted(os.sched_getaffinity(0)), load_average_end=os.getloadavg(),
                                   lscpu=capture(['lscpu'])), correctness_checks=checks, warmups=warmups,
                  measurements=measurements, summary=summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Frozen Forge optimization comparison', '', args.description, '',
             f'Measured `{started}` to `{report["finished_at_utc"]}` with {args.pairs} position-balanced pairs per workload. ' +
             ('Changed source variants use a provenance-matched Rust control.' if args.allow_equivalent_workload_rewrites else 'One preserved Rust binary is shared by every variant.'), '',
             '| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |',
             '| --- | --- | --- | ---: | ---: | --- |']
    for row in summary:
        for name in directories:
            for control in rust_names:
                ratio, gain = row['over_rust_controls'][control][name], row['baseline_speedup'][name]
                low, high = ratio['ci95']
                status = 'supported for this case' if low >= 1.10 else 'below target' if high < 1.10 else 'inconclusive'
                lines.append(f'| {row["workload"]} | {name} | {control} | {ratio["median"]:.4f} [{low:.4f}, {high:.4f}] | {gain["median"]:.4f} [{gain["ci95"][0]:.4f}, {gain["ci95"][1]:.4f}] | {status} |')
    lines += ['', 'All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.', '',
              'Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. ' +
              ('Changed workload sources are allowed only across variants; each Forge variant and its Rust control share frozen fixture hashes, and the timer source is common.' if args.allow_equivalent_workload_rewrites else 'FG/Rust workload and common timer sources are identical across variants.') +
              ' Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.', '',
              'Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Builder snapshot/copy/ownership-transfer choices are defined by the frozen fixture sources; compare their contracts before interpreting this row. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.', '',
              'These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.', '',
              f'Raw provenance and all samples: [{args.output.name}]({args.output.name}).', '']
    args.output.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
