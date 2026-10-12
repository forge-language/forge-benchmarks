use std::{env, os::raw::{c_int, c_void}};

const EPOLL_CTL_ADD: c_int = 1;
const EPOLLIN: u32 = 0x001;
const EFD_NONBLOCK: c_int = 0x800;
const EFD_CLOEXEC: c_int = 0x80000;

#[repr(C, packed)]
#[derive(Clone, Copy)]
struct EpollEvent {
    events: u32,
    data: u64,
}

#[link(name = "c")]
unsafe extern "C" {
    fn epoll_create1(flags: c_int) -> c_int;
    fn epoll_ctl(epfd: c_int, op: c_int, fd: c_int, event: *mut EpollEvent) -> c_int;
    fn epoll_wait(epfd: c_int, events: *mut EpollEvent, maxevents: c_int, timeout: c_int) -> c_int;
    fn eventfd(initval: u32, flags: c_int) -> c_int;
    fn write(fd: c_int, buf: *const c_void, count: usize) -> isize;
    fn close(fd: c_int) -> c_int;
    fn bench_clock_ns() -> i64;
}

fn main() {
    let mut args = env::args().skip(1);
    let count: usize = args.next().expect("event count").parse().expect("integer");
    let capacity: usize = args.next().expect("batch capacity").parse().expect("integer");
    assert!((1..=65_536).contains(&count));
    assert!((1..=65_536).contains(&capacity));
    unsafe {
        let epfd = epoll_create1(0);
        assert!(epfd >= 0, "epoll_create1 failed");
        let mut fds = Vec::with_capacity(count);
        for i in 0..count {
            let fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
            assert!(fd >= 0, "eventfd failed");
            let mut event = EpollEvent { events: EPOLLIN, data: i as u64 };
            assert_eq!(epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &mut event), 0, "epoll add failed");
            fds.push(fd);
        }
        let signal: u64 = 1;
        for fd in &fds {
            assert_eq!(write(*fd, (&signal as *const u64).cast(), 8), 8, "eventfd write failed");
        }

        let mut seen = vec![false; count];
        let mut observed = 0usize;
        let mut events = vec![EpollEvent { events: 0, data: 0 }; capacity];
        let mut poll_calls = 0u64;
        let start = bench_clock_ns();
        while observed < count {
            let n = epoll_wait(epfd, events.as_mut_ptr(), capacity as c_int, 0);
            assert!(n > 0, "epoll_wait failed or lost readiness");
            poll_calls += 1;
            for event in events.iter().take(n as usize) {
                let index = std::ptr::addr_of!(event.data).read_unaligned() as usize;
                assert!(index < count);
                if !seen[index] {
                    seen[index] = true;
                    observed += 1;
                }
            }
        }
        let elapsed = bench_clock_ns() - start;
        println!("{elapsed} {poll_calls} {observed}");
        assert_eq!(close(epfd), 0);
        for fd in fds { assert_eq!(close(fd), 0); }
    }
}
