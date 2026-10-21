"""Cooperative controls for independent sample generation."""
import threading
from typing import Optional, Callable, Any, Dict
StatusCallback = Callable[[Dict[str, Any]], None]

class RunControl:
    """Thread-safe pause/resume/stop control owned by the user interface."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._force_stop = threading.Event()

    def request_stop(self, *, force: bool = False) -> None:
        self._stop.set()
        if force:
            self._force_stop.set()
        self._pause.clear()

    def pause(self) -> None:
        if not self._stop.is_set():
            self._pause.set()

    def resume(self) -> None:
        self._pause.clear()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    @property
    def force_stop_requested(self) -> bool:
        return self._force_stop.is_set()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def wait_while_paused(self, callback: Optional[StatusCallback] = None) -> None:
        while self.paused and not self.stop_requested:
            if callback:
                callback({"status": "paused", "message": "Sample generation paused"})
            self._stop.wait(0.5)
