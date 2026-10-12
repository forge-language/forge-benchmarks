#!/usr/bin/env python3
"""Controlled loopback correctness checks for the separately versioned epoll observer."""
import argparse
import csv
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


class Peer:
    def __init__(self, behavior):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(32)
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.behavior = behavior
        self.stop = threading.Event()
        self.errors = []
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self.handle, args=(connection,), daemon=True).start()

    def handle(self, connection):
        with connection:
            try:
                connection.settimeout(2)
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    block = connection.recv(4096)
                    if not block:
                        return
                    data.extend(block)
                self.behavior(connection, bytes(data))
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass
            except BaseException as error:
                self.errors.append(repr(error))

    def close(self):
        self.stop.set()
        self.listener.close()
        self.thread.join(1)


def packet(seed=17):
    body = f"epoll-test-{seed}".encode()
    return f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body


class EpollLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = str(OPTIONS.binary.resolve())

    def invoke(self, port, expected, connect_timeout=500, io_timeout=500, requests=1, concurrency=1):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            response_path, rows_path = directory / "expected.bin", directory / "rows.tsv"
            response_path.write_bytes(expected)
            child = subprocess.Popen(
                [self.binary, str(port), str(concurrency), str(requests), "17",
                 str(response_path), str(rows_path), str(connect_timeout), str(io_timeout)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(child.stdout.readline(), "ready\n")
            child.stdin.write("go\n")
            child.stdin.flush()
            child.stdin.close()
            child.stdin = None
            output, errors = child.communicate(timeout=4)
            self.assertEqual(child.returncode, 0, errors)
            footer = output.strip().split("\t")
            self.assertEqual(len(footer), 3, output)
            rows = list(csv.DictReader(rows_path.open(), delimiter="\t"))
            return tuple(map(int, footer)), rows

    def run_peer(self, behavior, **kwargs):
        peer = Peer(behavior)
        try:
            footer, rows = self.invoke(peer.port, packet(), **kwargs)
            self.assertFalse(peer.errors)
            return footer, rows
        finally:
            peer.close()

    def test_fragmented_exact_response_and_eof(self):
        expected = packet()
        def fragmented(connection, _request):
            for offset in range(0, len(expected), 3):
                connection.sendall(expected[offset:offset + 3])
        (elapsed, attempts, errors), rows = self.run_peer(fragmented)
        self.assertGreater(elapsed, 0)
        self.assertEqual((attempts, errors), (1, 0))
        self.assertEqual(rows[0]["failed_stage"], "")
        self.assertEqual(int(rows[0]["response_bytes"]), len(expected))
        self.assertGreater(int(rows[0]["eof_ns"]), 0)

    def test_short_response_fails_read(self):
        expected = packet()
        _, rows = self.run_peer(lambda connection, _request: connection.sendall(expected[:-2]))
        self.assertEqual(rows[0]["failed_stage"], "read")
        self.assertEqual(int(rows[0]["response_bytes"]), len(expected) - 2)

    def test_extra_byte_fails_eof(self):
        expected = packet()
        _, rows = self.run_peer(lambda connection, _request: connection.sendall(expected + b"!"))
        self.assertEqual(rows[0]["failed_stage"], "eof")
        self.assertEqual(int(rows[0]["response_bytes"]), len(expected) + 1)

    def test_same_length_mutation_fails_exact_comparison(self):
        expected = packet()
        changed = expected[:-1] + bytes([expected[-1] ^ 1])
        _, rows = self.run_peer(lambda connection, _request: connection.sendall(changed))
        self.assertEqual(rows[0]["failed_stage"], "read")
        self.assertEqual(int(rows[0]["response_bytes"]), len(expected))

    def test_read_timeout_is_recorded(self):
        entered = threading.Event()
        def stalls(connection, _request):
            entered.set()
            time.sleep(0.4)
        (elapsed, attempts, errors), rows = self.run_peer(stalls, io_timeout=100)
        self.assertTrue(entered.is_set())
        self.assertEqual((attempts, errors), (1, 1))
        self.assertEqual(rows[0]["failed_stage"], "read")
        self.assertIn("TimedOut", rows[0]["error"], rows[0])
        self.assertGreaterEqual(int(rows[0]["read_ns"]), 80_000_000)

    def test_readiness_after_deadline_is_still_a_timeout(self):
        expected = packet()
        def late_response(connection, _request):
            time.sleep(0.2)
            connection.sendall(expected)
        _, rows = self.run_peer(late_response, io_timeout=100)
        self.assertEqual(rows[0]["failed_stage"], "read")
        self.assertIn("TimedOut", rows[0]["error"], rows[0])

    def test_first_failure_stops_replacement_requests_and_retains_rows(self):
        expected = packet()
        wrong = expected[:-1] + bytes([expected[-1] ^ 1])
        _, rows = self.run_peer(lambda connection, _request: connection.sendall(wrong), requests=20, concurrency=4)
        self.assertGreaterEqual(len(rows), 1)
        self.assertLessEqual(len(rows), 4)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertTrue(all(row["failed_stage"] == "read" for row in rows))

    def test_mixed_ready_batch_does_not_refill_after_failure(self):
        expected = packet()
        wrong = expected[:-1] + bytes([expected[-1] ^ 1])
        barrier = threading.Barrier(4)
        def mixed_response(connection, request):
            path = request.split(b"\r\n", 1)[0].split()[1]
            request_id = int(path.rsplit(b"/", 1)[1])
            barrier.wait(timeout=2)
            connection.sendall(expected if request_id == 0 else wrong)
        _, rows = self.run_peer(mixed_response, requests=20, concurrency=4)
        self.assertGreaterEqual(len(rows), 1)
        self.assertLessEqual(len(rows), 4)
        self.assertIn("read", {row["failed_stage"] for row in rows})

    def test_connect_timeout_with_undrained_loopback_queue(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(0)
        held = socket.create_connection(listener.getsockname())
        try:
            footer, rows = self.invoke(listener.getsockname()[1], packet(), connect_timeout=150)
            self.assertEqual((footer[1], footer[2]), (1, 1))
            self.assertEqual(rows[0]["failed_stage"], "connect")
            self.assertIn("TimedOut", rows[0]["error"])
        finally:
            held.close()
            listener.close()


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    OPTIONS = parser.parse_args()
    if not OPTIONS.binary.is_file():
        parser.error("--binary must name the built http-load-epoll executable")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EpollLoadTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
