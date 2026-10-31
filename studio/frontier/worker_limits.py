"""Per-child resource caps for the website's numerical workers.

The service cgroup (MemoryMax/TasksMax) bounds the whole tree, but a cgroup OOM kill picks a victim inside the *web service* and so can
take the website down; a cap inside the child makes the child fail first. Apply it first thing in a ``--worker`` entry point, before
reading the request.
"""
import resource
from threading import BoundedSemaphore

# Sizing, measured 2026-10-31 with the production worker environment (single-threaded BLAS) by lowering RLIMIT_AS until a valid request
# failed: bioelectric 158 MiB, mechanobio 268 MiB, engineering 127 MiB, beliefs 79 MiB (formalize caps itself at 384 MiB). RLIMIT_AS bounds
# virtual size, which is >= resident size, so a worker can never hold more than its cap in the 1 GiB service cgroup. 384 MiB leaves the
# heaviest worker 1.4x headroom. Two workers at once, across ALL four adapters, is 768 MiB, leaving the web process the rest of 1 GiB;
# the per-adapter slots alone would have allowed eight.
DEFAULT_ADDRESS_SPACE = 384 * 1024**2
DEFAULT_CPU_S = 8
MAX_CONCURRENT_WORKERS = 2
_WORKERS = BoundedSemaphore(MAX_CONCURRENT_WORKERS)


class Slots:
    """A per-adapter slot count that also takes one process-wide worker slot. Same acquire(blocking=False)/release as a semaphore."""

    def __init__(self, n: int = 2):
        self._own = BoundedSemaphore(n)

    def acquire(self, blocking: bool = False) -> bool:
        if not self._own.acquire(blocking=blocking):
            return False
        if not _WORKERS.acquire(blocking=blocking):
            self._own.release()
            return False
        return True

    def release(self) -> None:
        _WORKERS.release()
        self._own.release()


def cap_worker(address_space: int = DEFAULT_ADDRESS_SPACE, cpu_s: int = DEFAULT_CPU_S) -> None:
    """Lower RLIMIT_AS and RLIMIT_CPU; never raise a limit the caller already runs under."""
    for key, cap in ((resource.RLIMIT_AS, address_space), (resource.RLIMIT_CPU, cpu_s)):
        soft, hard = resource.getrlimit(key)
        value = cap if hard == resource.RLIM_INFINITY else min(cap, hard)
        if soft != resource.RLIM_INFINITY:
            value = min(value, soft)
        resource.setrlimit(key, (value, value))
