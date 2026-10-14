#!/usr/bin/env python3
"""Finite HTTP capacity grid using a barrier of established client connections.

All sockets connect before any GET is sent. End-to-end latency includes
connection setup and waiting at the barrier. This is a burst request cohort,
not application users, accepted server sockets, or sustained traffic.
"""
import argparse
import errno
import json
import math
import os
from pathlib import Path
import platform
import random
import selectors
import shutil
import socket
import time

import http_compare_v2 as v2
from cpu_compare import sha
from thread_compare import physical_cpus

PROTOCOL = "prepared-http-v4-connected-cohort"


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def observe(port, count, expected, request, setup_seconds=2, io_seconds=10,
            sources=8):
    """One selector thread; no retries; return every requested lane, even failures."""
    rows = []
    sockets = []
    released = None
    began = time.perf_counter_ns()
    selector = selectors.DefaultSelector()
    connected = 0
    setup_error = None

    def fail(row, stage, error):
        row.update(stage=stage, error=str(error), ended_ns=time.perf_counter_ns())

    try:
        for identifier in range(count):
            row = dict(id=identifier, started_ns=time.perf_counter_ns(), connected_ns=None,
                       ended_ns=None, sent_bytes=0, response_bytes=0, error="", stage="")
            rows.append(row)
            try:
                sock = socket.socket()
                sockets.append(sock)
                sock.setblocking(False)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.bind((f"127.0.0.{2 + identifier % sources}", 0))
                result = sock.connect_ex(("127.0.0.1", port))
                if result not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
                    raise OSError(result, os.strerror(result))
                selector.register(sock, selectors.EVENT_WRITE, row)
            except OSError as error:
                fail(row, "connect", error)
                setup_error = str(error)
                break
        deadline = time.monotonic() + max(0, setup_seconds - (time.perf_counter_ns() - began) / 1e9)
        while not setup_error and connected < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                setup_error = "cohort setup deadline"
                break
            for key, _ in selector.select(min(remaining, .05)):
                row = key.data
                error = key.fileobj.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if error:
                    fail(row, "connect", OSError(error, os.strerror(error)))
                    setup_error = row["error"]
                    break
                row["connected_ns"] = time.perf_counter_ns()
                connected += 1
                selector.unregister(key.fileobj)
        if not setup_error:
            # Verify that every connected socket is still open at the barrier.
            # No GET has been sent; a response or EOF here invalidates the cohort.
            for sock in sockets:
                try:
                    value = sock.recv(1, socket.MSG_PEEK)
                    setup_error = "unexpected bytes or EOF before release: " + repr(value)
                    break
                except BlockingIOError:
                    pass
                except OSError as error:
                    setup_error = str(error)
                    break
        if setup_error:
            for row in rows:
                if not row["error"]:
                    fail(row, "barrier", setup_error)
            while len(rows) < count:
                rows.append(dict(id=len(rows), started_ns=None, connected_ns=None,
                                 ended_ns=None, sent_bytes=0, response_bytes=0,
                                 error="not attempted after setup failure", stage="not_started"))
        else:
            released = time.perf_counter_ns()
            for sock, row in zip(sockets, rows):
                selector.register(sock, selectors.EVENT_WRITE, row)
            deadline = time.monotonic() + io_seconds
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    for key in list(selector.get_map().values()):
                        fail(key.data, "io_timeout", "cohort I/O deadline")
                        selector.unregister(key.fileobj)
                    break
                for key, mask in selector.select(min(remaining, .05)):
                    sock, row = key.fileobj, key.data
                    try:
                        if mask & selectors.EVENT_WRITE:
                            sent = sock.send(request[row["sent_bytes"]:])
                            if sent == 0:
                                raise OSError("zero-byte send")
                            row["sent_bytes"] += sent
                            if row["sent_bytes"] == len(request):
                                selector.modify(sock, selectors.EVENT_READ, row)
                        else:
                            chunk = sock.recv(4096)
                            if chunk:
                                offset = row["response_bytes"]
                                row["response_bytes"] += len(chunk)
                                if chunk != expected[offset:offset + len(chunk)]:
                                    fail(row, "response", "response bytes differ or exceed expected")
                                    selector.unregister(sock)
                            else:
                                if row["response_bytes"] != len(expected):
                                    fail(row, "eof", "short response")
                                else:
                                    row["ended_ns"] = time.perf_counter_ns()
                                selector.unregister(sock)
                    except BlockingIOError:
                        pass
                    except OSError as error:
                        fail(row, "write" if mask & selectors.EVENT_WRITE else "read", error)
                        selector.unregister(sock)
        ended = time.perf_counter_ns()
    finally:
        selector.close()
        for sock in sockets:
            sock.close()
    for row in rows:
        row["latency_ns"] = (row["ended_ns"] - row["started_ns"]
                             if row["ended_ns"] is not None and row["started_ns"] is not None else None)
        row["release_to_eof_ns"] = (row["ended_ns"] - released
                                    if released is not None and row["ended_ns"] is not None else None)
    errors = sum(bool(row["error"]) for row in rows)
    good = [row["latency_ns"] for row in rows if not row["error"]]
    return dict(requested=count, attempted=sum(row["started_ns"] is not None for row in rows),
                completed=count - errors, errors=errors, connected_before_release=connected,
                released_cohort=count if released is not None else 0,
                setup_error=setup_error, elapsed_ns=ended - began,
                setup_ns=released - began if released is not None else None,
                p99_ns=percentile(good, .99) if good else None,
                rps=(count - errors) * 1e9 / (ended - began), rows=rows)


