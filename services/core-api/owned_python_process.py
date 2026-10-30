"""Terminate a process we launched, including Windows venv redirectors."""
import psutil


class OwnedProcessTree:
    def __init__(self, pid):
        try:
            self.root = psutil.Process(pid) if pid is not None else None
        except psutil.NoSuchProcess:
            self.root = None

    def terminate(self):
        root = self.root
        if root is None or not root.is_running():
            return
        # Process instances retain creation identity and reject reused PIDs.
        descendants = root.children(recursive=True)[::-1]
        for process in [*descendants, root]:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        # The asyncio/Popen owner reaps the root, avoiding competing waiters.
        _, alive = psutil.wait_procs(descendants, timeout=5)
        if alive:
            raise RuntimeError('OWNED_PYTHON_PROCESS_DID_NOT_EXIT')
