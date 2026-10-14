#!/usr/bin/env python3
"""Shared Atomic Heavy-Job Lock across TOGG Workspaces.

Guarantees mutually exclusive heavy computation between workspaces (e.g. skin vs CD).
Maintains PID, processStarted, jobId, workspace, and unique nonce in lock ledger.
Only releases own lock, and verifies process ownership before clearing stale workspace locks.
Never deletes CDC lock file. Fails closed on AccessDenied or unverifiable lock data.
"""

import os
import sys
import time
import json
import uuid
import math
from pathlib import Path
from contextlib import contextmanager
import psutil

LOCK_FILE = Path(r"C:\Users\PC\Desktop\AI Workspace\TOGG\heavy_job.lock")
CDC_LOCK_FILE = Path(r"C:\Users\PC\Desktop\AI Workspace\TOGG\coordination-notes\heavy-compute.lock.json")

# Current process nonce for session ownership
_CURRENT_NONCE = uuid.uuid4().hex


def verify_pid_identity(pid: int, expected_start: float = None):
    """Verify whether a process is running and matches expected creation time.
    
    Returns:
        (True, "ALIVE") if running and matching start time
        (False, "NO_SUCH_PROCESS") if definitely dead
        (None, "ACCESS_DENIED") if permission denied (ambiguous ownership)
        (False, "START_TIME_MISMATCH") if PID was recycled by a different process
    """
    try:
        proc = psutil.Process(pid)
        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
            return False, "NO_SUCH_PROCESS"
        
        if expected_start is not None and math.isfinite(expected_start):
            birth = proc.create_time()
            if abs(birth - expected_start) > 2.0:
                return False, "START_TIME_MISMATCH"
        
        return True, "ALIVE"
    except psutil.NoSuchProcess:
        return False, "NO_SUCH_PROCESS"
    except psutil.AccessDenied:
        return None, "ACCESS_DENIED"


def check_cdc_lock(timeout_sec: float = 0.0) -> None:
    """Check CDC coordination lock and prevent colliding with active CDC compute jobs.
    
    Fails closed on active lock, unreadable lock, or AccessDenied (ambiguous ownership).
    Never deletes CDC lock file.
    """
    t_start = time.time()
    while CDC_LOCK_FILE.exists():
        try:
            raw = CDC_LOCK_FILE.read_text(encoding="utf-8")
            cdc_data = json.loads(raw)
        except Exception as e:
            raise RuntimeError(
                f"Unverifiable CDC coordination lock at {CDC_LOCK_FILE} ({e}). "
                f"Ambiguous ownership; cannot start heavy job."
            ) from e

        if not isinstance(cdc_data, dict):
            raise RuntimeError(
                f"Invalid CDC coordination lock format at {CDC_LOCK_FILE}. "
                f"Cannot start heavy job."
            )

        cdc_pid = cdc_data.get("pid")
        cdc_start = cdc_data.get("processStarted", cdc_data.get("startTime"))

        if not isinstance(cdc_pid, int) or cdc_pid <= 0:
            raise RuntimeError(
                f"CDC lock contains invalid PID ({cdc_pid}) at {CDC_LOCK_FILE}. "
                f"Cannot start heavy job."
            )

        is_alive, reason = verify_pid_identity(cdc_pid, cdc_start)

        if reason == "ACCESS_DENIED":
            raise RuntimeError(
                f"CDC lock held by PID {cdc_pid} cannot be verified due to AccessDenied. "
                f"Ambiguous process ownership; cannot start heavy job."
            )

        if is_alive:
            if time.time() - t_start < timeout_sec:
                time.sleep(2.0)
                continue
            raise RuntimeError(
                f"CDC heavy computation lock is currently held by active PID {cdc_pid} "
                f"(started: {cdc_start}, job: {cdc_data.get('jobId')}) at {CDC_LOCK_FILE}. "
                f"Cannot collide with CDC heavy task."
            )
        else:
            # Process definitely does not exist or PID was recycled
            print(
                f"[heavy_job_lock] Note: Stale CDC lock detected (PID {cdc_pid}, reason: {reason}). "
                f"Preserving CDC lock file as read-only per contract.",
                flush=True
            )
            break


def acquire_heavy_lock(job_id: str, timeout_sec: float = 0.0) -> dict:
    """Atomically acquire the heavy-job lock after verifying CDC lock.
    
    If held by an active process, raises RuntimeError.
    If held by a dead process, safely recovers own workspace lock.
    """
    my_pid = os.getpid()
    proc = psutil.Process(my_pid)
    my_start = proc.create_time()
    t_start = time.time()

    # 1. First check CDC lock (fail-closed)
    check_cdc_lock(timeout_sec=timeout_sec)

    # 2. Acquire workspace heavy_job.lock
    while True:
        if LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                # Unreadable workspace lock
                print(f"[heavy_job_lock] Warning: unreadable workspace lock ({e}). Overwriting stale file.", flush=True)
                data = None

            if data and isinstance(data, dict):
                held_pid = data.get("pid")
                held_start = data.get("processStarted", data.get("startTime"))
                held_nonce = data.get("nonce")

                if held_pid == my_pid and held_nonce == _CURRENT_NONCE:
                    # Re-entrant acquisition by same process instance
                    return data

                if held_pid:
                    is_alive, reason = verify_pid_identity(held_pid, held_start)

                    if reason == "ACCESS_DENIED":
                        raise RuntimeError(
                            f"Workspace lock held by PID {held_pid} cannot be verified due to AccessDenied. "
                            f"Ambiguous process ownership; cannot start heavy job."
                        )

                    if is_alive:
                        if time.time() - t_start < timeout_sec:
                            time.sleep(2.0)
                            continue
                        raise RuntimeError(
                            f"Heavy computation lock is currently held by active PID {held_pid} "
                            f"(job: {data.get('jobId')}, started: {held_start}). "
                            f"Cannot collide with ongoing heavy job."
                        )
                    else:
                        print(f"[heavy_job_lock] Stale workspace lock detected (PID {held_pid}, reason: {reason}). Safely recovering.", flush=True)
                        try:
                            LOCK_FILE.unlink(missing_ok=True)
                        except Exception:
                            pass

        payload = {
            "schema": "attune-workspace-heavy-lock-v2",
            "owner": "AG",
            "pid": my_pid,
            "processStarted": my_start,
            "startTime": time.time(),
            "jobId": job_id,
            "nonce": _CURRENT_NONCE,
            "workspace": str(Path.cwd().resolve())
        }

        # Atomic create via 'x' mode
        try:
            with open(LOCK_FILE, "x", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"[heavy_job_lock] Acquired heavy job lock for job '{job_id}' (PID: {my_pid}, nonce: {_CURRENT_NONCE[:8]})", flush=True)
            return payload
        except FileExistsError:
            # Race condition, retry check
            time.sleep(0.5)


def release_heavy_lock(job_id: str = None) -> bool:
    """Release workspace lock only if owned by current process and matching nonce."""
    my_pid = os.getpid()
    if not LOCK_FILE.exists():
        return True
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        if data.get("pid") == my_pid and data.get("nonce") == _CURRENT_NONCE:
            LOCK_FILE.unlink(missing_ok=True)
            print(f"[heavy_job_lock] Released heavy job lock for PID {my_pid}", flush=True)
            return True
        else:
            print(f"[heavy_job_lock] Refusing to release lock held by another process or nonce (PID {data.get('pid')})", flush=True)
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
