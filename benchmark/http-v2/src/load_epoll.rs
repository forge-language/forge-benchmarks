//! Separately versioned, bounded Linux epoll HTTP load observer.
//!
//! One reactor thread owns at most `concurrency` sockets. Requests use a new
//! connection each time and are counted successful only after an exact byte
//! comparison and a distinct EOF check. This is not timing-compatible with
//! `load.rs`: socket progress is driven by epoll instead of one blocking thread
//! per lane.
use std::fs::File;
use std::io::{self, BufRead, Write};
use std::mem::{size_of, zeroed};
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd, RawFd};
use std::time::{Duration, Instant};

const IO_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_PENDING_CONNECTS: usize = 256;
const TIMEOUT_SCAN_INTERVAL: Duration = Duration::from_millis(25);
const HEADER: &str = "id\tlatency_ns\tconnect_ns\tsetup_ns\twrite_ns\tread_ns\teof_ns\tresponse_bytes\tfailed_stage\terror\n";
const ERROR_EVENTS: u32 = (libc::EPOLLRDHUP | libc::EPOLLERR | libc::EPOLLHUP) as u32;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Phase {
    Connect,
    Setup,
    Write,
    Read,
    Eof,
    Response,
}

impl Phase {
    fn label(self) -> &'static str {
        match self {
            Self::Connect => "connect",
            Self::Setup => "setup",
            Self::Write => "write",
            Self::Read => "read",
            Self::Eof => "eof",
            Self::Response => "response",
        }
    }
}

struct Request {
    id: usize,
    bytes: Vec<u8>,
    started: Instant,
    phase_started: Instant,
    phase: Phase,
    connect_ns: u128,
    setup_ns: u128,
    write_ns: u128,
    read_ns: u128,
    eof_ns: u128,
    written: usize,
    received: Vec<u8>,
    fd: OwnedFd,
}

struct Completed {
    id: usize,
    latency_ns: u128,
    connect_ns: u128,
    setup_ns: u128,
    write_ns: u128,
    read_ns: u128,
    eof_ns: u128,
    bytes: usize,
    failed_stage: &'static str,
    error: String,
}

#[derive(Default)]
struct Peaks {
    active: usize,
    connected: usize,
    pending: usize,
}

impl Peaks {
    fn observe(&mut self, connected: usize, pending: usize) {
        self.active = self.active.max(connected + pending);
        self.connected = self.connected.max(connected);
        self.pending = self.pending.max(pending);
    }
}

