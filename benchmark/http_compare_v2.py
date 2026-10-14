#!/usr/bin/env python3
"""Prepared HTTP v2: bounded connect, per-stage timing, preserved failures.

Consumes a validated SDK, snapshots every build input, compares the actual Forge
public prepared-response API to an owned Rust/socket2 implementation. This is
not a full HTTP parser, application routing, TLS, or coroutine comparison.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import select
import shutil
import signal
import socket
import statistics
import subprocess
import time

from cpu_compare import capture, confidence, sha, source_state, stable_copy
from thread_compare import physical_cpus

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'benchmark/http-v2'
PROTOCOL = 'prepared-http-v2-bounded-connect-stage-observer'


def stamp():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def body_for(seed, size):
    rng = random.Random(seed)
    return ''.join(chr(65 + rng.randrange(26)) for _ in range(size))


def response_for(body):
    payload = body.encode('ascii')
    return (f'HTTP/1.1 200 OK\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n'.encode() + payload)


def preexec(cpus):
    def apply():
        os.sched_setaffinity(0, set(cpus))
        for limit, wanted in [(resource.RLIMIT_NOFILE, 65536),
                              (resource.RLIMIT_MEMLOCK, 64 * 1024 * 1024)]:
            soft, hard = resource.getrlimit(limit)
            target = wanted if hard == resource.RLIM_INFINITY else min(hard, wanted)
            resource.setrlimit(limit, (max(soft, target), hard))
    return apply


def unused_port():
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1', 0))
        return candidate.getsockname()[1]


def affinities(pid):
    return {int(task.name): sorted(os.sched_getaffinity(int(task.name)))
            for task in Path(f'/proc/{pid}/task').iterdir()}


def audit_workers(pid, cpus):
    current = affinities(pid)
    wanted = 1 if len(cpus) == 1 else len(cpus) + 1
    if len(current) != wanted or set(current[pid]) != set(cpus):
        raise RuntimeError(f'Wrong server thread count/main affinity: {current}')
    if len(cpus) == 1:
        workers = [current[pid]]
    else:
        workers = [value for tid, value in current.items() if tid != pid]
    if sorted(workers) != sorted([[cpu] for cpu in cpus]):
        raise RuntimeError(f'Worker affinity escaped/mismatched: {current}')
    return current


def process_stats(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
    ticks = os.sysconf('SC_CLK_TCK')
    return {'user_seconds': int(fields[11]) / ticks,
            'system_seconds': int(fields[12]) / ticks,
            'resident_pages': int(fields[21]), 'threads': int(fields[17])}


def passive_kernel(port):
    """Read shared counters/state without packets, sysctl changes or tracing."""
    result = {'observed_at_utc': stamp(), 'scope': 'network namespace/global; attribution unproven',
              'sysctls': {}, 'errors': []}
    for name in ['net/ipv4/tcp_syn_retries', 'net/ipv4/tcp_syn_linear_timeouts',
                 'net/ipv4/tcp_tw_reuse', 'net/ipv4/ip_local_port_range',
                 'net/ipv4/tcp_max_tw_buckets', 'net/ipv4/tcp_max_syn_backlog',
                 'net/core/somaxconn', 'net/netfilter/nf_conntrack_count',
                 'net/netfilter/nf_conntrack_max', 'net/ipv4/tcp_mem']:
        path = Path('/proc/sys') / name
        try:
            result['sysctls'][name] = path.read_text().strip()
        except OSError as error:
            result['errors'].append({'path': str(path), 'error': repr(error)})
    try:
        lines = Path('/proc/net/netstat').read_text().splitlines()
        values = dict(zip(lines[0].split()[1:], map(int, lines[1].split()[1:])))
        result['global_tcp_ext_counters'] = {key: values.get(key) for key in
                                            ['ListenOverflows', 'ListenDrops', 'TCPSynRetrans',
                                             'TCPTimeouts', 'TCPMemoryPressures', 'TCPTimeWaitOverflow',
                                             'TCPReqQFullDrop', 'TCPReqQFullDoCookies',
                                             'TCPBacklogDrop', 'TCPRcvQDrop']}
        result['sockstat'] = Path('/proc/net/sockstat').read_text()
        counts, pending = {}, []
        encoded = f'{port:04X}'
        for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
            fields = line.split()
            if fields[1].split(':')[1] != encoded and fields[2].split(':')[1] != encoded:
                continue
            state = fields[3]
            counts[state] = counts.get(state, 0) + 1
            if state in ('02', '03', '0A'):
                pending.append({'local_address_hex': fields[1], 'remote_address_hex': fields[2],
                                'state_hex': state, 'queue_hex': fields[4],
                                'timer_hex': fields[5], 'retransmissions_hex': fields[6],
                                'inode': fields[9]})
        result.update(port=port, port_socket_state_counts=counts, listeners_and_pending=pending)
    except (OSError, ValueError, IndexError) as error:
        result['errors'].append({'source': '/proc network observations', 'error': repr(error)})
    return result


def stop(child):
    if child is None:
        return None
    if child.returncode is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                return {'exit_code': child.returncode, 'user_seconds': usage.ru_utime,
                        'system_seconds': usage.ru_stime, 'peak_rss_kib': usage.ru_maxrss}
            time.sleep(.01)
        os.killpg(child.pid, signal.SIGKILL)
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
        return {'exit_code': child.returncode, 'user_seconds': usage.ru_utime,
                'system_seconds': usage.ru_stime, 'peak_rss_kib': usage.ru_maxrss}
    return {'exit_code': child.returncode}


def exchange(port, request, expected, fragmented=False):
    with socket.create_connection(('127.0.0.1', port), timeout=10) as connection:
        if fragmented:
            connection.sendall(request[:-2])
            connection.settimeout(.03)
            try:
                unexpected = connection.recv(1)
                raise RuntimeError('Server responded before complete headers: ' + repr(unexpected))
            except socket.timeout:
                pass
            connection.settimeout(10)
            connection.sendall(request[-2:])
        else:
            connection.sendall(request)
        received = bytearray()
        while True:
            block = connection.recv(65536)
            if not block:
                break
            received.extend(block)
            if len(received) > len(expected):
                raise RuntimeError('Extra response bytes')
        if bytes(received) != expected:
            raise RuntimeError(f'Exact independent response mismatch: {bytes(received)[:256]!r}')
    return {'request_sha256': hashlib.sha256(request).hexdigest(),
            'response_sha256': hashlib.sha256(received).hexdigest(),
            'response_bytes': len(received), 'fragmented': fragmented}


def start_server(binary, workers, body, cpus, raw_prefix, port=None):
    # Cohort callers can reserve a wildcard-compatible candidate: a port free
    # on 127.0.0.1 can still conflict with TIME_WAIT on another source alias.
    # Existing V2/V3 callers retain their original port-selection protocol.
    port = unused_port() if port is None else port
    env = dict(os.environ, FORGE_BENCH_CPUS=','.join(map(str, cpus)), FORGE_MAX_FDS='65536')
    command = [str(binary), str(port), str(workers), body]
    stdout = open(str(raw_prefix) + '-server.stdout', 'xb')
    stderr = open(str(raw_prefix) + '-server.stderr', 'xb')
    child = None
    try:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env,
                                 preexec_fn=preexec(cpus), start_new_session=True)
        deadline = time.monotonic() + 10
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError('Server readiness timeout (no retry)')
            try:
                audit = audit_workers(child.pid, cpus)
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    pass
                break
            except (OSError, RuntimeError):
                time.sleep(.01)
        return child, port, command, audit
    except BaseException:
        stop(child)
        raise
    finally:
        stdout.close(); stderr.close()


def correctness(binary, workers, cpus, seed, body_size, prefix):
    body = body_for(seed, body_size)
    expected = response_for(body)
    server = None
    result = {'server_binary': str(binary), 'workers': workers, 'seed': seed,
              'body_bytes': body_size, 'status': 'running', 'checks': []}
    save(prefix.with_suffix('.json'), result)
    try:
        server, port, command, audit = start_server(binary, workers, body, cpus, prefix)
        result.update(server_command=command, server_affinity_before=audit)
        for padding, fragmented in [(0, False), (513, False), (7800, False), (64, True)]:
            request = (f'GET /validation/{seed}/{padding} HTTP/1.1\r\nHost: localhost\r\n'
                       f'X-Test: {"x" * padding}\r\nConnection: close\r\n\r\n').encode()
            result['checks'].append(exchange(port, request, expected, fragmented))
            save(prefix.with_suffix('.json'), result)
        result['server_affinity_after'] = audit_workers(server.pid, cpus)
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        result['server_process_usage'] = stop(server)
        save(prefix.with_suffix('.json'), result)
    return result


def trial(server_binary, load_binary, workers, concurrency, requests, seed,
          body_size, server_cpus, client_cpus, prefix, connect_timeout_ms=10000):
    body = body_for(seed, body_size)
    expected = response_for(body)
    response_path = Path(str(prefix) + '-expected.bin')
    response_path.write_bytes(expected)
    samples_path = Path(str(prefix) + '-requests.tsv')
    stdout_path = Path(str(prefix) + '-load.stdout')
    stderr_path = Path(str(prefix) + '-load.stderr')
    result = {'status': 'running', 'protocol': PROTOCOL, 'workers': workers, 'concurrency': concurrency,
              'requests': requests, 'seed': seed, 'body_bytes': body_size,
              'connect_timeout_ms': connect_timeout_ms,
              'observer_failure_policy': 'first failure stops new requests; all in-flight attempts retained; trial fails without retry',
              'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
              'expected_response_sha256': sha(response_path),
              'expected_response_bytes': len(expected), 'raw_prefix': str(prefix),
              'server_cpus': server_cpus, 'client_cpus': client_cpus}
    save(prefix.with_suffix('.json'), result)
    server, client, port = None, None, None
    try:
        server, port, command, audit = start_server(server_binary, workers, body, server_cpus, prefix)
        result.update(server_command=command, server_affinity_before=audit)
        # Independent Python packet check establishes the server actually
        # produces the expected bytes before the shared load observer starts.
        request = f'GET /probe/{seed} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'.encode()
        result['independent_probe'] = exchange(port, request, expected)
        load_command = [str(load_binary), *map(str, [port, concurrency, requests, seed]),
                        str(response_path), str(samples_path), str(connect_timeout_ms)]
        result['load_command'] = load_command
        with stderr_path.open('xb') as error_output:
            client = subprocess.Popen(load_command, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=error_output,
                                      preexec_fn=preexec(client_cpus), start_new_session=True)
            if not select.select([client.stdout], [], [], 15)[0]:
                raise RuntimeError('Client readiness timeout')
            ready = client.stdout.readline()
            if ready != b'ready\n':
                raise RuntimeError('Client readiness failed: ' + repr(ready))
            client_audit = affinities(client.pid)
            if len(client_audit) != concurrency + 1 or any(set(value) != set(client_cpus) for value in client_audit.values()):
                raise RuntimeError('Client thread count or isolated affinity mismatch')
            result['client_affinity'] = client_audit
            result['passive_kernel_before'] = passive_kernel(port)
            result['server_stats_before'] = process_stats(server.pid)
            started = time.perf_counter_ns()
            client.stdin.write(b'go\n'); client.stdin.flush(); client.stdin.close()
            deadline = time.monotonic() + 180
            while True:
                pid, status, usage = os.wait4(client.pid, os.WNOHANG)
                if pid:
                    client.returncode = os.waitstatus_to_exitcode(status)
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('Client completion timeout (no retry)')
                time.sleep(.002)
            result['observer_wall_ns'] = time.perf_counter_ns() - started
            result['server_stats_after'] = process_stats(server.pid)
            result['server_affinity_after'] = audit_workers(server.pid, server_cpus)
            result['passive_kernel_after'] = passive_kernel(port)
            output = ready + client.stdout.read()
            stdout_path.write_bytes(output)
            result['client_exit_code'] = client.returncode
            result['client_process_usage'] = {'user_seconds': usage.ru_utime,
                                            'system_seconds': usage.ru_stime,
                                            'peak_rss_kib': usage.ru_maxrss}
            if client.returncode:
                raise RuntimeError('Client failed; retained stderr: ' + str(stderr_path))
            elapsed, completed, errors = map(int, output.splitlines()[1].split(b'\t'))
            result.update(elapsed_ns=elapsed, attempted_requests=completed,
                          completed_requests=completed - errors, errors=errors)
        with samples_path.open() as observations:
            reader = csv.DictReader(observations, delimiter='\t')
            rows = list(reader)
            columns = reader.fieldnames
        wanted_columns = ['id', 'latency_ns', 'connect_ns', 'setup_ns', 'write_ns',
                          'read_ns', 'eof_ns', 'response_bytes', 'failed_stage', 'error']
        if columns != wanted_columns or len(rows) != requests:
            raise RuntimeError('Observer result vector malformed or incomplete')
        latencies = []
        identifiers = []
        phases = {key: [] for key in ['connect_ns', 'setup_ns', 'write_ns', 'read_ns', 'eof_ns']}
        for row in rows:
            identifier, latency = int(row['id']), int(row['latency_ns'])
            identifiers.append(identifier)
            if latency <= 0 or int(row['response_bytes']) != len(expected) or row['error'] or row['failed_stage']:
                raise RuntimeError('Request failure; every row preserved without exclusions')
            for key in phases:
                value = int(row[key])
                if value < 0:
                    raise RuntimeError('Negative observer stage duration')
                phases[key].append(value)
            if sum(int(row[key]) for key in phases) > latency:
                raise RuntimeError('Stage intervals exceed request interval')
            latencies.append(latency)
        if sorted(identifiers) != list(range(requests)):
            raise RuntimeError('Duplicate/missing request ID; no exclusions allowed')
        if completed != requests or errors or elapsed <= 0:
            raise RuntimeError('Incomplete/failed load; no timing ratio may be claimed')
        ordered = sorted(latencies)
        result.update(status='passed', all_request_ids_once=True, every_response_exact=True,
                      request_samples_sha256=sha(samples_path),
                      requests_per_second=completed * 1e9 / elapsed,
                      phase_durations={key: {'median_ns': statistics.median(values),
                                             'p99_ns': sorted(values)[min(len(values) - 1, int(len(values) * .99))],
                                             'max_ns': max(values)} for key, values in phases.items()},
                      latency_median_ns=statistics.median(latencies),
                      latency_p99_ns=ordered[min(len(ordered) - 1, int(len(ordered) * .99))])
    except BaseException as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        if port is not None and 'passive_kernel_after' not in result:
            result['passive_kernel_on_failure'] = passive_kernel(port)
        result['client_cleanup_usage'] = stop(client)
        result['server_process_usage'] = stop(server)
        if samples_path.exists():
            # Rows are written after every completed attempt, including errors;
            # retain partially filled vectors when any parent deadline fires.
            result['request_samples_sha256'] = sha(samples_path)
            with samples_path.open() as observations:
                partial = list(csv.DictReader(observations, delimiter='\t'))
            result['retained_request_rows'] = len(partial)
            result['retained_failed_rows'] = [row for row in partial if row.get('error') or row.get('failed_stage')]
        save(prefix.with_suffix('.json'), result)
    return result


def build(args):
    directory = args.build_dir.resolve()
    snapshot = directory / 'snapshot'
    if args.reuse_build:
        metadata = json.loads((directory / 'build.json').read_text())
        for name, digest in metadata['binary_sha256'].items():
            if sha(directory / name) != digest:
                raise RuntimeError('Immutable binary changed: ' + name)
        for name, digest in metadata['snapshot_sha256'].items():
            if sha(snapshot / name) != digest:
                raise RuntimeError('Immutable build input changed: ' + name)
        return metadata
    if directory.exists():
        raise RuntimeError('Build directory exists; use fresh path or --reuse-build')
    snapshot.mkdir(parents=True)
    artifacts = {
        'compiler': stable_copy((args.forge or args.sdk / 'bin/forge').resolve(), snapshot / 'forge'),
        'runtime': stable_copy((args.sdk / 'lib/libforge_runtime.a').resolve(), snapshot / 'libforge_runtime.a'),
        'stdlib': stable_copy((args.sdk / 'lib/libforge_std.a').resolve(), snapshot / 'libforge_std.a')}
    shutil.copytree(args.sdk / 'include', snapshot / 'include')
    for name in ['server.fg', 'config.c', 'Cargo.toml', 'Cargo.lock']:
        shutil.copyfile(FIXTURE / name, snapshot / name)
    shutil.copytree(FIXTURE / 'src', snapshot / 'src')
    commands = [
        [str(snapshot / 'forge'), str(snapshot / 'server.fg'), '--emit-c', '-o', str(snapshot / 'server.c'), '--forge-root', str(snapshot)],
        [args.cc, '-std=gnu11', '-O3', '-DNDEBUG', '-march=native', '-flto',
         '-I', str(snapshot / 'include'), str(snapshot / 'server.c'), str(snapshot / 'config.c'),
         '-Wl,--wrap=fr_thread_pin_cpu', '-Wl,--start-group', str(snapshot / 'libforge_std.a'),
         str(snapshot / 'libforge_runtime.a'), '-Wl,--end-group', '-lpthread', '-lm', '-o', str(directory / 'forge-http')],
        [args.cc, '-std=gnu11', '-O3', '-march=native', '-c', str(snapshot / 'config.c'), '-o', str(snapshot / 'config.o')],
        [args.cargo, 'build', '--release', '--locked', '--offline', '--manifest-path', str(snapshot / 'Cargo.toml'), '--target-dir', str(directory / 'rust-target')],
    ]
    rustflags = '-C target-cpu=native -C link-arg=' + str(snapshot / 'config.o')
    command_results = []
    for command in commands:
        env = dict(os.environ, RUSTFLAGS=rustflags) if command[0] == args.cargo else None
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=180)
        command_results.append({'command': command, 'exit_code': result.returncode,
                                'stdout': result.stdout, 'stderr': result.stderr})
        save(directory / 'commands.json', command_results)
        result.check_returncode()
    for name in ['rust-http', 'http-load']:
        shutil.copy2(directory / 'rust-target/release' / name, directory / name)
    rust_version = capture(['rustc', '-Vv'])
    host_target = next(line.split(': ', 1)[1] for line in rust_version.splitlines() if line.startswith('host: '))
    # Target filtering keeps Linux provenance independent of unbuilt Windows
    # crates that Cargo.lock also names but which need not be cached offline.
    package_metadata = json.loads(capture([args.cargo, 'metadata', '--locked', '--offline',
                                          '--filter-platform', host_target, '--format-version', '1',
                                          '--manifest-path', str(snapshot / 'Cargo.toml')]))
    dependencies = []
    for package in package_metadata['packages']:
        if package['source']:
            root = Path(package['manifest_path']).parent
            dependencies.append({'name': package['name'], 'version': package['version'],
                                 'source': package['source'], 'manifest_sha256': sha(root / 'Cargo.toml'),
                                 'cargo_checksum_sha256': sha(root / '.cargo-checksum.json') if (root / '.cargo-checksum.json').exists() else None,
                                 'source_file_sha256': {str(path.relative_to(root)): sha(path)
                                                        for path in root.rglob('*') if path.is_file()}})
    metadata = {'artifacts': artifacts, 'commands': commands, 'command_results': command_results,
                'rustflags': rustflags, 'dependencies': dependencies,
                'cc_version': capture([args.cc, '--version']), 'rust_version': rust_version,
                'host_target': host_target,
                'source_state_observation': {name: source_state(ROOT.parent / name) for name in ['forge', 'forge-runtime', 'forge-stdlib']},
                'snapshot_sha256': {str(path.relative_to(snapshot)): sha(path) for path in snapshot.rglob('*') if path.is_file()},
                'runner_sha256': sha(Path(__file__)),
                'binary_sha256': {name: sha(directory / name) for name in ['forge-http', 'rust-http', 'http-load']}}
    save(directory / 'build.json', metadata)
    return metadata


def markdown(report, output):
    lines = ['# Prepared HTTP backend comparison — observer protocol v2', '',
             'V2 adds bounded connect_timeout, per-stage connect/setup/write/read/EOF durations, immediate per-attempt TSV writes and passive kernel observations. Its observer overhead and failure behavior differ from V1; these reports must remain separate.', '',
             'This compares Forge `http_prepare` + `http_serve_mt` against pinned socket2/libc Rust with owned sockets and the same prepared-response policy. It consumes complete headers without parsing routing, method, Host or body semantics. It cannot establish a full HTTP framework or language-wide 110% claim.', '',
             '| Body bytes | Workers | Concurrent clients | Forge requests/s | Rust requests/s | Paired throughput ratio (95% interval) | 1.10 target |',
             '| ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for row in report['summary']:
        low, high = row['ci95']
        lines.append(f'| {row["body_bytes"]} | {row["workers"]} | {row["concurrency"]} | {row["forge_median_rps"]:.1f} | {row["rust_median_rps"]:.1f} | {row["paired_ratio_median"]:.4f} [{low:.4f}, {high:.4f}] | {row["target_status"]} |')
    lines += ['',
              'Ratio = Rust elapsed / Forge elapsed for the same fixed request count. Every request uses a new loopback TCP connection, a dynamic seeded path and header padding; both servers receive the same request byte sequence and prepare the same dynamic seeded ASCII body. Every returned byte, status/header order, Content-Length and EOF is checked against a response file constructed independently in Python. Each per-request latency and any error remains in the raw TSV files. Independent Python probes also verify complete response bytes, large headers and fragmentation across the header terminator; premature responses fail validation.', '',
              'Pairs are order-balanced per configuration, shuffled reproducibly, and use same-input prewarming for each language. There are no excluded failures, silent retries or discarded timing outliers. A failure aborts the report and preserves previous samples plus the failed attempt. The interval is a 10,000-resample percentile bootstrap of within-pair ratio medians, not family-wise and not a guarantee across machines.', '',
              'Both backends use one main serving thread for one worker; multi-worker runs use exactly N pinned OS serving threads plus one idle main. Each worker owns a SO_REUSEPORT listening socket, uses level-triggered epoll and at most 256 accepts per readiness visit, switches accepted NONBLOCK+CLOEXEC sockets to blocking, reads up to 8,191 header bytes, applies 5-second receive/send timeouts, sends a cached response and closes. Socket backlog is 8,192 and listening receive/send buffers request 65,536 bytes. These are policy equivalences; Rust uses idiomatic Read/Write with RAII, Arc-owned shared bytes and standard write_all, while Forge uses native C helpers. Rust does not intentionally reproduce resource leaks or error-handling defects. No full semantic parser, keepalive, request body, TLS, database work, coroutine or async I/O policy is measured.', '',
              'Shared C provides CPU configuration only: the Forge worker affinity call is intercepted at link time to map worker indices to the configured physical CPUs; Rust calls that same configuration helper. It contains no HTTP or measured algorithm. Before/after /proc thread audits check exact counts and affinities; client threads are restricted to disjoint physical cores. Both processes receive the same file-descriptor and memlock limits. The runner retains generated C, all source/archive/compiler/header hashes, pinned lock/dependency identities, full commands, output logs and the executed runner source.', '',
              'The shared Rust load observer uses closed-loop OS threads and fixed completed request counts. The interval spans barrier release, all requests and final client thread joins; server startup/probes/prewarming and client response preparation/thread creation are excluded. Full-process CPU/RSS and timed server CPU counters are separate diagnostics. Client generation, checking and kernel loopback work can limit throughput; client CPU occupancy, finite bursts, source-port reuse/TIME_WAIT, kernel scheduling, response sizes and shared-host frequency remain caveats. These results describe this complete connection-per-request benchmark, not isolated maximum server capacity. A target result applies only to an explicitly listed configuration with passing correctness gates.', '',
              f'Raw run, build provenance and every attempt: [{output.name}]({output.name}); associated raw directory: `{report["raw_directory"]}`.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--forge', type=Path)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--cargo', default='cargo')
    parser.add_argument('--workers', type=int, nargs='+', default=[1, 2, 4])
    parser.add_argument('--concurrency', type=int, nargs='+', default=[16, 64])
    parser.add_argument('--body-bytes', type=int, nargs='+', default=[32, 4096])
    parser.add_argument('--requests', type=int, default=12000)
    parser.add_argument('--pairs', type=int, default=16)
    parser.add_argument('--client-cores', type=int, default=2)
    parser.add_argument('--connect-timeout-ms', type=int, default=10000)
    parser.add_argument('--random-seed', type=int, default=20261012)
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-build', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    cpus = physical_cpus()
    if (not args.workers or len(set(args.workers)) != len(args.workers) or
            any(value not in (1, 2, 4) for value in args.workers) or
            args.client_cores < 1 or max(args.workers) + args.client_cores > len(cpus) or
            not 1 <= args.connect_timeout_ms <= 60000 or
            args.pairs < 8 or args.pairs % 2 or args.requests < max(args.concurrency) or
            any(value < 1 or value > 512 for value in args.concurrency) or
            any(value < 1 or value > 65536 for value in args.body_bytes)):
        parser.error('Require unique 1/2/4 workers, disjoint physical cores, even >=8 pairs and valid positive dimensions')
    if not args.build_only and (args.output.exists() or args.output.with_suffix('.md').exists()):
        parser.error('Preserve reports: choose a fresh output')
    metadata = build(args)
    if args.build_only:
        print('Built immutable HTTP snapshot: ' + str(args.build_dir.resolve()))
        return
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix('.raw')
    raw.mkdir()
    source = Path(__file__).read_text()
    (raw / 'executed-runner.py').write_text(source)
    client_cpus = cpus[max(args.workers):max(args.workers) + args.client_cores]
    report = {'status': 'running', 'protocol': PROTOCOL, 'started_at_utc': stamp(), 'build': metadata,
              'raw_directory': str(raw), 'measurement_runner_source': source,
              'measurement_runner_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'environment': {'platform': platform.platform(), 'lscpu': capture(['lscpu']),
                              'physical_cpu_candidates': cpus, 'client_cpus': client_cpus,
                              'load_average_start': os.getloadavg(),
                              'rlimits_parent': {name: resource.getrlimit(getattr(resource, name)) for name in ['RLIMIT_NOFILE', 'RLIMIT_MEMLOCK']},
                              'kernel_tcp': {str(path): path.read_text().strip() for path in [Path('/proc/sys/net/ipv4/ip_local_port_range'), Path('/proc/sys/net/ipv4/tcp_tw_reuse'), Path('/proc/sys/net/core/somaxconn')] if path.exists()}},
              'method': {'protocol': PROTOCOL, 'connect_timeout_ms': args.connect_timeout_ms,
                         'observer_rows': 'every completed attempt immediately written under mutex to unbuffered File; OS page-cache persistence, no fsync/power-loss guarantee',
                         'observer_failure_policy': 'stop launching new requests on first error; all in-flight attempts finish/time out and are retained; fail whole trial without retry',
                         'passive_observations': 'before/after global kernel TCP counters, per-port socket states and limits; causal attribution unproven',
                         'pairs': args.pairs, 'requests_per_sample': args.requests,
                         'worker_configurations': args.workers, 'concurrency_configurations': args.concurrency,
                         'body_byte_configurations': args.body_bytes, 'random_seed': args.random_seed,
                         'ordering': 'independently balanced shuffled paired orders per configuration',
                         'scope': 'closed-loop fixed-count TCP connect + dynamic request write + exact response read/EOF/check + client worker joins',
                         'prewarm': 'same input fixed-count complete checked load immediately before every measured sample',
                         'excluded_failures_or_outliers': 0,
                         'c_bridge': 'worker CPU configuration only; link wrap changes affinity mapping, no generated-C adapter or HTTP algorithm'},
              'correctness_checks': [], 'warmups': [], 'measurements': [], 'summary': []}
    save(output, report)
    binaries = {name: args.build_dir.resolve() / (name + '-http') for name in ['forge', 'rust']}
    load = args.build_dir.resolve() / 'http-load'
    try:
        for workers in args.workers:
            for body_size in args.body_bytes:
                for name, binary in binaries.items():
                    prefix = raw / f'check-{name}-w{workers}-b{body_size}'
                    row = correctness(binary, workers, cpus[:workers], 71, body_size, prefix)
                    report['correctness_checks'].append({'language': name, **row})
                    save(output, report)
        if args.validate_only:
            # Bounded observer smoke runs exercise all request IDs, load
            # readiness/barrier, logs/cleanup and independent response files.
            for name, binary in binaries.items():
                workers = args.workers[0]
                concurrency = min(args.concurrency)
                row = trial(binary, load, workers, concurrency, max(137, concurrency), 97,
                            args.body_bytes[0], cpus[:workers], client_cpus, raw / ('smoke-' + name),
                            args.connect_timeout_ms)
                report['correctness_checks'].append({'language': name, 'observer_smoke': True, **row})
                save(output, report)
            report['status'] = 'validation_passed_no_performance_measurements'
            return
        configurations = [(body, workers, concurrent) for body in args.body_bytes
                          for workers in args.workers for concurrent in args.concurrency]
        rng = random.Random(args.random_seed)
        orders = {key: [False, True] * (args.pairs // 2) for key in configurations}
        for values in orders.values():
            rng.shuffle(values)
        for pair in range(args.pairs):
            sequence = configurations.copy(); rng.shuffle(sequence)
            for body_size, workers, concurrency in sequence:
                key = (body_size, workers, concurrency)
                seed = rng.randrange(1, 1000000000)
                order = ['forge', 'rust'] if orders[key][pair] else ['rust', 'forge']
                for position, name in enumerate(order):
                    for kind in ['prewarm', 'measurement']:
                        prefix = raw / f'p{pair:03d}-b{body_size}-w{workers}-c{concurrency}-{position}-{name}-{kind}'
                        row = trial(binaries[name], load, workers, concurrency, args.requests,
                                    seed, body_size, cpus[:workers], client_cpus, prefix,
                                    args.connect_timeout_ms)
                        record = {'pair': pair, 'order': position, 'language': name, **row}
                        report['warmups' if kind == 'prewarm' else 'measurements'].append(record)
                        save(output, report)
            print('Completed HTTP pair ' + str(pair + 1), flush=True)
        for body_size, workers, concurrency in configurations:
            samples = [row for row in report['measurements'] if (row['body_bytes'], row['workers'], row['concurrency']) == (body_size, workers, concurrency)]
            ratios = []
            for pair in range(args.pairs):
                paired = {row['language']: row for row in samples if row['pair'] == pair}
                ratios.append(paired['rust']['elapsed_ns'] / paired['forge']['elapsed_ns'])
            interval = confidence(ratios, args.random_seed + workers + body_size + concurrency)
            report['summary'].append({'body_bytes': body_size, 'workers': workers, 'concurrency': concurrency,
                                      'forge_median_rps': statistics.median(row['requests_per_second'] for row in samples if row['language'] == 'forge'),
                                      'rust_median_rps': statistics.median(row['requests_per_second'] for row in samples if row['language'] == 'rust'),
                                      'paired_ratios': ratios, 'paired_ratio_median': statistics.median(ratios), 'ci95': interval,
                                      'target_status': 'supported for this benchmark configuration' if interval[0] >= 1.10 else 'below target' if interval[1] < 1.10 else 'inconclusive'})
        report['status'] = 'completed'
        output.with_suffix('.md').write_text(markdown(report, output))
    except BaseException as error:
        report.update(status='failed_no_claim', error=repr(error))
        raise
    finally:
        # This includes the currently failed/incomplete attempt even when it
        # never returned to the measurement loop. Failures are evidence.
        report['attempt_records'] = {str(path.relative_to(raw)): json.loads(path.read_text())
                                     for path in sorted(raw.glob('*.json'))}
        report['finished_at_utc'] = stamp()
        report['environment']['load_average_end'] = os.getloadavg()
        save(output, report)


if __name__ == '__main__':
    main()
