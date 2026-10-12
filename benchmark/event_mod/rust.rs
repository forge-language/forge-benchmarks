use std::env;
use std::os::raw::{c_int, c_void};

const EPOLL_CTL_ADD: c_int = 1;
const EPOLL_CTL_MOD: c_int = 3;
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
    let operations: u64 = env::args().nth(1).expect("operations").parse().expect("integer");
    assert!((1..=100_000_000).contains(&operations));
    unsafe {
        let fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
        assert!(fd >= 0, "eventfd failed");
        let epfd = epoll_create1(0);
        assert!(epfd >= 0, "epoll_create1 failed");
        let mut entry = EpollEvent { events: EPOLLIN, data: 0 };
        assert_eq!(epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &mut entry), 0, "epoll add failed");

        let start = bench_clock_ns();
        for i in 1..=operations {
            entry.data = i;
            assert_eq!(epoll_ctl(epfd, EPOLL_CTL_MOD, fd, &mut entry), 0, "epoll mod failed");
        }
        let elapsed = bench_clock_ns() - start;

        let signal: u64 = 1;
        assert_eq!(write(fd, (&signal as *const u64).cast(), 8), 8, "eventfd write failed");
        let mut ready = [EpollEvent { events: 0, data: 0 }];
        assert_eq!(epoll_wait(epfd, ready.as_mut_ptr(), 1, 1000), 1, "epoll wait failed");
        let seen = std::ptr::addr_of!(ready[0].data).read_unaligned();
        assert_eq!(seen, operations, "epoll userdata mismatch");
        println!("{elapsed} {operations}");
        assert_eq!(close(epfd), 0);
        assert_eq!(close(fd), 0);
    }
}
