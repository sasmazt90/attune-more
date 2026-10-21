"""Linux runner service handoff; never kill a process discovered through a port."""
import os
import signal
import socket
import time

import psutil


def free_port(port, reuse=True):
    # Match asyncio/Uvicorn/Node server binding. TIME_WAIT is not a listener.
    # Never use SO_REUSEPORT: an existing listener must still block the run.
    with socket.socket() as probe:
        if reuse:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', port))
        probe.listen(1)


def wait_free_ports(ports, seconds=5):
    deadline = time.monotonic() + seconds
    while True:
        blocked = []
        for port in ports:
            try:
                free_port(port)
            except OSError:
                blocked.append(port)
        if not blocked:
            return list(ports)
        if time.monotonic() >= deadline:
            raise ValueError('SERVICE_PORTS_NOT_RELEASED: ' + ','.join(map(str, blocked)))
        time.sleep(.05)


def port_observations(ports):
    """Numerical socket state and process name only; no command lines/env."""
    rows = []
    for connection in psutil.net_connections(kind='tcp'):
        if connection.laddr.port not in ports:
            continue
        name = None
        if connection.pid:
            try:
                name = psutil.Process(connection.pid).name()
            except psutil.Error:
                pass
        rows.append({'port': connection.laddr.port, 'state': connection.status,
                     'pid': connection.pid, 'processName': name})
    return rows


def group_running(pgid):
    # A reaped leader can leave live children; PID 1 may retain exited zombies.
    # Neither poll() on the leader nor killpg(..., 0) alone establishes cleanup.
    for process in psutil.process_iter(['pid', 'status']):
        try:
            if os.getpgid(process.pid) == pgid and process.info['status'] not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                return True
        except (ProcessLookupError, PermissionError, psutil.Error):
            continue
    return False


def stop_owned_services(processes, seconds=10):
    """Only Popen records created by this caller with start_new_session=True."""
    groups = [process.pid for process in processes]
    if any(pgid <= 1 or pgid == os.getpgrp() for pgid in groups):
        raise ValueError('UNSAFE_SERVICE_PROCESS_GROUP')

    def send(pgid, sig):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass

    # Signal known groups even when their original leader has already exited.
    for pgid in groups:
        send(pgid, signal.SIGTERM)
    deadline = time.monotonic() + seconds
    while any(group_running(pgid) for pgid in groups) and time.monotonic() < deadline:
        time.sleep(.05)
    for pgid in groups:
        if group_running(pgid):
            send(pgid, signal.SIGKILL)
    for process in processes:
        process.wait(timeout=5)
    deadline = time.monotonic() + 5
    while any(group_running(pgid) for pgid in groups):
        if time.monotonic() >= deadline:
            raise ValueError('OWNED_SERVICE_GROUP_NOT_STOPPED')
        time.sleep(.05)
    return [{'pid': process.pid, 'exitCode': process.returncode, 'groupStopped': True}
            for process in processes]
