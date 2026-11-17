"""The only bridge between WebRTC workers and the Streamlit session."""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass

from game import GameEngine, Observation


@dataclass(frozen=True)
class ArenaSnapshot:
    game: GameEngine
    camera_live: bool
    camera_requested: bool
    requested_at: float | None
    vision_error: str | None


class SharedArena:
    def __init__(self, game: GameEngine | None = None) -> None:
        self._lock = threading.RLock()
        self._game = game or GameEngine()
        self._generation = 0
        self._armed = False
        self._requested_at: float | None = None
        self._last_frame: float | None = None
        self._vision_error: str | None = None

    def arm_camera(self, now: float) -> None:
        with self._lock:
            self._armed = True
            self._requested_at = now
            self._vision_error = None

    def open_stream(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def publish(self, observation: Observation, generation: int) -> None:
        with self._lock:
            if not self._armed or generation != self._generation:
                return
            self._last_frame = observation.at
            self._vision_error = observation.error
            self._game.observe(observation)
            self._game.tick(observation.at)

    def stream_ended(self, generation: int) -> None:
        with self._lock:
            if generation == self._generation:
                self._last_frame = None
                self._game.stop_camera()

    def stop_camera(self) -> None:
        with self._lock:
            self._armed = False
            self._generation += 1  # Reject late callbacks from the stopped stream.
            self._requested_at = self._last_frame = None
            self._vision_error = None
            self._game.stop_camera()

    def start_round(self, now: float) -> bool:
        with self._lock:
            fresh = self._last_frame is not None and now - self._last_frame <= self._game.config.stale_seconds
            return bool(self._armed and fresh and not self._vision_error and self._game.start_round())

    def reset_match(self, *, confirmed: bool = False) -> bool:
        with self._lock:
            return self._game.reset_match(confirmed=confirmed)

    def cancel_round(self) -> bool:
        with self._lock:
            return self._game.cancel_round()

    def configure(self, confidence: float, frames: int) -> bool:
        with self._lock:
            return self._game.configure(confidence, frames)

    def snapshot(self, now: float) -> ArenaSnapshot:
        with self._lock:
            self._game.tick(now)
            fresh = self._last_frame is not None and now - self._last_frame <= self._game.config.stale_seconds
            return ArenaSnapshot(copy.deepcopy(self._game), self._armed and fresh,
                                 self._armed, self._requested_at, self._vision_error)
