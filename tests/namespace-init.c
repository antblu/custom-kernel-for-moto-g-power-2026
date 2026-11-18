/* Freestanding AArch64 init for an isolated namespace smoke test. */
#include <asm/unistd.h>
#include <linux/reboot.h>
#include <linux/sched.h>

static long syscall5(long nr, long a, long b, long c, long d, long e)
{
    register long x8 asm("x8") = nr;
    register long x0 asm("x0") = a;
    register long x1 asm("x1") = b;
    register long x2 asm("x2") = c;
    register long x3 asm("x3") = d;
    register long x4 asm("x4") = e;

    asm volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4) : "memory");
    return x0;
}

#define SAY(text) syscall5(__NR_write, 1, (long)(text), sizeof(text) - 1, 0, 0)

void _start(void)
{
    const long flags = CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC |
                       CLONE_NEWUSER | CLONE_NEWPID | CLONE_NEWNET | 17; /* SIGCHLD */
    long child = syscall5(__NR_clone, flags, 0, 0, 0, 0);
    int status = -1;

    if (child == 0) {
        int passed = syscall5(__NR_getpid, 0, 0, 0, 0, 0) == 1 &&
                     syscall5(__NR_unshare, CLONE_NEWTIME, 0, 0, 0, 0) == 0;
        syscall5(__NR_exit, !passed, 0, 0, 0, 0);
        __builtin_unreachable();
    }
    if (child > 0 && syscall5(__NR_wait4, child, (long)&status, 0, 0, 0) == child &&
        status == 0)
        SAY("NAMESPACE_SMOKE_PASS\n");
    else
        SAY("NAMESPACE_SMOKE_FAIL\n");

    syscall5(__NR_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
             LINUX_REBOOT_CMD_POWER_OFF, 0, 0);
    syscall5(__NR_exit, 1, 0, 0, 0, 0);
    __builtin_unreachable();
}
