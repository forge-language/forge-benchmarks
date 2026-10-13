#!/usr/bin/env python3
"""Bounded observer correctness tests. Requires an already built HTTP observer.

No builds, benchmarking, external addresses, retries or packet-filter changes.
Run only after the benchmark coordinator authorizes test execution. Every test
has a supervisor deadline; successful and deliberately failing peer responses,
stdout/stderr, request rows and metadata are preserved in a fresh evidence dir.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import threading
import time
import unittest

OPTIONS = None
COLUMNS = ['id', 'latency_ns', 'connect_ns', 'setup_ns', 'write_ns', 'read_ns',
           'eof_ns', 'response_bytes', 'failed_stage', 'error']
PHASES = ['connect_ns', 'setup_ns', 'write_ns', 'read_ns', 'eof_ns']


def expected_packet(seed):
    body = f'independent-observer-validation-{seed}'.encode()
    return (f'HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode() + body)


def rows(path):
    text = path.read_text()
    # A concurrently observed trailing partial line is not a complete record.
    if not text.endswith('\n'):
        text = text.rsplit('\n', 1)[0] + '\n'
    reader = csv.DictReader(io.StringIO(text), delimiter='\t')
    if reader.fieldnames != COLUMNS:
        raise AssertionError('Unexpected observer schema')
    return list(reader)


class Peer:
    """Disposable bounded loopback peer; no production server code reused."""
    def __init__(self, directory, behavior):
        self.directory, self.behavior = directory, behavior
        self.exit = threading.Event()
        self.lock = threading.Lock()
        self.connections, self.threads, self.requests, self.exceptions = [], [], [], []
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(32)
        self.listener.settimeout(.1)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.accept, daemon=True)
        self.thread.start()

    def accept(self):
        while not self.exit.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self.lock:
                self.connections.append(connection)
            worker = threading.Thread(target=self.handle, args=(connection,), daemon=True)
            self.threads.append(worker)
            worker.start()

    def handle(self, connection):
        try:
            with connection:
                connection.settimeout(2)
                request = bytearray()
                while b'\r\n\r\n' not in request:
                    block = connection.recv(8192)
                    if not block:
                        raise RuntimeError('Observer closed before writing a full request')
                    request.extend(block)
                    if len(request) > 8192:
                        raise RuntimeError('Unexpected test request length')
                with self.lock:
                    self.requests.append(bytes(request).decode('ascii'))
                self.behavior(connection, bytes(request), self.exit)
        except BaseException as error:
            with self.lock:
                self.exceptions.append(repr(error))

    def close(self):
        self.exit.set()
        self.listener.close()
        with self.lock:
            connections = self.connections.copy()
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.thread.join(1)
        for thread in self.threads:
            thread.join(1)
        (self.directory / 'peer.json').write_text(json.dumps(
            {'port': self.port, 'requests': self.requests, 'exceptions': self.exceptions,
             'all_threads_stopped': not self.thread.is_alive() and not any(t.is_alive() for t in self.threads)}, indent=2) + '\n')
        if self.thread.is_alive() or any(thread.is_alive() for thread in self.threads):
            raise RuntimeError('Controlled peer exceeded its cleanup bound')


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = OPTIONS.evidence_dir / self._testMethodName
        self.directory.mkdir()
        self.seed = 7931
        self.expected = expected_packet(self.seed)
        self.response_path = self.directory / 'expected-response.bin'
        self.response_path.write_bytes(self.expected)
        self.output_path = self.directory / 'requests.tsv'
        self.children, self.peers = [], []
        self.metadata = {'test': self._testMethodName, 'kind': 'controlled correctness test; no performance claim',
                         'seed': self.seed, 'status': 'running',
                         'expected_sha256': hashlib.sha256(self.expected).hexdigest()}
        self.store()

    def store(self):
        (self.directory / 'test.json').write_text(json.dumps(self.metadata, indent=2) + '\n')

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(1)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(1)
            if child.stdout and not child.stdout.closed:
                remainder = child.stdout.read()
                with (self.directory / 'observer.stdout').open('ab') as destination:
                    destination.write(remainder)
                child.stdout.close()
            child.test_stderr.close()
        for peer in self.peers:
            peer.close()
        if self.output_path.exists():
            self.metadata['request_rows_sha256'] = hashlib.sha256(self.output_path.read_bytes()).hexdigest()
            self.metadata['retained_complete_rows'] = len(rows(self.output_path))
        self.metadata['status'] = 'finished; see suite outcomes for pass/fail'
        self.store()

    def peer(self, behavior):
        peer = Peer(self.directory, behavior)
        self.peers.append(peer)
        return peer

    def start(self, port, requests=1, concurrency=1, timeout_ms=200):
        command = [str(OPTIONS.load_binary), *map(str, [port, concurrency, requests, self.seed]),
                   str(self.response_path), str(self.output_path), str(timeout_ms)]
        error_output = (self.directory / 'observer.stderr').open('xb')
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=error_output, start_new_session=True,
                                 preexec_fn=lambda: os.sched_setaffinity(0, {OPTIONS.cpu}))
        child.test_stderr = error_output
        self.children.append(child)
        self.metadata.update(command=command, cpu=OPTIONS.cpu, supervisor_deadline_seconds=OPTIONS.deadline)
        self.metadata.update(requested=requests, configured_concurrency=concurrency)
        self.store()
        self.assertTrue(select.select([child.stdout], [], [], OPTIONS.deadline)[0], 'Readiness deadline')
        self.assertEqual(child.stdout.readline(), b'ready\n')
        (self.directory / 'observer.stdout').write_bytes(b'ready\n')
        child.stdin.write(b'go\n'); child.stdin.flush(); child.stdin.close(); child.stdin = None
        return child

    def finish(self, child):
        # Deadline failure is recorded as a failed test; it is never retried.
        child.wait(OPTIONS.deadline)
        output = child.stdout.read()
        with (self.directory / 'observer.stdout').open('ab') as destination:
            destination.write(output)
        child.stdout.close()
        self.assertEqual(child.returncode, 0)
        footer = output.strip().split(b'\t')
        self.assertIn(len(footer), [6] if OPTIONS.require_peaks else [3, 6])
        elapsed, attempts, errors = map(int, footer[:3])
        if len(footer) == 6:
            active, connected, pending = map(int, footer[3:])
            self.assertTrue(0 <= connected <= active <= min(attempts, self.metadata['configured_concurrency']))
            self.assertTrue(0 <= pending <= min(256, active))
            self.assertLessEqual(active, connected + pending)
            self.metadata['observed_peaks'] = dict(inflight=active, connected=connected, pending=pending)
        self.metadata.update(observer_elapsed_ns=elapsed, attempts=attempts, errors=errors,
                             observer_exit_code=child.returncode)
        self.store()
        observed = rows(self.output_path)
        self.assertEqual(len(observed), attempts)
        self.assertEqual(sum(bool(row['error']) for row in observed), errors)
        for row in observed:
            self.assertTrue(all(row.get(key) is not None for key in COLUMNS))
            self.assertGreater(int(row['latency_ns']), 0)
            self.assertTrue(all(int(row[key]) >= 0 for key in PHASES))
            self.assertLessEqual(sum(int(row[key]) for key in PHASES), int(row['latency_ns']))
        return observed, attempts, errors

    def test_exact_response_and_all_request_ids(self):
        peer = self.peer(lambda connection, request, exit: connection.sendall(self.expected))
        observed, attempts, errors = self.finish(self.start(peer.port, requests=23, concurrency=4))
        self.assertEqual((attempts, errors), (23, 0))
        self.assertEqual(sorted(int(row['id']) for row in observed), list(range(23)))
        self.assertTrue(all(int(row['response_bytes']) == len(self.expected) and not row['failed_stage'] for row in observed))

    def test_observed_connected_peak_with_peer_barrier(self):
        if not OPTIONS.require_peaks:
            self.skipTest('Requires V3.3 peak gauges')
        barrier = threading.Barrier(4)
        def respond(connection, request, exit):
            # No request can finish before all four full requests reach the peer.
            barrier.wait(timeout=2)
            connection.sendall(self.expected)
        peer = self.peer(respond)
        _, attempts, errors = self.finish(self.start(peer.port, requests=4, concurrency=4, timeout_ms=1000))
        self.assertEqual((attempts, errors), (4, 0))
        self.assertEqual(self.metadata['observed_peaks']['inflight'], 4)
        self.assertEqual(self.metadata['observed_peaks']['connected'], 4)

    def test_read_and_eof_durations_are_separate(self):
        def respond(connection, request, exit):
            exit.wait(.12)
            connection.sendall(self.expected[:17])
            exit.wait(.06)
            connection.sendall(self.expected[17:])
            exit.wait(.12)
        peer = self.peer(respond)
        observed, attempts, errors = self.finish(self.start(peer.port))
        self.assertEqual((attempts, errors), (1, 0))
        self.assertGreater(int(observed[0]['read_ns']), 80_000_000)
        self.assertGreater(int(observed[0]['eof_ns']), 40_000_000)

    def test_mutated_same_length_response_fails(self):
        malformed = self.expected[:-1] + bytes([self.expected[-1] ^ 1])
        peer = self.peer(lambda connection, request, exit: connection.sendall(malformed))
        observed, attempts, errors = self.finish(self.start(peer.port, requests=100))
        self.assertEqual((attempts, errors), (1, 1))
        # Epoll checks bytes incrementally during Read; V2 checks the full packet.
        self.assertEqual(observed[0]['failed_stage'], 'read' if OPTIONS.require_peaks else 'response')
        self.assertEqual(int(observed[0]['response_bytes']), len(self.expected))

    def test_early_eof_preserves_actual_partial_bytes(self):
        peer = self.peer(lambda connection, request, exit: connection.sendall(self.expected[:-3]))
        observed, attempts, errors = self.finish(self.start(peer.port, requests=100))
        self.assertEqual((attempts, errors), (1, 1))
        self.assertEqual(observed[0]['failed_stage'], 'read')
        self.assertEqual(int(observed[0]['response_bytes']), len(self.expected) - 3)

    def test_extra_byte_fails_eof_check(self):
        peer = self.peer(lambda connection, request, exit: connection.sendall(self.expected + b'x'))
        observed, attempts, errors = self.finish(self.start(peer.port))
        self.assertEqual((attempts, errors), (1, 1))
        self.assertEqual(observed[0]['failed_stage'], 'eof')
        self.assertEqual(int(observed[0]['response_bytes']), len(self.expected) + 1)

    def test_concurrent_failure_retains_every_finished_attempt(self):
        malformed = self.expected[:-1] + b'!'
        peer = self.peer(lambda connection, request, exit: connection.sendall(malformed))
        observed, attempts, errors = self.finish(self.start(peer.port, requests=100, concurrency=4))
        self.assertGreaterEqual(attempts, 1)
        self.assertLessEqual(attempts, 4)
        self.assertEqual(errors, attempts)
        self.assertEqual(len(set(row['id'] for row in observed)), attempts)
        mismatch_stage = 'read' if OPTIONS.require_peaks else 'response'
        self.assertTrue(all(row['failed_stage'] == mismatch_stage for row in observed))

    def test_completed_row_survives_supervisor_termination(self):
        second_inflight = threading.Event()
        def respond(connection, request, exit):
            path = request.split(b' ', 2)[1]
            identifier = int(path.rsplit(b'/', 1)[1])
            if identifier == 0:
                connection.sendall(self.expected)
            else:
                second_inflight.set()
                exit.wait(OPTIONS.deadline)
        peer = self.peer(respond)
        child = self.start(peer.port, requests=3)
        self.assertTrue(second_inflight.wait(OPTIONS.deadline))
        deadline = time.monotonic() + OPTIONS.deadline
        while time.monotonic() < deadline:
            current = rows(self.output_path)
            if len(current) == 1:
                break
            time.sleep(.005)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['id'], '0')
        self.assertFalse(current[0]['error'])
        self.assertIsNone(child.poll(), 'Observer must still be holding the second request')
        before = self.output_path.read_bytes()
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(1)
        self.assertEqual(child.returncode, -signal.SIGTERM)
        self.assertEqual(self.output_path.read_bytes(), before)
        self.metadata.update(deliberate_supervisor_termination=True,
                             incomplete_inflight_id=1, retained_completed_id=0)
        self.store()

    def test_connect_timeout_with_saturated_loopback_queue(self):
        # Linux's listen(0) accepts one established socket into its undrained
        # queue. A further SYN then waits without a completed connect. No
        # firewall, external address, privilege or application retry required.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(0)
            port = listener.getsockname()[1]
            with socket.create_connection(('127.0.0.1', port), timeout=2):
                encoded = f'{port:04X}'
                queue = [line.split()[4] for line in Path('/proc/net/tcp').read_text().splitlines()[1:]
                         if line.split()[1].split(':')[1] == encoded and line.split()[3] == '0A']
                self.assertEqual(len(queue), 1)
                self.assertGreaterEqual(int(queue[0].split(':')[1], 16), 1,
                                        'Saturated-queue fixture not established; no retry or skip')
                self.metadata['listener_queue_before'] = queue[0]
                self.store()
                observed, attempts, errors = self.finish(self.start(port, requests=100, timeout_ms=200))
        self.assertEqual((attempts, errors), (1, 1))
        self.assertEqual(observed[0]['failed_stage'], 'connect')
        self.assertIn('TimedOut', observed[0]['error'])
        self.assertGreaterEqual(int(observed[0]['connect_ns']), 120_000_000)
        self.assertLess(int(observed[0]['connect_ns']), 2_000_000_000)
        self.assertTrue(all(int(observed[0][key]) == 0 for key in PHASES if key != 'connect_ns'))


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load-binary', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=5)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--require-peaks', action='store_true', help='Require V3.3 footer and validate simultaneous connected states')
    OPTIONS = parser.parse_args()
    if not OPTIONS.load_binary.is_file() or OPTIONS.deadline <= 0 or OPTIONS.deadline > 10 or OPTIONS.cpu not in os.sched_getaffinity(0):
        parser.error('Require existing observer, allowed CPU and supervisor deadline <=10s')
    OPTIONS.load_binary = OPTIONS.load_binary.resolve()
    OPTIONS.evidence_dir = OPTIONS.evidence_dir.resolve()
    OPTIONS.evidence_dir.mkdir(parents=True)
    metadata = {'kind': 'bounded controlled-loopback observer validation; no performance claims',
                'binary_path': str(OPTIONS.load_binary),
                'binary_sha256': hashlib.sha256(OPTIONS.load_binary.read_bytes()).hexdigest(),
                'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'deadline_seconds': OPTIONS.deadline, 'cpu': OPTIONS.cpu}
    (OPTIONS.evidence_dir / 'executed-test-source.py').write_bytes(Path(__file__).read_bytes())
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ObserverTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    metadata.update(tests_run=result.testsRun, successful=result.wasSuccessful(),
                    failures=[{'test': str(test), 'traceback': error} for test, error in result.failures],
                    errors=[{'test': str(test), 'traceback': error} for test, error in result.errors],
                    skipped=[{'test': str(test), 'reason': reason} for test, reason in result.skipped])
    (OPTIONS.evidence_dir / 'suite.json').write_text(json.dumps(metadata, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
