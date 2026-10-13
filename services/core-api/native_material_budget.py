"""Cooperative request scope for research native inference; no detached work."""
import threading,time

class NativeRequestStopped(RuntimeError):
    pass

class NativeRequestBudget:
    def __init__(self,seconds=45.):
        if not 0<seconds<=45:raise ValueError('Native inference cannot extend the product budget')
        self.deadline=time.monotonic()+seconds;self.event=threading.Event();self.reason=None
    def cancel(self):
        self.reason='CANCELLED';self.event.set()
    def check(self):
        if self.event.is_set():raise NativeRequestStopped(self.reason)
        if time.monotonic()>=self.deadline:
            self.reason='LOCAL_ANALYSIS_TIMEOUT';self.event.set();raise NativeRequestStopped(self.reason)
