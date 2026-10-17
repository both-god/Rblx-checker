from threading import Lock


class ThreadLock:
    def __init__(self):
        self._lock = Lock()

    def get_lock(self) -> Lock:
        return self._lock


lock = ThreadLock()