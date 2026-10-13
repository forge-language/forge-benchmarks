#!/usr/bin/env python3
"""Prepared HTTP V3 runner using the single-reactor Linux epoll observer.

V3 deliberately has its own runner, report protocol and client binary. The
Forge/Rust server builds and validation helpers are shared with V2, while V2's
blocking observer and timing protocol remain unchanged.
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
import statistics
import subprocess
import time

import http_compare_v2 as v2
from cpu_compare import confidence, sha
from thread_compare import physical_cpus

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "prepared-http-v3.3-observed-inflight-peaks"
FIXTURE = v2.FIXTURE
IO_TIMEOUT_MS = 10000


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def build(args):
    """Use V2's immutable server snapshot builder, then attest the V3 client."""
    metadata = v2.build(args)
    directory = args.build_dir.resolve()
    epoll_source = directory / "snapshot/src/load_epoll.rs"
    if not epoll_source.is_file():
        raise RuntimeError("Immutable snapshot lacks the V3 epoll source")
    artifact = directory / "rust-target/release/http-load-epoll"
    target = directory / "http-load-epoll"
    if args.reuse_build:
        if not target.is_file() or sha(target) != metadata.get("binary_sha256", {}).get("http-load-epoll"):
            raise RuntimeError("V3 epoll binary missing or changed in reused build")
    else:
        if not artifact.is_file():
            raise RuntimeError("Cargo build did not produce release/http-load-epoll")
        shutil.copy2(artifact, target)
        metadata.setdefault("binary_sha256", {})["http-load-epoll"] = sha(target)
        metadata["epoll_build"] = {
            "protocol": PROTOCOL,
            "cargo_command": metadata["commands"][-1],
            "cargo_target": "release/http-load-epoll",
            "manifest_sha256": sha(directory / "snapshot/Cargo.toml"),
            "lock_sha256": sha(directory / "snapshot/Cargo.lock"),
            "source_sha256": sha(epoll_source),
            "binary_sha256": sha(target),
            "build_profile": "Cargo release profile declared in the snapshotted manifest",
        }
        save(directory / "build.json", metadata)
    return metadata


def validate_request_rows(columns, rows, wanted, requested, attempted, completed, errors):
    if columns != wanted:
        raise RuntimeError(f"Epoll TSV schema mismatch: expected {wanted!r}, got {columns!r}")
    if len(rows) != attempted:
        raise RuntimeError(
            f"Epoll TSV row count {len(rows)} does not match observer footer attempted={attempted}"
        )
    failures = [row for row in rows if row.get("error") or row.get("failed_stage")]
    if errors or attempted != requested or completed != requested:
        detail = ""
        if failures:
            first = failures[0]
            detail = (
                f"; first failure id={first.get('id')} stage={first.get('failed_stage')}"
                f" error={first.get('error')}"
            )
        raise RuntimeError(
            f"Epoll observer failed: requested={requested}, attempted={attempted}, "
            f"completed={completed}, errors={errors}{detail}"
        )
    if len(rows) != requested:
        raise RuntimeError(f"Epoll TSV row count {len(rows)} does not match requested={requested}")


def parse_footer(line, concurrency, requests):
    footer = list(map(int, line.split(b"\t")))
    if len(footer) != 6:
        raise RuntimeError("V3.3 requires actual observed concurrency gauges")
    elapsed, attempted, errors, active, connected, pending = footer
    if not (elapsed > 0 and 0 <= errors <= attempted <= requests
            and 0 <= connected <= active <= min(concurrency, attempted)
            and 0 <= pending <= min(256, active)
            and active <= connected + pending
            and (attempted == errors or active > 0)):
        raise RuntimeError("Observer concurrency gauges or counters exceed physical/configured bounds")
    return footer


