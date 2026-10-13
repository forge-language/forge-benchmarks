#!/usr/bin/env python3
"""Native three-way CPU comparison for Linux, macOS and MinGW Windows.

Both Forge compilers share one SDK, algorithm sources, timer and Rust control.
Kernel timings are printed by the common C timer, excluding process startup.
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
import time

from cpu_compare import confidence, reference, sha

ROOT = Path(__file__).resolve().parents[1]


def command(argv, timeout=180):
    result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{argv!r} failed ({result.returncode}):\n{result.stderr}\n{result.stdout}')
    return result.stdout.strip()


def run_binary(binary, mode, n, rounds, seed):
    start = time.perf_counter_ns()
    output = command([binary, mode, n, rounds, seed], timeout=60)
    wall = time.perf_counter_ns() - start
    lines = output.splitlines()
    if len(lines) != 2:
        raise RuntimeError('Unexpected output: ' + repr(output))
    checksum, elapsed = map(int, lines)
    if elapsed < 0:
        raise RuntimeError('Timer went backwards')
    return {'checksum': checksum, 'kernel_ns': elapsed, 'process_wall_ns': wall}


def source_revision(root):
    # checkout runs Windows Git; native Python in MSYS2 may invoke MSYS2 Git
    # with a different global autocrlf setting. Compare canonical content with
    # the Windows checkout filter, rather than treating every CRLF file as an
    # edit. This does not discard real content changes.
    overrides = ['-c', 'core.autocrlf=true', '-c', 'core.filemode=false'] if os.name == 'nt' else []
    git = ['git', *overrides, '-C', root]
    dirty = command([*git, 'status', '--porcelain', '--untracked-files=no'])
    crlf_equivalent = False
    if os.name == 'nt' and dirty:
        # Git's cached index/stat state may still report M after switching
        # filters. Compare content explicitly, ignoring only CR at line ends.
        diff = subprocess.run(list(map(str, [*git, 'diff', '--exit-code', '--ignore-cr-at-eol', 'HEAD', '--'])),
                              capture_output=True, text=True, timeout=180)
        if diff.returncode not in (0, 1):
            raise RuntimeError('Source comparison failed: ' + diff.stderr)
        if diff.returncode == 0:
            dirty = ''
            crlf_equivalent = True
    return {'head': command([*git, 'rev-parse', 'HEAD']), 'tracked_dirty': dirty,
            'git_config_overrides': overrides, 'crlf_equivalent_to_head': crlf_equivalent}


def hardware_description():
    if platform.system() == 'Linux':
        return command(['lscpu'])
    if platform.system() == 'Darwin':
        return command(['sysctl', '-n', 'machdep.cpu.brand_string', 'hw.model', 'hw.ncpu'])
    if os.name == 'nt':
        return command(['powershell.exe', '-NoProfile', '-Command',
                        'Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name'])
    return platform.processor()


def apply_probe(text, kind):
    """Explicit fixture experiments, never implicit changes to measured code."""
    changes = {}
    if kind in ('bounded-hint', 'bounded-inline'):
        old = '        if (product > n) product -= d;\n        return (int64_t)(n - product);'
        new = ('        if ((n >= (UINT64_C(1) << 43) || d > (UINT64_C(1) << 21)) && product > n) product -= d;\n'
               '        uint64_t remainder = n - product;\n'
               '        if (remainder >= d) __builtin_unreachable();\n'
               '        return (int64_t)remainder;')
        if text.count(old) != 1:
            raise RuntimeError('Unexpected invariant-mod helper shape')
        text = text.replace(old, new)
        changes.update(replaced_body=old, new_body=new)
        if kind == 'bounded-inline':
            for function in ['prime_mod_pow', 'prime_mr_pass']:
                declaration = 'static int64_t ' + function + '('
                if text.count(declaration) != 2:
                    raise RuntimeError('Unexpected prime function shape')
                text = text.replace(declaration, 'static inline __attribute__((always_inline)) int64_t ' + function + '(')
            changes['always_inline_functions'] = ['prime_mod_pow', 'prime_mr_pass']
    if kind in ('reserved-builder', 'hardware-builder'):
        signature = 'static const char* pattern(int64_t n, int64_t seed) {'
        begin = text.index(signature)
        end = text.index('\n}\n', begin) + 3
        body = text[begin:end]
        loop = ('    int64_t i = INT64_C(0);\n    while (\n(i < n)) {\n'
                '        if ((fr_str_builder_char(builder,FORGE_ADD(INT64_C(65), (FORGE_ADD(i, seed) % INT64_C(26)))) == INT64_C(0))) {\n'
                '            return "";\n        }\n        i = (i + INT64_C(1));\n    }')
        if body.count(loop) != 1:
            raise RuntimeError('Unexpected reserved builder loop shape')
        fast = ('    fr_detail_str_builder *probe_builder = (fr_detail_str_builder *)(intptr_t)builder;\n'
                '    if (n > 0 && probe_builder->data && probe_builder->len == 0 && probe_builder->cap > (uint64_t)n) {\n'
                '        char *probe_data = probe_builder->data;\n'
                '        int64_t i = 0;\n        while (i < n) {\n'
                '            probe_data[i] = (char)FORGE_ADD(INT64_C(65), (FORGE_ADD(i, seed) % INT64_C(26)));\n'
                '            i = i + 1;\n        }\n'
                '        probe_builder->len = (size_t)n;\n'
                '        return fr_str_builder_finish_take(builder);\n    }\n')
        new_body = body.replace(loop, fast + loop)
        text = text[:begin] + new_body + text[end:]
        changes['builder_body_before'] = body
        changes['builder_body_after'] = new_body
        if kind == 'hardware-builder':
            directive = '#if defined(__SIZEOF_INT128__)'
            if text.count(directive) != 2:
                raise RuntimeError('Unexpected reciprocal preprocessor guards')
            text = text.replace(directive, '#if 0 /* explicit hardware-remainder experiment */')
            changes['reciprocal_disabled'] = True
    return text, changes


def markdown(report):
    lines = ['# Native cross-OS CPU comparison', '',
             f"Platform: `{report['environment']['platform']}` / `{report['environment']['architecture']}`. "
             f"Measured {report['method']['pairs']} balanced triples per workload, seed {report['method']['random_seed']}.", '',
             '| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |',
             '| --- | ---: | ---: | --- |']
    probe = report['build'].get('after_probe', {}).get('name', 'none')
    if probe != 'none':
        lines[3:3] = [f'**Generated-C experiment `{probe}`: the candidate C helper is modified after emission. '
                       'These results do not measure the shipped compiler unchanged.**', '']
    for row in report['summary']:
        gain, rust = row['candidate_speedup'], row['candidate_over_rust']
        lines.append(f"| {row['workload']} | {gain['median']:.4f} [{gain['ci95'][0]:.4f}, {gain['ci95'][1]:.4f}] | "
                     f"{rust['median']:.4f} [{rust['ci95'][0]:.4f}, {rust['ci95'][1]:.4f}] | {row['target_status']} |")
    lines += ['', 'All measured checksums and same-input warmups match an independent Python reference. '
              'All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap '
              '95% interval; this is not simultaneous confidence over workloads or proof for all programs.', '',
              'Both Forge versions share identical SDK archives/headers, source algorithms and clock; '
              'one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, '
              'target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel '
              'times. All platforms use unpinned child processes; virtualized/shared runners and frequency '
              'changes remain sources of noise. Compare before/after ratios within each OS; absolute times '
              'across different OS/hardware/architectures are not OS-only causal comparisons.', '',
              'Builder transfers the buffer in both implementations. Immutable append uses different '
              'allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence '
              'or universal language throughput. Build failures are recorded as failed_no_claim and must '
              'not be silently removed from the cross-OS report.', '',
              f"Full samples, commands and hashes: [{Path(report['output']).name}]({Path(report['output']).name}).", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'sdk', 'before-root', 'after-root', 'runtime-root', 'stdlib-root', 'dimensions', 'build-dir', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--rustc', default='rustc')
    parser.add_argument('--rust-target')
    parser.add_argument('--rust-linker')
    parser.add_argument('--pairs', type=int, default=60)
    parser.add_argument('--random-seed', type=int, default=20261013)
    parser.add_argument('--seed-offset', type=int, default=0)
    parser.add_argument('--after-probe', choices=['none', 'bounded-hint', 'bounded-inline', 'reserved-builder', 'hardware-builder'], default='none',
                        help='Explicit generated-C experiment; never report it as shipped compiler code')
    parser.add_argument('--workloads', nargs='+', default=['lcg', 'primes', 'scan', 'builder', 'immutable'])
    args = parser.parse_args()
    args.random_seed += args.seed_offset
    if args.pairs < 12 or args.pairs % 6:
        parser.error('Choose >=12 pairs divisible by six')
    if args.build_dir.exists() or args.output.exists() or args.output.with_suffix('.md').exists():
        parser.error('Choose fresh build/output paths')
    dimensions = {row['workload']: (row['n'], row['rounds']) for row in json.loads(args.dimensions.read_text())['summary']}
    if set(args.workloads) - dimensions.keys():
        parser.error('Every workload must have frozen dimensions')
    directory = args.build_dir.resolve()
    snapshot = directory / 'snapshot'
    snapshot.mkdir(parents=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'output': str(args.output),
              'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'environment': {'platform': platform.platform(), 'architecture': platform.machine(),
                              'python': platform.python_version(), 'logical_cpus': os.cpu_count(),
                              'runner_name': os.environ.get('RUNNER_NAME'), 'runner_os': os.environ.get('RUNNER_OS'),
                              'run_url': 'https://github.com/forge-language/forge-benchmarks/actions/runs/' + os.environ['GITHUB_RUN_ID'] if os.environ.get('GITHUB_RUN_ID') else None},
              'method': {'pairs': args.pairs, 'random_seed': args.random_seed,
                         'order': 'all six permutations equally represented, randomized per workload',
                         'prewarm': 'identical input immediately before every measurement',
                         'cpu_affinity': 'unpinned on all platforms', 'target_ratio': 1.10,
                         'confidence': '10000 paired-ratio median bootstrap resamples; row-wise percentile 95%',
                         'dimensions_sha256': sha(args.dimensions)},
              'commands': [], 'build': {}, 'correctness': [], 'warmups': [], 'measurements': [], 'summary': [],
              'runner_sha256': sha(Path(__file__)), 'runner_source': Path(__file__).read_text()}

    def checkpoint():
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    def build_command(argv):
        report['commands'].append(list(map(str, argv)))
        checkpoint()
        return command(argv)

    checkpoint()
    try:
        report['environment']['hardware'] = hardware_description()
        report['revisions'] = {name: source_revision(root) for name, root in
                               [('before', args.before_root), ('after', args.after_root),
                                ('runtime', args.runtime_root), ('stdlib', args.stdlib_root), ('benchmarks', ROOT)]}
        if any(value['tracked_dirty'] for value in report['revisions'].values()):
            raise RuntimeError('Cross-OS evidence requires clean tracked source trees')
        shutil.copytree(args.sdk / 'include', snapshot / 'include')
        extension = '.exe' if os.name == 'nt' else ''
        sources = {'kernels.fg': ROOT / 'benchmark/cpu/kernels_prime_miller_rabin_smallprime.fg',
                   'kernels.rs': ROOT / 'benchmark/cpu/kernels_prime_miller_rabin_smallprime.rs',
                   'clock.c': ROOT / 'benchmark/cpu/clock_portable.c',
                   'libforge_std.a': args.sdk / 'lib/libforge_std.a',
                   'libforge_runtime.a': args.sdk / 'lib/libforge_runtime.a',
                   'forge-before' + extension: args.before, 'forge-after' + extension: args.after}
        for name, source in sources.items():
            shutil.copy2(source, snapshot / name)
        report['build']['snapshot_sha256'] = {name: sha(snapshot / name) for name in sources}
        report['build']['header_sha256'] = {str(p.relative_to(snapshot / 'include')): sha(p) for p in (snapshot / 'include').rglob('*') if p.is_file()}
        report['build']['cc_version'] = command([args.cc, '--version']).splitlines()[0]
        report['build']['rust_version'] = command([args.rustc, '--version', '--verbose'])
        cpu_flag = '-mcpu=native' if platform.machine().lower() in ('arm64', 'aarch64') else '-march=native'
        macros = command([args.cc, '-std=gnu11', cpu_flag, '-dM', '-E', snapshot / 'clock.c'])
        int128 = [line.split()[-1] for line in macros.splitlines() if line.startswith('#define __SIZEOF_INT128__ ')]
        report['build']['int128_bytes'] = int(int128[0]) if int128 else None
        report['build']['cc_target'] = command([args.cc, '-dumpmachine'])
        report['build']['native_cpu_flag'] = cpu_flag
        report['build']['timer'] = 'QueryPerformanceCounter' if os.name == 'nt' else 'CLOCK_MONOTONIC'
        binaries = {}
        for name in ('before', 'after'):
            c_file, binary = snapshot / (name + '.c'), directory / (name + extension)
            build_command([snapshot / ('forge-' + name + extension), snapshot / 'kernels.fg', '--emit-c', '-o', c_file, '--forge-root', snapshot])
            if name == 'after' and args.after_probe != 'none':
                original_hash = sha(c_file)
                text, changes = apply_probe(c_file.read_text(), args.after_probe)
                c_file.write_text(text)
                report['build']['after_probe'] = {'name': args.after_probe,
                                                 'original_c_sha256': original_hash,
                                                 **changes}
            link = ['-lpthread', '-lm'] if os.name != 'nt' else ['-lws2_32', '-lm']
            build_command([args.cc, '-std=gnu11', '-O3', '-DNDEBUG', cpu_flag, '-flto', '-I', snapshot / 'include',
                           c_file, snapshot / 'clock.c', snapshot / 'libforge_std.a', snapshot / 'libforge_runtime.a',
                           *link, '-o', binary])
            binaries[name] = binary
        clock_object = snapshot / 'clock.o'
        build_command([args.cc, '-std=gnu11', '-O3', cpu_flag, '-c', snapshot / 'clock.c', '-o', clock_object])
        rust_binary = directory / ('rust' + extension)
        rust_command = [args.rustc, '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'lto=thin',
                        '-C', 'codegen-units=1', '-C', 'overflow-checks=off', '-C', 'link-arg=' + str(clock_object)]
        if os.name == 'nt':
            # Rust appends user link arguments after its import libraries.
            # Repeat Kernel32 after clock.o to resolve the QPC references.
            rust_command += ['-C', 'link-arg=-lkernel32']
        if args.rust_target:
            rust_command += ['--target', args.rust_target]
        if args.rust_linker:
            rust_command += ['-C', 'linker=' + args.rust_linker]
        build_command([*rust_command, snapshot / 'kernels.rs', '-o', rust_binary])
        binaries['rust'] = rust_binary
        report['build']['executables'] = {name: {'path': str(path), 'sha256': sha(path)} for name, path in binaries.items()}
        report['build']['generated_c_sha256'] = {name: sha(snapshot / (name + '.c')) for name in ('before', 'after')}
        report['build'].setdefault('after_probe', {'name': 'none'})
        for name, path in binaries.items():
            disassembler = ['otool', '-tvV'] if platform.system() == 'Darwin' else ['objdump', '-d']
            if shutil.which(disassembler[0]):
                listing = directory / (name + '-disassembly.txt')
                listing.write_text(command([*disassembler, path]))
                report['build'].setdefault('disassembly_sha256', {})[name] = sha(listing)
        checkpoint()

        def checked(name, mode, n, rounds, seed, expected):
            row = run_binary(binaries[name], mode, n, rounds, seed)
            if row['checksum'] != expected:
                raise RuntimeError(f'Checksum mismatch {name}/{mode}/{n}/{rounds}/{seed}: {row["checksum"]} != {expected}')
            return {'implementation': name, 'workload': mode, 'n': n, 'rounds': rounds,
                    'seed': seed, 'reference_checksum': expected, **row}

        rng = random.Random(args.random_seed)
        for mode in args.workloads:
            cases = [(0, 3, 0), (1, 1, 1), (13, 3, -100000), (31, 3, 17), (127, 2, 719)]
            if mode != 'primes':
                cases += [(13, 3, -(1 << 63)), (13, 3, (1 << 63) - 1)]
            else:
                cases += [(1, 1, value - 1000001) for value in (2, 3, 5, 1373652, 1373653, 1373654, 2000003)]
            for n, rounds, seed in cases:
                expected = reference(mode, n, rounds, seed)
                for name in binaries:
                    report['correctness'].append(checked(name, mode, n, rounds, seed, expected))
            n, rounds = dimensions[mode]
            orders = list(itertools.permutations(binaries)) * (args.pairs // 6)
            rng.shuffle(orders)
            elapsed = {name: [] for name in binaries}
            ratios = {'candidate_speedup': [], 'candidate_over_rust': [], 'baseline_over_rust': []}
            for pair, order in enumerate(orders):
                seed = rng.randint(1, 100000)
                expected = reference(mode, n, rounds, seed)
                paired = {}
                for position, name in enumerate(order):
                    warm = checked(name, mode, n, rounds, seed, expected)
                    report['warmups'].append({'pair': pair, 'position': position, **warm})
                    measured = checked(name, mode, n, rounds, seed, expected)
                    if measured['kernel_ns'] <= 0:
                        raise RuntimeError('Measured timer did not advance')
                    report['measurements'].append({'pair': pair, 'position': position, **measured})
                    paired[name] = measured['kernel_ns']
                    elapsed[name].append(measured['kernel_ns'])
                ratios['candidate_speedup'].append(paired['before'] / paired['after'])
                ratios['candidate_over_rust'].append(paired['rust'] / paired['after'])
                ratios['baseline_over_rust'].append(paired['rust'] / paired['before'])
                checkpoint()
            row = {'workload': mode, 'n': n, 'rounds': rounds,
                   'median_ms': {name: statistics.median(values) / 1e6 for name, values in elapsed.items()},
                   **{name: {'median': statistics.median(values), 'ci95': confidence(values, args.random_seed + index)}
                      for index, (name, values) in enumerate(ratios.items())}}
            low, high = row['candidate_over_rust']['ci95']
            row['target_status'] = 'supported for this case' if low >= 1.10 else 'below target' if high < 1.10 else 'inconclusive'
            report['summary'].append(row)
            print(f"{mode}: speedup={row['candidate_speedup']['median']:.4f}, Forge/Rust={row['candidate_over_rust']['median']:.4f}", flush=True)
        report['status'] = 'completed'
        report['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        checkpoint()
        args.output.with_suffix('.md').write_text(markdown(report))
    except Exception as error:
        report['status'] = 'failed_no_claim'
        report['error'] = str(error)
        report['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        checkpoint()
        raise


if __name__ == '__main__':
    main()
