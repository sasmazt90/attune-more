#!/usr/bin/env python3
"""Shared Atomic Heavy-Job Lock across TOGG Workspaces.

Guarantees mutually exclusive heavy computation between workspaces (e.g. skin vs CD).
Maintains PID, startTime, jobId, and workspace in lock ledger.
Only releases own lock, and verifies process ownership before clearing stale locks.
"""

import os
import sys
import time
import json
from pathlib import Path
from contextlib import contextmanager
import psutil

LOCK_FILE = Path(r"C:\Users\PC\Desktop\AI Workspace\TOGG\heavy_job.lock")
CDC_LOCK_FILE = Path(r"C:\Users\PC\Desktop\AI Workspace\TOGG\coordination-notes\heavy-compute.lock.json")

# Note: Historically, heavy_job.lock (used by skin-research) and CDC's heavy-compute.lock.json
# were not automatically shared. Both are now explicitly verified to prevent mutual compute collisions.


def is_pid_alive(pid: int) -> bool:
    """Check if process with PID is currently active."""
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def check_cdc_lock(timeout_sec: float = 0.0) -> None:
    """Check CDC coordination lock and prevent colliding with active CDC compute jobs."""
    t_start = time.time()
    while CDC_LOCK_FILE.exists():
        try:
            cdc_data = json.loads(CDC_LOCK_FILE.read_text(encoding="utf-8"))
            cdc_pid = cdc_data.get("pid")
            if cdc_pid and is_pid_alive(cdc_pid):
                if time.time() - t_start < timeout_sec:
                    time.sleep(2.0)
                    continue
                raise RuntimeError(
                    f"CDC heavy computation lock is currently held by active PID {cdc_pid} "
                    f"at {CDC_LOCK_FILE}. Cannot collide with CDC heavy task."
                )
            else:
                # Stale CDC lock from dead process; note without deleting CDC file directly
                print(f"[heavy_job_lock] Note: Stale CDC lock detected (PID {cdc_pid} not alive).", flush=True)
                break
        except (json.JSONDecodeError, Exception) as e:
            print(f"[heavy_job_lock] Note: Could not parse CDC lock ({e}).", flush=True)
            break


def acquire_heavy_lock(job_id: str, timeout_sec: float = 0.0) -> dict:
    """Atomically acquire the heavy-job lock after verifying CDC lock.
    
    If held by an active process, raises RuntimeError.
    If held by a dead process, safely recovers the stale lock.
    """
    my_pid = os.getpid()
    t_start = time.time()

    # 1. First check CDC lock
    check_cdc_lock(timeout_sec=timeout_sec)

    # 2. Acquire workspace heavy_job.lock
    while True:
        if LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
                held_pid = data.get("pid")
                if held_pid == my_pid:
                    # Re-entrant acquisition
                    return data
                if held_pid and is_pid_alive(held_pid):
                    if time.time() - t_start < timeout_sec:
                        time.sleep(2.0)
                        continue
                    raise RuntimeError(
                        f"Heavy computation lock is currently held by active PID {held_pid} "
                        f"(job: {data.get('jobId')}, started: {data.get('startTime')}). "
                        f"Cannot collide with ongoing heavy job."
                    )
                else:
                    print(f"[heavy_job_lock] Stale lock detected (dead PID {held_pid}). Safely recovering.", flush=True)
                    try:
                        LOCK_FILE.unlink(missing_ok=True)
                    except Exception:
                        pass
            except json.JSONDecodeError:
                LOCK_FILE.unlink(missing_ok=True)

        payload = {
            "pid": my_pid,
            "jobId": job_id,
            "startTime": time.time(),
            "workspace": os.getcwd()
        }

        # Atomic create via 'x' mode
        try:
            with open(LOCK_FILE, "x", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"[heavy_job_lock] Acquired heavy job lock for job '{job_id}' (PID: {my_pid})", flush=True)
            return payload
        except FileExistsError:
            # Race condition, retry check
            time.sleep(0.5)


def release_heavy_lock(job_id: str = None) -> bool:
    """Release lock only if owned by current process."""
    my_pid = os.getpid()
    if not LOCK_FILE.exists():
        return True
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        if data.get("pid") == my_pid:
            LOCK_FILE.unlink(missing_ok=True)
            print(f"[heavy_job_lock] Released heavy job lock for PID {my_pid}", flush=True)
            return True
        else:
            print(f"[heavy_job_lock] Refusing to release lock held by another process (PID {data.get('pid')})", flush=True)
            return False
    except Exception as e:
        print(f"[heavy_job_lock] Error checking lock for release: {e}", flush=True)
        return False


@contextmanager
def heavy_job_guard(job_id: str):
    """Context manager for heavy computation."""
    acquire_heavy_lock(job_id)
    try:
        yield
    finally:
        release_heavy_lock(job_id)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print("=== Heavy Job Coordination Status ===")
        print(f"1. Workspace Lock ({LOCK_FILE}):")
        if LOCK_FILE.exists():
            print(f"   ACTIVE:\n{LOCK_FILE.read_text('utf-8')}")
        else:
            print("   FREE (No active lock)")

        print(f"\n2. CDC Coordination Lock ({CDC_LOCK_FILE}):")
        if CDC_LOCK_FILE.exists():
            print(f"   ACTIVE:\n{CDC_LOCK_FILE.read_text('utf-8')}")
        else:
            print("   FREE (No active lock)")
