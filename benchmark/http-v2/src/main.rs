//! Prepared, header-consuming HTTP backend, not a general HTTP parser.
//! Mirrors Forge's public prepared-response API with owned Rust resources.
use socket2::{Domain, Protocol, Socket, Type};
use std::io::{self, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::sync::Arc;
use std::time::Duration;

unsafe extern "C" {
    fn bench_config();
    fn bench_pin_worker(index: i32);
}

fn listener(port: u16, reuseport: bool) -> io::Result<TcpListener> {
    let socket = Socket::new(Domain::IPV4, Type::STREAM, Some(Protocol::TCP))?;
    socket.set_reuse_address(true)?;
    if reuseport {
        socket.set_reuse_port(true)?;
    }
    socket.set_recv_buffer_size(65536)?;
    socket.set_send_buffer_size(65536)?;
    socket.bind(&SocketAddr::from(([0, 0, 0, 0], port)).into())?;
    socket.listen(8192)?;
    socket.set_nonblocking(true)?;
    Ok(socket.into())
}

fn consume_and_respond(mut stream: TcpStream, response: &[u8]) -> io::Result<()> {
    // Forge accepts NONBLOCK+CLOEXEC, then changes to blocking per request.
    stream.set_nonblocking(false)?;
    stream.set_read_timeout(Some(Duration::from_secs(5)))?;
    stream.set_write_timeout(Some(Duration::from_secs(5)))?;
    let mut buffer = [0u8; 8192];
    let mut length = 0;
    while length < buffer.len() - 1 {
        let count = match stream.read(&mut buffer[length..8191]) {
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            value => value?,
        };
        if count == 0 {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }
        length += count;
        if buffer[..length]
            .windows(4)
            .any(|value| value == b"\r\n\r\n")
        {
            // Standard-library write_all handles short writes and EINTR;
            // Linux Rust sockets suppress SIGPIPE. Forge retries send too.
            stream.write_all(response)?;
            return Ok(());
        }
    }
    Err(io::ErrorKind::InvalidData.into())
}

fn serve(listener: TcpListener, response: Arc<Vec<u8>>) -> io::Result<()> {
    let raw = unsafe { libc::epoll_create1(libc::EPOLL_CLOEXEC) };
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    let epoll = unsafe { OwnedFd::from_raw_fd(raw) };
    let mut event = libc::epoll_event {
        events: libc::EPOLLIN as u32,
        u64: listener.as_raw_fd() as u64,
    };
    if unsafe {
        libc::epoll_ctl(
            epoll.as_raw_fd(),
            libc::EPOLL_CTL_ADD,
            listener.as_raw_fd(),
            &mut event,
        )
    } < 0
    {
        return Err(io::Error::last_os_error());
    }
    let mut events = [libc::epoll_event { events: 0, u64: 0 }; 128];
    loop {
        let count = unsafe {
            libc::epoll_wait(
                epoll.as_raw_fd(),
                events.as_mut_ptr(),
                events.len() as i32,
                -1,
            )
        };
        if count < 0 {
            if io::Error::last_os_error().kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(io::Error::last_os_error());
        }
        for _ in 0..count {
            for _ in 0..256 {
                // Same accept4 flags as Forge; Owned TcpStream closes exactly
                // once on success/error. No shared C HTTP implementation.
                let raw = unsafe {
                    libc::accept4(
                        listener.as_raw_fd(),
                        std::ptr::null_mut(),
                        std::ptr::null_mut(),
                        libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
                    )
                };
                if raw < 0 {
                    let error = io::Error::last_os_error();
                    if matches!(error.raw_os_error(), Some(libc::EMFILE | libc::ENFILE)) {
                        std::thread::sleep(Duration::from_micros(1000));
                    }
                    break;
                }
                let stream = unsafe { TcpStream::from_raw_fd(raw) };
                let _ = consume_and_respond(stream, &response);
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 4);
    let port = args[1].parse::<u16>().unwrap();
    let workers = args[2].parse::<usize>().unwrap();
    assert!((1..=64).contains(&workers));
    unsafe {
        bench_config();
    }
    let body = args[3].as_bytes();
    let mut response = format!(
        "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    )
    .into_bytes();
    response.extend_from_slice(body);
    let response = Arc::new(response);
    if workers == 1 {
        serve(listener(port, false).unwrap(), response).unwrap();
    } else {
        // Forge's multi-worker path closes its initial socket before rebinding
        // a separate SO_REUSEPORT socket per detached OS worker.
        let listeners: Vec<_> = (0..workers)
            .map(|_| listener(port, true).unwrap())
            .collect();
        for (index, listener) in listeners.into_iter().enumerate() {
            let response = Arc::clone(&response);
            std::thread::spawn(move || {
                unsafe {
                    bench_pin_worker(index as i32);
                }
                serve(listener, response).unwrap();
            });
        }
        loop {
            std::thread::park();
        }
    }
}
