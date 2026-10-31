"""Bounded nvidia-smi sampling inside a job. Two labelled streams:
  ASSIGNED-DEVICE telemetry: utilization.gpu, utilization.memory, memory.used/total, power.draw, temperature.gpu for the GPU assigned to this job
     (one GPU per job; it is device-level, includes every process on that device, not attributed to a single process).
  PER-PROCESS attribution: `nvidia-smi --query-compute-apps` (pid, used_memory); inside a container this is frequently empty or shows other PID namespaces, so it
     is recorded as returned and flagged 'available' only if rows came back. Nothing about other jobs/teams is read: nvidia-smi sees only the assigned device.
Raw sample files are kept verbatim with their sha256; summary statistics are derived from them. No price is derived or implied.
Usage:  with Telemetry(outdir, max_s=3000, period_ms=1000): ...work...    -> writes telemetry_device.csv, telemetry_procs.csv, telemetry_summary.json"""
import hashlib, json, os, shutil, subprocess, threading, time

Q = "timestamp,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu"


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class Telemetry:
    def __init__(self, outdir, max_s=3000, period_ms=1000, proc_every_s=10):
        self.out, self.max_s, self.period_ms, self.proc_every = outdir, max_s, period_ms, proc_every_s
        self.dev_csv, self.proc_csv = os.path.join(outdir, "telemetry_device.csv"), os.path.join(outdir, "telemetry_procs.csv")
        self.p, self.t, self.stop_ev, self.avail = None, None, threading.Event(), shutil.which("nvidia-smi") is not None
        self.t_start = self.t_stop = None

    def _proc_loop(self):
        with open(self.proc_csv, "w") as f:
            f.write("sample_utc,timestamp,pid,process_name,used_memory_MiB\n")
            t_end = time.time() + self.max_s
            while not self.stop_ev.is_set() and time.time() < t_end:
                r = subprocess.run(["nvidia-smi", "--query-compute-apps=timestamp,pid,process_name,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True)
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                for line in r.stdout.strip().splitlines():
                    f.write(now + "," + line + "\n")
                f.flush()
                self.stop_ev.wait(self.proc_every)

    def __enter__(self):
        self.t_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.avail:
            return self
        self.f = open(self.dev_csv, "w")
        self.f.write(Q + "\n")
        self.f.flush()
        # `timeout` bounds the sampler even if this process dies
        self.p = subprocess.Popen(["timeout", str(int(self.max_s)), "nvidia-smi", f"--query-gpu={Q}", "--format=csv,noheader,nounits", f"-lms", str(self.period_ms)],
                                  stdout=self.f, stderr=subprocess.DEVNULL)
        self.t = threading.Thread(target=self._proc_loop, daemon=True)
        self.t.start()
        return self

    def __exit__(self, *a):
        self.t_stop = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.stop_ev.set()
        if self.p:
            self.p.terminate()
            try:
                self.p.wait(10)
            except Exception:
                self.p.kill()
            self.f.close()
        if self.t:
            self.t.join(15)
        summ = summarize(self.dev_csv, self.proc_csv) if self.avail else {"assigned_device": {"available": False, "reason": "nvidia-smi not found"}}
        summ.update({"window_utc": [self.t_start, self.t_stop], "period_ms": self.period_ms, "max_s": self.max_s,
                     "raw_files_sha256": {os.path.basename(p): _sha(p) for p in (self.dev_csv, self.proc_csv) if os.path.exists(p)},
                     "labels": {"assigned_device": "device-level for the single GPU assigned to this job; not per-process", "per_process": "nvidia-smi compute-apps rows as returned inside the container; may be empty or namespace-limited"},
                     "billing": "none derived; the event exposes no price or usage receipt"})
        json.dump(summ, open(os.path.join(self.out, "telemetry_summary.json"), "w"), indent=1)


def _f(x):
    try:
        return float(x)
    except ValueError:
        return None


def summarize(dev_csv, proc_csv):
    rows = [l.strip().split(", ") for l in open(dev_csv).read().strip().splitlines()[1:] if l.strip()]
    cols = Q.split(",")
    d = {c: [_f(r[i]) for r in rows if len(r) == len(cols)] for i, c in enumerate(cols) if c != "timestamp"}
    st = lambda v: {"mean": round(sum(x for x in v if x is not None) / max(1, len([x for x in v if x is not None])), 2), "max": max((x for x in v if x is not None), default=None)}
    ts = [r[0] for r in rows if r]
    procs = [l for l in open(proc_csv).read().strip().splitlines()[1:]] if os.path.exists(proc_csv) else []
    pids = sorted({l.split(",")[2].strip() for l in procs if len(l.split(",")) > 2})
    pm = [_f(l.split(",")[-1]) for l in procs if len(l.split(",")) > 4]
    return {"assigned_device": {"available": bool(rows), "n_samples": len(rows), "first_timestamp": ts[0] if ts else None, "last_timestamp": ts[-1] if ts else None,
                                "utilization_gpu_pct": st(d["utilization.gpu"]), "utilization_memory_pct": st(d["utilization.memory"]),
                                "memory_used_MiB": st(d["memory.used"]), "memory_total_MiB": (d["memory.total"][0] if d["memory.total"] else None),
                                "power_draw_W": st(d["power.draw"]), "temperature_C": st(d["temperature.gpu"])},
            "per_process": {"available": bool(procs), "n_rows": len(procs), "distinct_pids": pids, "max_used_memory_MiB": max((x for x in pm if x is not None), default=None)}}