def run_trial(binary, count, seed, cpus, prefix, args):
    body = v2.body_for(seed, 32)
    expected = v2.response_for(body)
    request = f"GET /cohort/{seed} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    server = None
    result = dict(status="running", language=binary.name, cohort=count, seed=seed)
    v2.save(prefix.with_suffix(".json"), result)
    try:
        server, port, command, audit = v2.start_server(binary, len(cpus), body, cpus, prefix)
        result.update(server_command=command, server_affinity=audit,
                      independent_probe=v2.exchange(port, request, expected),
                      kernel_before=v2.passive_kernel(port), expected_sha256=sha_bytes(expected))
        observed = observe(port, count, expected, request, args.setup_seconds, args.io_seconds)
        rows = observed.pop("rows")
        row_file = Path(str(prefix) + "-requests.json")
        v2.save(row_file, rows)
        result.update(observed, rows_file=str(row_file), rows_sha256=sha(row_file),
                      kernel_after=v2.passive_kernel(port), server_stats=v2.process_stats(server.pid),
                      server_affinity_after=v2.audit_workers(server.pid, cpus))
        result["slo_pass"] = (observed["errors"] == 0 and observed["released_cohort"] == count
                              and observed["p99_ns"] <= args.slo_ms * 1e6)
        result["status"] = "completed"
    except Exception as error:
        result.update(status="failed_no_claim", error=repr(error), slo_pass=False)
    finally:
        v2.stop(server)
        v2.save(prefix.with_suffix(".json"), result)
    return result


def sha_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--forge", type=Path)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--reuse-build", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--cohorts", nargs="+", type=int, default=[256, 512, 1024, 2048, 4096, 8192, 16384])
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--setup-seconds", type=float, default=2)
    parser.add_argument("--io-seconds", type=float, default=10)
    parser.add_argument("--slo-ms", type=float, default=1000)
    args = parser.parse_args()
    cpus = physical_cpus()
    if (min(args.cohorts) < 1 or max(args.cohorts) > 32768 or args.pairs < 4
            or args.pairs % 2 or not 1 <= args.workers < len(cpus)
            or not 0 < args.setup_seconds < 5 or args.io_seconds <= 0 or args.slo_ms <= 0):
        parser.error("invalid finite grid, balanced pairs, cores or deadlines")
    if args.output.exists() or args.output.with_suffix(".raw").exists():
        parser.error("use a fresh output to preserve every attempt")
    metadata = v2.build(args)
    if args.build_only:
        return
    raw = args.output.with_suffix(".raw")
    raw.mkdir(parents=True)
    for source in [Path(__file__), Path(v2.__file__)]:
        shutil.copy2(source, raw / source.name)
    report = dict(protocol=PROTOCOL, status="running", started=v2.stamp(), build=metadata,
                  observer_sha256=sha(Path(__file__)), platform=platform.platform(),
                  cpu_model=Path("/proc/cpuinfo").read_text(), server_cpus=cpus[:args.workers],
                  client_cpu=cpus[args.workers], config=vars(args).copy(), trials=[])
    report["config"] = {k: str(v) if isinstance(v, Path) else v for k, v in report["config"].items()}
    old_affinity = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, [cpus[args.workers]])
        for count in args.cohorts:
            orders = [["forge", "rust"], ["rust", "forge"]] * (args.pairs // 2)
            random.Random(20261014 + count).shuffle(orders)
            for pair, order in enumerate(orders):
                for language in order:
                    prefix = raw / f"cohort-{count}-pair-{pair}-{language}"
                    trial = run_trial(args.build_dir.resolve() / f"{language}-http", count,
                                      20261014 + pair, cpus[:args.workers], prefix, args)
                    trial.update(pair=pair, language=language, order=order)
                    report["trials"].append(trial)
                    v2.save(args.output, report)
                    print(count, pair, language, trial["status"], trial.get("errors"),
                          trial.get("p99_ns"), "SLO", trial["slo_pass"], flush=True)
        report.update(status="completed", ended=v2.stamp())
    finally:
        os.sched_setaffinity(0, old_affinity)
        v2.save(args.output, report)


if __name__ == "__main__":
    main()
