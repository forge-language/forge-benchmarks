#!/usr/bin/env python3
"""Controlled peers test cohort simultaneity, byte checking and failure retention."""
import socket
import threading
import unittest

from http_cohort_compare import observe, percentile


class CohortTests(unittest.TestCase):
    def peer(self, count, response, reply=None, stall=False):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(count)
        listener.settimeout(3)
        failures = []
        ready = threading.Event()
        release = threading.Event()

        def serve():
            sockets = []
            try:
                for _ in range(count):
                    sock, _ = listener.accept()
                    sockets.append(sock)
                ready.set()
                for sock in sockets:
                    sock.settimeout(3)
                    data = b""
                    while b"\r\n\r\n" not in data:
                        data += sock.recv(4096)
                    self.assertEqual(data, b"GET / HTTP/1.1\r\n\r\n")
                    sock.sendall(response if reply is None else reply)
                    if not stall:
                        sock.close()
                if stall:
                    release.wait(3)
            except Exception as error:
                failures.append(error)
            finally:
                for sock in sockets:
                    sock.close()
                listener.close()

        thread = threading.Thread(target=serve)
        thread.start()
        return listener.getsockname()[1], thread, failures, ready, release

    def observe_peer(self, response=b"hello", reply=None, stall=False):
        port, thread, failures, ready, release = self.peer(4, response, reply, stall)
        try:
            result = observe(port, 4, response, b"GET / HTTP/1.1\r\n\r\n",
                             setup_seconds=1, io_seconds=.1 if stall else 2)
        finally:
            release.set()
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(ready.is_set())
        return result

    def test_complete_cohort_and_end_to_end_clock(self):
        result = self.observe_peer()
        self.assertEqual((result["released_cohort"], result["connected_before_release"]), (4, 4))
        self.assertEqual((result["completed"], result["errors"]), (4, 0))
        for row in result["rows"]:
            self.assertGreaterEqual(row["latency_ns"], row["release_to_eof_ns"])
            self.assertEqual(row["response_bytes"], 5)
        self.assertGreater(result["setup_ns"], 0)

    def test_wrong_bytes_fail_every_lane(self):
        result = self.observe_peer(reply=b"jello")
        self.assertEqual(result["errors"], 4)
        self.assertEqual({r["stage"] for r in result["rows"]}, {"response"})

    def test_short_response_is_failure(self):
        result = self.observe_peer(reply=b"he")
        self.assertEqual(result["errors"], 4)
        self.assertEqual({r["stage"] for r in result["rows"]}, {"eof"})

    def test_extra_bytes_are_failure(self):
        self.assertEqual(self.observe_peer(reply=b"hello!")["errors"], 4)

    def test_valid_response_without_eof_is_timeout(self):
        self.assertEqual(self.observe_peer(stall=True)["errors"], 4)

    def test_refused_connect_does_not_release_partial_cohort(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.close()
        result = observe(port, 4, b"hello", b"GET / HTTP/1.1\r\n\r\n", .1, .1)
        self.assertEqual(result["released_cohort"], 0)
        self.assertEqual(result["errors"], 4)
        self.assertEqual([r["id"] for r in result["rows"]], list(range(4)))

    def test_nearest_rank_percentile(self):
        self.assertEqual(percentile(list(range(1, 101)), .99), 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