def run_trial(server_binary, load_binary, workers, concurrency, requests, seed,
              body_size, server_cpus, client_cpu, prefix, connect_timeout_ms,
              source_address_count, io_timeout_ms):
    body = v2.body_for(seed, body_size)
    expected = v2.response_for(body)
    response_path = Path(str(prefix) + "-expected.bin")
    response_path.write_bytes(expected)
    samples_path = Path(str(prefix) + "-requests.tsv")
    stdout_path = Path(str(prefix) + "-load.stdout")
    stderr_path = Path(str(prefix) + "-load.stderr")
    result = {
        "status": "running", "protocol": PROTOCOL, "workers": workers,
        "concurrency": concurrency, "requests": requests, "seed": seed,
        "source_address_count": source_address_count,
        "body_bytes": body_size, "connect_timeout_ms": connect_timeout_ms,
        "io_timeout_ms": io_timeout_ms,
        "observer_failure_policy": "first failure stops new requests; all in-flight attempts finish/time out and are retained; fail without retry",
        "observer_thread_model": "one epoll reactor thread; at most concurrency active sockets",
        "throughput_clock_scope": "observer internal timer after epoll/map setup, before event-vector allocation, through final request TSV write; excludes readiness/go handshake, footer printing and process exit; parent observer_wall_ns retained separately",
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "expected_response_sha256": sha(response_path),
        "expected_response_bytes": len(expected), "raw_prefix": str(prefix),
        "server_cpus": server_cpus, "client_cpus": [client_cpu],
    }
    save(prefix.with_suffix(".json"), result)
    server = client = None
    port = None
    try:
        server, port, command, audit = v2.start_server(server_binary, workers, body, server_cpus, prefix)
        result.update(server_command=command, server_affinity_before=audit)
        request = f"GET /probe/{seed} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
        result["independent_probe"] = v2.exchange(port, request, expected)
        load_command = [str(load_binary), *map(str, [port, concurrency, requests, seed]),
                        str(response_path), str(samples_path), str(connect_timeout_ms),
                        str(io_timeout_ms), str(source_address_count)]
        result["load_command"] = load_command
        env = dict(os.environ)
        with stderr_path.open("xb") as error_output:
            client = subprocess.Popen(load_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=error_output, env=env,
                                      preexec_fn=v2.preexec([client_cpu]), start_new_session=True)
            if not select.select([client.stdout], [], [], 15)[0]:
                raise RuntimeError("Epoll client readiness timeout")
            ready = client.stdout.readline()
            if ready != b"ready\n":
                raise RuntimeError("Epoll client readiness failed: " + repr(ready))
            client_audit = v2.affinities(client.pid)
            if len(client_audit) != 1 or any(set(value) != {client_cpu} for value in client_audit.values()):
                raise RuntimeError("Epoll observer must remain one thread pinned to its isolated client CPU")
            result["client_affinity"] = client_audit
            result["passive_kernel_before"] = v2.passive_kernel(port)
            result["server_stats_before"] = v2.process_stats(server.pid)
            started = time.perf_counter_ns()
            client.stdin.write(b"go\n")
            client.stdin.flush()
            client.stdin.close()
            client.stdin = None
            deadline = time.monotonic() + 180
            while True:
                pid, status, usage = os.wait4(client.pid, os.WNOHANG)
                if pid:
                    client.returncode = os.waitstatus_to_exitcode(status)
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Epoll client completion timeout (no retry)")
                time.sleep(.002)
            result["observer_wall_ns"] = time.perf_counter_ns() - started
            result["server_stats_after"] = v2.process_stats(server.pid)
            result["server_affinity_after"] = v2.audit_workers(server.pid, server_cpus)
            result["passive_kernel_after"] = v2.passive_kernel(port)
            output = ready + client.stdout.read()
            stdout_path.write_bytes(output)
            result["client_exit_code"] = client.returncode
            result["client_process_usage"] = {"user_seconds": usage.ru_utime,
                "system_seconds": usage.ru_stime, "peak_rss_kib": usage.ru_maxrss}
            if client.returncode:
                raise RuntimeError("Epoll client failed; see retained stderr " + str(stderr_path))
            lines = output.splitlines()
            if len(lines) != 2:
                raise RuntimeError("Malformed epoll observer stdout footer")
            elapsed, attempted, errors, peak_active, peak_connected, peak_pending = parse_footer(
                lines[1], concurrency, requests)
            result.update(elapsed_ns=elapsed, attempted_requests=attempted,
                          completed_requests=attempted - errors, errors=errors,
                          observed_peak_inflight_requests=peak_active,
                          observed_peak_connected_client_states=peak_connected,
                          observed_peak_pending_connects=peak_pending,
                          concurrency_gauge_scope="client request states through EOF handling; not accepted server sockets, sessions or users")

        with samples_path.open(newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            rows = list(reader)
            columns = reader.fieldnames
        wanted = ["id", "latency_ns", "connect_ns", "setup_ns", "write_ns", "read_ns",
                  "eof_ns", "response_bytes", "failed_stage", "error"]
        validate_request_rows(columns, rows, wanted, requests, attempted,
                              attempted - errors, errors)
        latencies = []
        phases = {name: [] for name in wanted[2:7]}
        ids = []
        for row in rows:
            identifier, latency = int(row["id"]), int(row["latency_ns"])
            ids.append(identifier)
            if latency <= 0 or int(row["response_bytes"]) != len(expected) or row["error"] or row["failed_stage"]:
                raise RuntimeError("Request failed exact response/EOF validation")
            for name in phases:
                value = int(row[name])
                if value < 0:
                    raise RuntimeError("Negative request phase duration")
                phases[name].append(value)
            if sum(int(row[name]) for name in phases) > latency:
                raise RuntimeError("Request stage intervals exceed total latency")
            latencies.append(latency)
        if sorted(ids) != list(range(requests)) or attempted != requests or errors or elapsed <= 0:
            raise RuntimeError("Incomplete request vector or failed observer; no timing claim")
        ordered = sorted(latencies)
        result.update(status="passed", all_request_ids_once=True, every_response_exact=True,
            request_samples_sha256=sha(samples_path), requests_per_second=requests * 1e9 / elapsed,
            phase_durations={name: {"median_ns": statistics.median(values),
                "p99_ns": sorted(values)[min(len(values) - 1, int(len(values) * .99))],
                "max_ns": max(values)} for name, values in phases.items()},
            latency_median_ns=statistics.median(latencies),
            latency_p99_ns=ordered[min(len(ordered) - 1, int(len(ordered) * .99))])
    except BaseException as error:
        result.update(status="failed", error=repr(error))
        raise
    finally:
        if port is not None and "passive_kernel_after" not in result:
            result["passive_kernel_on_failure"] = v2.passive_kernel(port)
        result["client_cleanup_usage"] = v2.stop(client)
        result["server_process_usage"] = v2.stop(server)
        if samples_path.exists():
            result["request_samples_sha256"] = sha(samples_path)
            with samples_path.open(newline="") as stream:
                retained = list(csv.DictReader(stream, delimiter="\t"))
            result["retained_request_rows"] = len(retained)
            result["retained_failed_rows"] = [row for row in retained if row.get("error") or row.get("failed_stage")]
        save(prefix.with_suffix(".json"), result)
    return result


def markdown(report, output):
    lines = ["# Prepared HTTP benchmark — observer protocol V3.3 (observed request-state peaks)", "",
        "A single Linux epoll client drives the prepared HTTP servers, binds across the configured 127/8 source addresses, caps pending connects at 256, and checks deadlines every 25 ms. V3.3 adds constant-time peak gauges and is reported separately from V1/V2/V3.2; do not pool timings across observer versions.", "",
        "| Body bytes | Workers | Configured ceiling | Forge req/s | Rust req/s | Forge peak in-flight / connected | Rust peak in-flight / connected | Paired Rust/Forge ratio (95% interval) | 1.10 target |",
        "| ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |"]
    for row in report["summary"]:
        low, high = row["ci95"]
        peaks = row['observed_peaks']
        forge, rust = peaks['forge'], peaks['rust']
        lines.append(f"| {row['body_bytes']} | {row['workers']} | {row['concurrency']} | {row['forge_median_rps']:.1f} | {row['rust_median_rps']:.1f} | {forge['inflight_min']}–{forge['inflight_max']} / {forge['connected_min']}–{forge['connected_max']} | {rust['inflight_min']}–{rust['inflight_max']} / {rust['connected_min']}–{rust['connected_max']} | {row['paired_ratio_median']:.4f} [{low:.4f}, {high:.4f}] | {row['target_status']} |")
    lines += ["", f"Every request uses a new loopback connection across {report['method']['source_address_count']} source addresses. The observer has one pinned reactor thread and at most the configured number of active sockets, with no more than 256 pending connects. It checks every response byte against an independently generated packet, then separately requires EOF. Partial/failed trials preserve completed TSV rows and fail the comparison without retries or excluded failures. Throughput uses the observer's internal timer, starting after epoll/map setup and before event-vector allocation, and ending after the final request TSV write. Connect, epoll work, deadline checks, response validation and TSV writes are timed. Readiness/go handshakes, footer printing and process exit are excluded; the parent go-to-exit observer_wall_ns is retained separately.", "",
        "Peak ranges are the minimum and maximum per-trial peaks among measured samples. In-flight includes pending connects and connected client request states; connected states last through response validation and EOF processing, and may outlive the server's socket. They do not measure accepted server sockets, sessions, users, or maximum capacity. The configured ceiling is a limit, not a measured population.", "",
        "The Forge and Rust server fixtures, server correctness probes, CPU setup, kernel snapshots, and paired-order statistics reuse the V2 runner helpers. The client source, runner, resulting binary hash, snapshot hashes and commands are retained in the build/report metadata. The client uses the same implementation for both server languages, so its work is part of the measured end-to-end loopback workload. Results do not establish general HTTP framework, TLS, keepalive, internet-facing capacity, or language-wide performance.", "",
        f"Raw run and retained attempts: [{output.name}]({output.name}); directory `{report['raw_directory']}`.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--forge", type=Path)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--concurrency", type=int, nargs="+", default=[16, 64])
    parser.add_argument("--body-bytes", type=int, nargs="+", default=[32, 4096])
    parser.add_argument("--requests", type=int, default=12000)
    parser.add_argument("--pairs", type=int, default=16)
    parser.add_argument("--connect-timeout-ms", type=int, default=10000,
                        help="per-phase connect timeout; capacity probes may require up to 180000 ms")
    parser.add_argument("--io-timeout-ms", type=int, default=IO_TIMEOUT_MS,
                        help="per-phase I/O timeout; capacity probes may require up to 180000 ms")
    parser.add_argument("--source-address-count", type=int, default=1,
                        help="spread client sockets across 127.0.0.1..127.0.0.N to expand ephemeral-port tuples")
    parser.add_argument("--random-seed", type=int, default=20261012)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--reuse-build", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    cpus = physical_cpus()
    if (not args.workers or len(set(args.workers)) != len(args.workers) or
        any(value not in (1, 2, 4) for value in args.workers) or
        max(args.workers) + 1 > len(cpus) or
        not 1 <= args.connect_timeout_ms <= 180000 or
        not 1 <= args.io_timeout_ms <= 180000 or args.pairs < 8 or args.pairs % 2 or
        args.requests < max(args.concurrency) or
        not 1 <= args.source_address_count <= 254 or
        any(value < 1 or value > 28232 * args.source_address_count for value in args.concurrency) or
        any(value < 1 or value > 65536 for value in args.body_bytes)):
        parser.error("Require unique 1/2/4 workers, one disjoint client CPU, even >=8 pairs and valid dimensions")
    if not args.build_only and (args.output.exists() or args.output.with_suffix(".md").exists()):
        parser.error("Preserve prior evidence: choose a fresh output path")
    metadata = build(args)
    if args.build_only:
        print("Built immutable V3 HTTP snapshot: " + str(args.build_dir.resolve()))
        return
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix(".raw")
    raw.mkdir()
    (raw / "executed-runner.py").write_text(Path(__file__).read_text())
    client_cpu = cpus[max(args.workers)]
    report = {"status": "running", "protocol": PROTOCOL, "started_at_utc": v2.stamp(),
        "build": metadata, "raw_directory": str(raw),
        "runner_sha256": sha(Path(__file__)),
        "helper_sha256": {name: sha(Path(module.__file__)) for name, module in
            [("http_compare_v2", v2),
             ("cpu_compare", __import__("cpu_compare")),
             ("thread_compare", __import__("thread_compare"))]},
        "environment": {"platform": platform.platform(), "lscpu": v2.capture(["lscpu"]),
            "physical_cpu_candidates": cpus, "client_cpu": client_cpu,
            "load_average_start": os.getloadavg(),
            "kernel_tcp": {str(path): path.read_text().strip() for path in [
                Path("/proc/sys/net/ipv4/ip_local_port_range"),
                Path("/proc/sys/net/ipv4/tcp_max_syn_backlog"),
                Path("/proc/sys/net/core/somaxconn")
            ] if path.exists()},
            "rlimits_parent": {name: resource.getrlimit(getattr(resource, name)) for name in ["RLIMIT_NOFILE", "RLIMIT_MEMLOCK"]}},
        "method": {"protocol": PROTOCOL, "io_timeout_ms": args.io_timeout_ms,
            "pairs": args.pairs, "requests_per_sample": args.requests,
            "worker_configurations": args.workers, "concurrency_configurations": args.concurrency,
            "source_address_count": args.source_address_count,
            "body_byte_configurations": args.body_bytes, "random_seed": args.random_seed,
            "scope": "single reactor; closed-loop fixed-count TCP connect + request write + exact response bytes + separate EOF + immediate TSV writes",
            "connect_window": "at most 256 pending TCP connects; the reactor polls and sends request bytes while additional lanes are launched; socket deadlines are checked every 25 ms instead of scanning all active sockets for every event batch",
            "observer_failure_policy": "stop new requests after first failure; drain active attempts; no retry",
            "timing_compatibility": "separate protocol; do not pool with V1, V2 or V3.2",
            "concurrency_gauge_scope": "client request states through EOF handling; not accepted server sockets, sessions or users"},
        "correctness_checks": [], "warmups": [], "measurements": [], "summary": []}
    save(output, report)
    servers = {name: args.build_dir.resolve() / (name + "-http") for name in ["forge", "rust"]}
    load = args.build_dir.resolve() / "http-load-epoll"
    try:
        for workers in args.workers:
            for body_size in args.body_bytes:
                for name, server_binary in servers.items():
                    row = v2.correctness(server_binary, workers, cpus[:workers], 71, body_size,
                        raw / f"check-{name}-w{workers}-b{body_size}")
                    report["correctness_checks"].append({"language": name, **row})
                    save(output, report)
        if args.validate_only:
            workers = args.workers[0]
            concurrency = min(args.concurrency)
            for name, server_binary in servers.items():
                row = run_trial(server_binary, load, workers, concurrency,
                    max(17, concurrency), 97, args.body_bytes[0], cpus[:workers], client_cpu,
                    raw / ("smoke-" + name), args.connect_timeout_ms,
                    args.source_address_count, args.io_timeout_ms)
                report["correctness_checks"].append({"language": name, "epoll_observer_smoke": True, **row})
                save(output, report)
            report["status"] = "validation_passed_no_performance_measurements"
            return
        configurations = [(body, workers, concurrent) for body in args.body_bytes
                          for workers in args.workers for concurrent in args.concurrency]
        rng = random.Random(args.random_seed)
        orders = {key: [False, True] * (args.pairs // 2) for key in configurations}
        for values in orders.values(): rng.shuffle(values)
        for pair in range(args.pairs):
            sequence = configurations.copy(); rng.shuffle(sequence)
            for body, workers, concurrency in sequence:
                seed = rng.randrange(1, 1000000000)
                order = ["forge", "rust"] if orders[(body, workers, concurrency)][pair] else ["rust", "forge"]
                for position, name in enumerate(order):
                    for kind in ["prewarm", "measurement"]:
                        prefix = raw / f"p{pair:03d}-b{body}-w{workers}-c{concurrency}-{position}-{name}-{kind}"
                        row = run_trial(servers[name], load, workers, concurrency, args.requests, seed,
                            body, cpus[:workers], client_cpu, prefix, args.connect_timeout_ms,
                            args.source_address_count, args.io_timeout_ms)
                        report["warmups" if kind == "prewarm" else "measurements"].append(
                            {"pair": pair, "order": position, "language": name, **row})
                        save(output, report)
        for body, workers, concurrency in configurations:
            samples = [row for row in report["measurements"] if
                (row["body_bytes"], row["workers"], row["concurrency"]) == (body, workers, concurrency)]
            ratios = []
            for pair in range(args.pairs):
                paired = {row["language"]: row for row in samples if row["pair"] == pair}
                ratios.append(paired["rust"]["elapsed_ns"] / paired["forge"]["elapsed_ns"])
            interval = confidence(ratios, args.random_seed + workers + body + concurrency)
            peaks = {}
            for name in ["forge", "rust"]:
                group = [row for row in samples if row["language"] == name]
                peaks[name] = {}
                for label, field in [("inflight", "observed_peak_inflight_requests"),
                                     ("connected", "observed_peak_connected_client_states"),
                                     ("pending", "observed_peak_pending_connects")]:
                    peaks[name][label + "_min"] = min(row[field] for row in group)
                    peaks[name][label + "_max"] = max(row[field] for row in group)
            report["summary"].append({"body_bytes": body, "workers": workers, "concurrency": concurrency,
                "observed_peaks": peaks,
                "forge_median_rps": statistics.median(row["requests_per_second"] for row in samples if row["language"] == "forge"),
                "rust_median_rps": statistics.median(row["requests_per_second"] for row in samples if row["language"] == "rust"),
                "paired_ratios": ratios, "paired_ratio_median": statistics.median(ratios), "ci95": interval,
                "target_status": "supported for this configuration" if interval[0] >= 1.10 else "below target" if interval[1] < 1.10 else "inconclusive"})
        report["status"] = "completed"
        output.with_suffix(".md").write_text(markdown(report, output))
    except BaseException as error:
        report.update(status="failed_no_claim", error=repr(error))
        raise
    finally:
        report["attempt_records"] = {str(path.relative_to(raw)): json.loads(path.read_text())
            for path in sorted(raw.glob("*.json"))}
        report["finished_at_utc"] = v2.stamp()
        report["environment"]["load_average_end"] = os.getloadavg()
        save(output, report)


if __name__ == "__main__":
    main()