fn socket_connect(port: u16, source_address: u8) -> io::Result<(OwnedFd, bool)> {
    // SAFETY: socket returns either an owned descriptor or -1.
    let raw = unsafe {
        libc::socket(
            libc::AF_INET,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    let fd = unsafe { OwnedFd::from_raw_fd(raw) };
    let source = libc::sockaddr_in {
        sin_family: libc::AF_INET as libc::sa_family_t,
        sin_port: 0,
        sin_addr: libc::in_addr {
            s_addr: u32::from_ne_bytes([127, 0, 0, source_address]),
        },
        sin_zero: [0; 8],
    };
    // SAFETY: source is a live IPv4 sockaddr with an ephemeral local port.
    if unsafe {
        libc::bind(
            raw,
            (&source as *const libc::sockaddr_in).cast(),
            size_of::<libc::sockaddr_in>() as libc::socklen_t,
        )
    } < 0
    {
        return Err(io::Error::last_os_error());
    }
    let address = libc::sockaddr_in {
        sin_family: libc::AF_INET as libc::sa_family_t,
        sin_port: port.to_be(),
        sin_addr: libc::in_addr {
            s_addr: u32::from_ne_bytes([127, 0, 0, 1]),
        },
        sin_zero: [0; 8],
    };
    // SAFETY: address has the correct IPv4 sockaddr size and remains live.
    let result = unsafe {
        libc::connect(
            raw,
            (&address as *const libc::sockaddr_in).cast(),
            size_of::<libc::sockaddr_in>() as libc::socklen_t,
        )
    };
    if result == 0 {
        return Ok((fd, true));
    }
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(libc::EINPROGRESS) {
        Ok((fd, false))
    } else {
        Err(error)
    }
}

fn set_nodelay(fd: RawFd) -> io::Result<()> {
    let enabled: libc::c_int = 1;
    // SAFETY: pointer and length describe the live integer option value.
    let result = unsafe {
        libc::setsockopt(
            fd,
            libc::IPPROTO_TCP,
            libc::TCP_NODELAY,
            (&enabled as *const libc::c_int).cast(),
            size_of::<libc::c_int>() as libc::socklen_t,
        )
    };
    if result == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

fn epoll_ctl(epoll: RawFd, op: libc::c_int, fd: RawFd, token: u64, phase: Phase) -> io::Result<()> {
    let io_events = match phase {
        Phase::Connect | Phase::Write => libc::EPOLLOUT as u32,
        Phase::Read | Phase::Eof => libc::EPOLLIN as u32,
        Phase::Setup | Phase::Response => 0,
    };
    let mut event = libc::epoll_event {
        events: io_events | ERROR_EVENTS,
        u64: token,
    };
    // SAFETY: event points to a writable event for the duration of the call.
    let result = unsafe { libc::epoll_ctl(epoll, op, fd, &mut event) };
    if result == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

fn phase_timeout(phase: Phase, connect_timeout: Duration, io_timeout: Duration) -> Duration {
    if phase == Phase::Connect {
        connect_timeout
    } else {
        io_timeout
    }
}

fn elapsed_ns(start: Instant) -> u128 {
    start.elapsed().as_nanos()
}

fn finish(req: Request, error: Option<(Phase, io::Error)>) -> Completed {
    let mut connect_ns = req.connect_ns;
    let mut setup_ns = req.setup_ns;
    let mut write_ns = req.write_ns;
    let mut read_ns = req.read_ns;
    let mut eof_ns = req.eof_ns;
    let pending_ns = req.phase_started.elapsed().as_nanos();
    match req.phase {
        Phase::Connect if connect_ns == 0 => connect_ns = pending_ns,
        Phase::Setup if setup_ns == 0 => setup_ns = pending_ns,
        Phase::Write if write_ns == 0 => write_ns = pending_ns,
        Phase::Read if read_ns == 0 => read_ns = pending_ns,
        Phase::Eof if eof_ns == 0 => eof_ns = pending_ns,
        _ => {}
    }
    let failed_stage = error.as_ref().map(|(phase, _)| phase.label()).unwrap_or("");
    let error_text = error
        .map(|(_, error)| format!("{error:?}"))
        .unwrap_or_default();
    Completed {
        id: req.id,
        latency_ns: elapsed_ns(req.started),
        connect_ns,
        setup_ns,
        write_ns,
        read_ns,
        eof_ns,
        bytes: req.received.len(),
        failed_stage,
        error: error_text,
    }
}

fn begin_request(
    id: usize,
    seed: usize,
    port: u16,
    epoll: RawFd,
    token: u64,
    response_len: usize,
    source_address_count: u8,
) -> Result<Request, Completed> {
    let padding = "x".repeat(32 + (seed + id) % 512);
    let bytes = format!("GET /bench/{seed}/{id} HTTP/1.1\r\nHost: localhost\r\nX-Input: {padding}\r\nConnection: close\r\n\r\n").into_bytes();
    let started = Instant::now();
    let source_address = (id % usize::from(source_address_count)) as u8 + 1;
    let (fd, connected) = match socket_connect(port, source_address) {
        Ok(result) => result,
        Err(error) => {
            let elapsed = elapsed_ns(started);
            return Err(Completed {
                id,
                latency_ns: elapsed,
                connect_ns: elapsed,
                setup_ns: 0,
                write_ns: 0,
                read_ns: 0,
                eof_ns: 0,
                bytes: 0,
                failed_stage: "connect",
                error: format!("{error:?}"),
            });
        }
    };
    if let Err(error) = epoll_ctl(
        epoll,
        libc::EPOLL_CTL_ADD,
        fd.as_raw_fd(),
        token,
        Phase::Connect,
    ) {
        let elapsed = elapsed_ns(started);
        return Err(Completed {
            id,
            latency_ns: elapsed,
            connect_ns: elapsed,
            setup_ns: 0,
            write_ns: 0,
            read_ns: 0,
            eof_ns: 0,
            bytes: 0,
            failed_stage: "connect",
            error: format!("{error:?}"),
        });
    }
    let mut req = Request {
        id,
        bytes,
        started,
        phase_started: started,
        phase: Phase::Connect,
        connect_ns: 0,
        setup_ns: 0,
        write_ns: 0,
        read_ns: 0,
        eof_ns: 0,
        written: 0,
        received: Vec::with_capacity(response_len + 1),
        fd,
    };
    if connected {
        if let Err(error) = enter_setup(&mut req) {
            let phase = req.phase;
            return Err(finish(req, Some((phase, error))));
        }
        if let Err(error) = epoll_ctl(
            epoll,
            libc::EPOLL_CTL_MOD,
            req.fd.as_raw_fd(),
            token,
            req.phase,
        ) {
            let phase = req.phase;
            return Err(finish(req, Some((phase, error))));
        }
    }
    Ok(req)
}

fn transition(req: &mut Request, phase: Phase) {
    let duration = req.phase_started.elapsed().as_nanos();
    match req.phase {
        Phase::Connect => req.connect_ns = duration,
        Phase::Setup => req.setup_ns = duration,
        Phase::Write => req.write_ns = duration,
        Phase::Read => req.read_ns = duration,
        Phase::Eof => req.eof_ns = duration,
        Phase::Response => {}
    }
    req.phase = phase;
    req.phase_started = Instant::now();
}

fn enter_setup(req: &mut Request) -> io::Result<()> {
    transition(req, Phase::Setup);
    let result = set_nodelay(req.fd.as_raw_fd());
    // Setup interval is recorded even on failure.
    if result.is_ok() {
        transition(req, Phase::Write);
    }
    result
}

fn write_ready(req: &mut Request) -> io::Result<bool> {
    loop {
        let remaining = &req.bytes[req.written..];
        // SAFETY: the slice is readable for its length; send doesn't retain it.
        let count = unsafe {
            libc::send(
                req.fd.as_raw_fd(),
                remaining.as_ptr().cast(),
                remaining.len(),
                libc::MSG_NOSIGNAL,
            )
        };
        if count > 0 {
            req.written += count as usize;
        } else if count == 0 {
            return Err(io::ErrorKind::WriteZero.into());
        } else {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            if error.kind() == io::ErrorKind::WouldBlock {
                return Ok(false);
            }
            return Err(error);
        }
        if req.written == req.bytes.len() {
            transition(req, Phase::Read);
            return Ok(true);
        }
    }
}

fn read_ready(req: &mut Request, response: &[u8]) -> io::Result<bool> {
    let mut scratch = [0u8; 8192];
    loop {
        let remaining = match req.phase {
            Phase::Read => response.len().saturating_sub(req.received.len()),
            Phase::Eof => 1,
            _ => return Ok(false),
        };
        let capacity = remaining.min(scratch.len()).max(1);
        // SAFETY: scratch is writable for `capacity` bytes and recv doesn't retain it.
        let count =
            unsafe { libc::recv(req.fd.as_raw_fd(), scratch.as_mut_ptr().cast(), capacity, 0) };
        if count == 0 {
            if req.phase == Phase::Read {
                return Err(io::ErrorKind::UnexpectedEof.into());
            }
            transition(req, Phase::Response);
            return Ok(true);
        }
        if count < 0 {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            if error.kind() == io::ErrorKind::WouldBlock {
                return Ok(false);
            }
            return Err(error);
        }
        let count = count as usize;
        if req.phase == Phase::Read {
            let start = req.received.len();
            if scratch[..count] != response[start..start + count] {
                req.received.extend_from_slice(&scratch[..count]);
                return Err(io::ErrorKind::InvalidData.into());
            }
            req.received.extend_from_slice(&scratch[..count]);
            if req.received.len() == response.len() {
                transition(req, Phase::Eof);
            }
        } else {
            req.received.extend_from_slice(&scratch[..count]);
            return Err(io::ErrorKind::InvalidData.into());
        }
    }
}

fn main() -> io::Result<()> {
    #[cfg(not(target_os = "linux"))]
    compile_error!("http-load-epoll requires Linux epoll");
    let args: Vec<_> = std::env::args().collect();
    if !(8..=10).contains(&args.len()) {
        eprintln!(
            "usage: http-load-epoll PORT CONCURRENCY REQUESTS SEED RESPONSE_FILE ROWS_FILE CONNECT_TIMEOUT_MS [IO_TIMEOUT_MS [SOURCE_ADDRESS_COUNT]]"
        );
        std::process::exit(2);
    }
    let port: u16 = args[1].parse().expect("port");
    let concurrency: usize = args[2].parse().expect("concurrency");
    let requests: usize = args[3].parse().expect("requests");
    let seed: usize = args[4].parse().expect("seed");
    let response = std::fs::read(&args[5])?;
    let connect_timeout = Duration::from_millis(args[7].parse().expect("connect timeout ms"));
    let io_timeout = if args.len() >= 9 {
        Duration::from_millis(args[8].parse().expect("I/O timeout ms"))
    } else {
        IO_TIMEOUT
    };
    let source_address_count = if args.len() == 10 {
        args[9].parse::<usize>().expect("source address count")
    } else {
        1
    };
    if concurrency == 0
        || requests < concurrency
        || connect_timeout.is_zero()
        || io_timeout.is_zero()
        || source_address_count == 0
        || source_address_count > 254
        || response.is_empty()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid concurrency, request count, timeout or empty response",
        ));
    }
    // The default policy mirrors V2's ten-second write/read timeout. A custom
    // timeout is provided only for deterministic bounded correctness tests.
    let mut rows = File::options()
        .write(true)
        .create_new(true)
        .open(&args[6])?;
    rows.write_all(HEADER.as_bytes())?;
    println!("ready");
    io::stdout().flush()?;
    let mut signal = String::new();
    io::stdin().lock().read_line(&mut signal)?;
    if signal.trim() != "go" {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "expected go"));
    }

    let raw_epoll = unsafe { libc::epoll_create1(libc::EPOLL_CLOEXEC) };
    if raw_epoll < 0 {
        return Err(io::Error::last_os_error());
    }
    let epoll = unsafe { OwnedFd::from_raw_fd(raw_epoll) };
    let mut active: std::collections::HashMap<u64, Request> =
        std::collections::HashMap::with_capacity(concurrency);
    let mut pending_connects = 0usize;
    let mut connected_active = 0usize;
    let mut peaks = Peaks::default();
    let mut next_id = 0usize;
    let mut next_token = 1u64;
    let mut attempts = 0usize;
    let mut errors = 0usize;
    let mut stopped = false;
    let started = Instant::now();
    let mut next_timeout_scan = started + TIMEOUT_SCAN_INTERVAL;
    let mut events: Vec<libc::epoll_event> = (0..concurrency.min(256).max(1))
        .map(|_| unsafe { zeroed() })
        .collect();

    while next_id < requests
        && active.len() < concurrency
        && pending_connects < MAX_PENDING_CONNECTS
    {
        let id = next_id;
        next_id += 1;
        let token = next_token;
        next_token += 1;
        match begin_request(
            id,
            seed,
            port,
            epoll.as_raw_fd(),
            token,
            response.len(),
            source_address_count as u8,
        ) {
            Ok(req) => {
                if req.phase == Phase::Connect {
                    pending_connects += 1;
                } else {
                    connected_active += 1;
                }
                peaks.observe(connected_active, pending_connects);
                active.insert(token, req);
            }
            Err(row) => {
                errors += 1;
                stopped = true;
                write_row(&mut rows, &row)?;
                attempts += 1;
                break;
            }
        }
    }

    while !active.is_empty() {
        let now = Instant::now();
        let wait_ms = if next_timeout_scan <= now {
            0
        } else {
            ((next_timeout_scan - now).as_millis().max(1)).min(i32::MAX as u128) as i32
        };
        let event_count = unsafe {
            libc::epoll_wait(
                epoll.as_raw_fd(),
                events.as_mut_ptr(),
                events.len() as i32,
                wait_ms,
            )
        };
        if event_count < 0 {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(error);
        }
        let mut done = Vec::new();
        for event in events.iter().take(event_count as usize) {
            let token = event.u64;
            let Some(req) = active.get_mut(&token) else {
                continue;
            };
            let flags = event.events;
            let now = Instant::now();
            if now >= req.phase_started + phase_timeout(req.phase, connect_timeout, io_timeout) {
                done.push((
                    token,
                    Some((
                        req.phase,
                        io::Error::new(io::ErrorKind::TimedOut, "stage deadline exceeded"),
                    )),
                ));
                continue;
            }
            let result: io::Result<bool> = (|| {
                if req.phase == Phase::Connect {
                    let mut socket_error: libc::c_int = 0;
                    let mut len = size_of::<libc::c_int>() as libc::socklen_t;
                    // SAFETY: getsockopt fills the initialized value and len.
                    let status = unsafe {
                        libc::getsockopt(
                            req.fd.as_raw_fd(),
                            libc::SOL_SOCKET,
                            libc::SO_ERROR,
                            (&mut socket_error as *mut libc::c_int).cast(),
                            &mut len,
                        )
                    };
                    if status < 0 {
                        return Err(io::Error::last_os_error());
                    }
                    if socket_error != 0 {
                        return Err(io::Error::from_raw_os_error(socket_error));
                    }
                    pending_connects -= 1;
                    connected_active += 1;
                    peaks.observe(connected_active, pending_connects);
                    enter_setup(req)?;
                }
                let socket_failure =
                    flags & ((libc::EPOLLERR | libc::EPOLLHUP | libc::EPOLLRDHUP) as u32) != 0;
                if req.phase == Phase::Write && socket_failure {
                    let mut socket_error: libc::c_int = 0;
                    let mut len = size_of::<libc::c_int>() as libc::socklen_t;
                    // SAFETY: getsockopt fills the initialized value and len.
                    let status = unsafe {
                        libc::getsockopt(
                            req.fd.as_raw_fd(),
                            libc::SOL_SOCKET,
                            libc::SO_ERROR,
                            (&mut socket_error as *mut libc::c_int).cast(),
                            &mut len,
                        )
                    };
                    if status < 0 {
                        return Err(io::Error::last_os_error());
                    }
                    if socket_error != 0 {
                        return Err(io::Error::from_raw_os_error(socket_error));
                    }
                }
                if req.phase == Phase::Write
                    && (flags & (libc::EPOLLOUT as u32) != 0 || socket_failure)
                {
                    write_ready(req)?;
                }
                if matches!(req.phase, Phase::Read | Phase::Eof)
                    && flags
                        & ((libc::EPOLLIN | libc::EPOLLRDHUP | libc::EPOLLHUP | libc::EPOLLERR)
                            as u32)
                        != 0
                {
                    read_ready(req, &response)?;
                    if req.phase == Phase::Eof
                        && flags & ((libc::EPOLLHUP | libc::EPOLLRDHUP) as u32) != 0
                    {
                        // A subsequent recv observes orderly EOF (or extra bytes).
                        read_ready(req, &response)?;
                    }
                    if req.phase == Phase::Response
                        && req.received[..response.len()] != response[..]
                    {
                        return Err(io::ErrorKind::InvalidData.into());
                    }
                }
                if req.phase != Phase::Response {
                    epoll_ctl(
                        epoll.as_raw_fd(),
                        libc::EPOLL_CTL_MOD,
                        req.fd.as_raw_fd(),
                        token,
                        req.phase,
                    )?;
                }
                Ok(req.phase == Phase::Response)
            })();
            match result {
                Ok(true) => done.push((token, None)),
                Ok(false) => {}
                Err(error) => done.push((token, Some((req.phase, error)))),
            }
        }
        let now = Instant::now();
        if now >= next_timeout_scan {
            for (token, req) in active.iter() {
                if now >= req.phase_started + phase_timeout(req.phase, connect_timeout, io_timeout)
                {
                    done.push((
                        *token,
                        Some((
                            req.phase,
                            io::Error::new(io::ErrorKind::TimedOut, "stage deadline exceeded"),
                        )),
                    ));
                }
            }
            next_timeout_scan = now + TIMEOUT_SCAN_INTERVAL;
        }
        done.sort_by_key(|(token, _)| *token);
        done.dedup_by_key(|(token, _)| *token);
        // Resolve the entire observed batch before refilling any slot. A
        // success with a lower token must not launch work if this same batch
        // already contains a failed request.
        if done.iter().any(|(_, error)| error.is_some()) {
            stopped = true;
        }
        for (token, error) in done {
            let Some(req) = active.remove(&token) else {
                continue;
            };
            if req.phase == Phase::Connect {
                pending_connects -= 1;
            } else {
                connected_active -= 1;
            }
            let _ = unsafe {
                libc::epoll_ctl(
                    epoll.as_raw_fd(),
                    libc::EPOLL_CTL_DEL,
                    req.fd.as_raw_fd(),
                    std::ptr::null_mut(),
                )
            };
            let failed = error.is_some();
            let row = finish(req, error);
            write_row(&mut rows, &row)?;
            attempts += 1;
            if failed {
                errors += 1;
                stopped = true;
            }
        }
        // Keep connect creation bounded while the reactor also services
        // already-connected sockets. Filling every lane before polling can
        // deadlock a server whose accept workers wait for request bytes.
        while !stopped
            && next_id < requests
            && active.len() < concurrency
            && pending_connects < MAX_PENDING_CONNECTS
        {
            let id = next_id;
            next_id += 1;
            let token = next_token;
            next_token += 1;
            match begin_request(
                id,
                seed,
                port,
                epoll.as_raw_fd(),
                token,
                response.len(),
                source_address_count as u8,
            ) {
                Ok(req) => {
                    if req.phase == Phase::Connect {
                        pending_connects += 1;
                    } else {
                        connected_active += 1;
                    }
                    peaks.observe(connected_active, pending_connects);
                    active.insert(token, req);
                }
                Err(row) => {
                    errors += 1;
                    stopped = true;
                    write_row(&mut rows, &row)?;
                    attempts += 1;
                }
            }
        }
    }
    debug_assert_eq!(connected_active, 0);
    debug_assert_eq!(pending_connects, 0);
    println!(
        "{}\t{}\t{}\t{}\t{}\t{}",
        started.elapsed().as_nanos(),
        attempts,
        errors,
        peaks.active,
        peaks.connected,
        peaks.pending
    );
    Ok(())
}

fn write_row(file: &mut File, row: &Completed) -> io::Result<()> {
    writeln!(
        file,
        "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
        row.id,
        row.latency_ns,
        row.connect_ns,
        row.setup_ns,
        row.write_ns,
        row.read_ns,
        row.eof_ns,
        row.bytes,
        row.failed_stage,
        row.error
    )
}
