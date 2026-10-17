from threading import Lock


class Counter:
    def __init__(self):
        self._value = 0
        self._lock = Lock()

    def increment(self) -> None:
        with self._lock:
            self._value += 1

    def get_value(self) -> int:
        with self._lock:
            return self._value

    def get_and_increment(self) -> int:
        with self._lock:
            val = self._value
            self._value += 1
            return val


counter = Counter()