#!/usr/bin/env python3
"""Start the reference apps locally, without Docker (ADR 0007):

    DESP   http://127.0.0.1:8000
    PSP A  http://127.0.0.1:8001
    PSP B  http://127.0.0.1:8002

Each app runs as its own process and prints one line per message it sends or
receives. Waits until all three answer GET /health. Ctrl+C stops all of them.

    python3 tools/run_local.py
"""
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = [
    # (name, folder, arguments, port)
    ("DESP", "apps/desp", ["app.py"], 8000),
    ("PSP A", "apps/psp", ["app.py", "config/psp-a.json"], 8001),
    ("PSP B", "apps/psp", ["app.py", "config/psp-b.json"], 8002),
]


def healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_all(log_dir: str | None = None, timeout: float = 20.0) -> list:
    """Start all apps. With log_dir, each app's output goes to <log_dir>/<name>.log,
    otherwise to this terminal. Returns the processes; raises SystemExit on failure."""
    busy = [f"{name} (port {port})" for name, _, _, port in APPS if healthy(port)]
    if busy:
        raise SystemExit(f"Already running: {', '.join(busy)}. Stop them first, or run without --start.")
    procs = []
    for name, folder, args, port in APPS:
        out = open(os.path.join(log_dir, name.replace(" ", "-") + ".log"), "w") if log_dir else None
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        p = subprocess.Popen([sys.executable, *args], cwd=os.path.join(ROOT, folder), stdout=out,
                             stderr=subprocess.STDOUT if out else None, env=env, start_new_session=True)
        p.sim_name, p.sim_port = name, port
        procs.append(p)
    deadline = time.time() + timeout
    waiting = list(procs)
    while waiting and time.time() < deadline:
        for p in list(waiting):
            if p.poll() is not None:
                stop_all(procs)
                where = f" See {os.path.join(log_dir, p.sim_name.replace(' ', '-') + '.log')}." if log_dir else ""
                raise SystemExit(f"{p.sim_name} stopped right after start (exit code {p.returncode}).{where}")
            if healthy(p.sim_port):
                waiting.remove(p)
        time.sleep(0.1)
    if waiting:
        stop_all(procs)
        raise SystemExit("Not healthy in time: " + ", ".join(p.sim_name for p in waiting))
    return procs


def stop_all(procs: list) -> None:
    for p in procs:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)


def _stop_on_sigterm(signum, frame):
    raise KeyboardInterrupt  # handled like Ctrl+C below


def main():
    signal.signal(signal.SIGTERM, _stop_on_sigterm)
    signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl+C, also when started in the background
    procs = start_all()
    print("\nAll apps are up:", ", ".join(f"{p.sim_name} http://127.0.0.1:{p.sim_port}" for p in procs))
    print("Try:  python3 tools/e2e_flows.py      Stop: Ctrl+C\n", flush=True)
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        print("An app stopped; stopping the others.")
    except KeyboardInterrupt:
        print("\nStopping …")
    finally:
        stop_all(procs)


if __name__ == "__main__":
    main()
