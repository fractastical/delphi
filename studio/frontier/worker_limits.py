"""Per-child resource caps for the website's numerical workers.

The service cgroup (MemoryMax/TasksMax) bounds the whole tree, but a cgroup OOM kill picks a victim inside the *web service* and so can
take the website down; a cap inside the child makes the child fail first. Apply it first thing in a ``--worker`` entry point, before
reading the request.
"""
import resource

DEFAULT_ADDRESS_SPACE = 2 * 1024**3
DEFAULT_CPU_S = 8


def cap_worker(address_space: int = DEFAULT_ADDRESS_SPACE, cpu_s: int = DEFAULT_CPU_S) -> None:
    """Lower RLIMIT_AS and RLIMIT_CPU; never raise a limit the caller already runs under."""
    for key, cap in ((resource.RLIMIT_AS, address_space), (resource.RLIMIT_CPU, cpu_s)):
        soft, hard = resource.getrlimit(key)
        value = cap if hard == resource.RLIM_INFINITY else min(cap, hard)
        if soft != resource.RLIM_INFINITY:
            value = min(value, soft)
        resource.setrlimit(key, (value, value))
