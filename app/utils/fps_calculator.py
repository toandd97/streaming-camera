"""
Sliding window FPS calculator.

Usage:
    fps_calc = SlidingWindowFPS(window_size=30)
    fps_calc.tick()          # call each time a frame is received
    fps = fps_calc.get_fps() # returns current FPS
"""
import time
from collections import deque


class SlidingWindowFPS:
    """Calculates FPS using a sliding window of recent frame timestamps."""

    def __init__(self, window_size: int = 30):
        self._window_size = window_size
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def tick(self) -> None:
        """Record that a frame was received right now."""
        self._timestamps.append(time.monotonic())

    def get_fps(self) -> float:
        """Calculate current FPS based on timestamps in the window."""
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return round((len(self._timestamps) - 1) / elapsed, 2)

    def reset(self) -> None:
        self._timestamps.clear()
