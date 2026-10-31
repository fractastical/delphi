"""The website's engineering and belief workers cap their own memory and CPU, as the simulation worker already did."""
import json
import subprocess
import sys

from frontier import worker_limits

ROOT = worker_limits.__file__.rsplit("/frontier/", 1)[0]
ALLOCATE = ("import sys; from frontier.worker_limits import cap_worker; cap_worker(address_space=512*1024**2)\n"
            "try:\n    b = bytearray(int(sys.argv[1]))\nexcept MemoryError:\n    print('refused')\nelse:\n    print('allocated')\n")


def run_alloc(size):
    return subprocess.run([sys.executable, "-c", ALLOCATE, str(size)], capture_output=True, text=True, cwd=ROOT, timeout=30).stdout.strip()


def test_cap_refuses_an_allocation_past_the_cap_and_allows_one_inside_it():
    assert run_alloc(1024**3) == "refused"
    assert run_alloc(32 * 1024**2) == "allocated"          # positive control: the cap does not break ordinary work


def test_cap_never_raises_a_lower_inherited_limit():
    code = ("import resource; from frontier.worker_limits import cap_worker\n"
            "resource.setrlimit(resource.RLIMIT_CPU, (3, 3)); cap_worker(cpu_s=8)\n"
            "print(resource.getrlimit(resource.RLIMIT_CPU)[0])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=30).stdout.strip()
    assert out == "3"


def test_workers_still_answer_under_the_cap():
    done = subprocess.run([sys.executable, "-m", "frontier.engineering_api", "--worker"], input=json.dumps({"mass": "0.5", "area": "0.05"}),
                          capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert done.returncode == 0 and json.loads(done.stdout)["schema"] == "frontier.engineering.solve/1"
