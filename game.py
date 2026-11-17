"""Pure Python rules and clock-driven game state. No UI, camera, or sleeps."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Move(str, Enum):
    ROCK = "ROCK"
    PAPER = "PAPER"
    SCISSORS = "SCISSORS"

    @property
    def emoji(self) -> str:
        return {Move.ROCK: "✊", Move.PAPER: "✋", Move.SCISSORS: "✌️"}[self]


GESTURE_MAP = {"Closed_Fist": Move.ROCK, "Open_Palm": Move.PAPER, "Victory": Move.SCISSORS}


class Phase(str, Enum):
    IDLE = "IDLE"
    WAITING_FOR_HAND = "WAITING_FOR_HAND"
    COUNTDOWN = "COUNTDOWN"
    SHOOT = "SHOOT"
    RESULT = "RESULT"


class Outcome(str, Enum):
    WIN = "Win"
    LOSS = "Loss"
    DRAW = "Draw"


def determine_winner(player: Move, computer: Move) -> Outcome:
    if player == computer:
        return Outcome.DRAW
    return Outcome.WIN if (player, computer) in {
        (Move.ROCK, Move.SCISSORS), (Move.SCISSORS, Move.PAPER), (Move.PAPER, Move.ROCK)
    } else Outcome.LOSS


def random_computer_move() -> Move:
    """Equal-probability choice. Deliberately accepts no player information."""
    return random.choice(tuple(Move))


@dataclass(frozen=True)
class GameConfig:
    confidence_threshold: float = 0.65
    stable_frames: int = 6
    stable_seconds: float = 0.30
    countdown_seconds: float = 3.0
    shoot_seconds: float = 0.35
    stale_seconds: float = 0.70
    max_frame_gap: float = 0.45

    def __post_init__(self) -> None:
        if not 0 < self.confidence_threshold <= 1:
            raise ValueError("Confidence must be between zero and one.")
        if self.stable_frames < 2 or self.stable_seconds <= 0:
            raise ValueError("Stability requires multiple frames and a positive duration.")
        if min(self.countdown_seconds, self.shoot_seconds, self.stale_seconds, self.max_frame_gap) <= 0:
            raise ValueError("All timing settings must be positive.")


@dataclass(frozen=True)
class Observation:
    at: float
    hand_count: int = 0
    in_zone: bool = False
    move: Move | None = None
    confidence: float = 0.0
    error: str | None = None
    position_hint: str = "Move your hand into the target zone."

    def valid(self, config: GameConfig) -> bool:
        return (not self.error and self.hand_count == 1 and self.in_zone
                and self.move is not None and self.confidence >= config.confidence_threshold)


@dataclass
class GestureStabilizer:
    config: GameConfig
    candidate: Move | None = None
    count: int = 0
    since: float | None = None
    last_at: float | None = None
    stable: Move | None = None

    def reset(self) -> None:
        self.candidate = self.stable = None
        self.count = 0
        self.since = self.last_at = None

    def update(self, observation: Observation) -> Move | None:
        if not observation.valid(self.config):
            self.reset()
            return None
        gap = self.last_at is None or observation.at - self.last_at > self.config.max_frame_gap
        if observation.move != self.candidate or gap:
            self.candidate = observation.move
            self.count = 0
            self.since = observation.at
            self.stable = None
        self.count += 1
        self.last_at = observation.at
        if (self.count >= self.config.stable_frames and self.since is not None
                and observation.at - self.since >= self.config.stable_seconds - 1e-9):
            self.stable = self.candidate
        return self.stable


@dataclass(frozen=True)
class RoundRecord:
    number: int
    player: Move
    computer: Move
    outcome: Outcome


@dataclass
class Score:
    player: int = 0
    computer: int = 0
    draws: int = 0

    @property
    def total(self) -> int:
        return self.player + self.computer + self.draws

    @property
    def win_rate(self) -> float:
        return 100 * self.player / self.total if self.total else 0.0

    def record(self, outcome: Outcome) -> None:
        if outcome == Outcome.WIN:
            self.player += 1
        elif outcome == Outcome.LOSS:
            self.computer += 1
        else:
            self.draws += 1


@dataclass
class GameEngine:
    """Caller owns synchronization. All times are from time.monotonic()."""
    config: GameConfig = field(default_factory=GameConfig)
    choose_move: Callable[[], Move] = random_computer_move
    phase: Phase = Phase.IDLE
    score: Score = field(default_factory=Score)
    history: list[RoundRecord] = field(default_factory=list)
    observation: Observation | None = None
    countdown_started: float | None = None
    countdown_move: Move | None = None
    shoot_at: float | None = None
    last_round: RoundRecord | None = None
    _pending: RoundRecord | None = None
    stabilizer: GestureStabilizer = field(init=False)

    def __post_init__(self) -> None:
        self.stabilizer = GestureStabilizer(self.config)

    @property
    def active(self) -> bool:
        return self.phase in {Phase.WAITING_FOR_HAND, Phase.COUNTDOWN, Phase.SHOOT}

    def start_round(self) -> bool:
        if self.active:
            return False
        self.phase = Phase.WAITING_FOR_HAND
        self.countdown_started = self.countdown_move = self.shoot_at = None
        self.last_round = self._pending = None
        self.stabilizer.reset()  # Require fresh predictions after the click.
        return True

    def _cancel_countdown(self) -> None:
        self.phase = Phase.WAITING_FOR_HAND
        self.countdown_started = self.countdown_move = None
        self.stabilizer.reset()

    def observe(self, observation: Observation) -> None:
        # Duplicate and out-of-order frames must not build stability or change a round.
        if self.observation is not None and observation.at <= self.observation.at:
            return
        previous_at = self.observation.at if self.observation else None
        self.observation = observation
        stable = self.stabilizer.update(observation)
        if self.phase == Phase.COUNTDOWN:
            uninterrupted = previous_at is not None and observation.at - previous_at <= self.config.max_frame_gap
            if not uninterrupted or not observation.valid(self.config) or observation.move != self.countdown_move:
                self._cancel_countdown()
                return
            if observation.at - self.countdown_started >= self.config.countdown_seconds - 1e-9:  # type: ignore[operator]
                # Only a fresh valid video frame may commit the player's move.
                player = self.countdown_move
                assert player is not None
                computer = self.choose_move()  # Called exactly once, at SHOOT.
                self._pending = RoundRecord(self.score.total + 1, player, computer,
                                            determine_winner(player, computer))
                self.phase = Phase.SHOOT
                self.shoot_at = observation.at
        elif self.phase == Phase.WAITING_FOR_HAND and stable is not None:
            self.phase = Phase.COUNTDOWN
            self.countdown_move = stable
            self.countdown_started = observation.at

    def tick(self, now: float) -> None:
        """Advance reveal, and cancel stale countdowns even if video stops entirely."""
        if self.phase == Phase.SHOOT and self.shoot_at is not None:
            if now - self.shoot_at >= self.config.shoot_seconds:
                self._finish_round()
        if self.observation is not None and now - self.observation.at > self.config.stale_seconds:
            self.stabilizer.reset()
            if self.phase == Phase.COUNTDOWN:
                self._cancel_countdown()

    def _finish_round(self) -> None:
        if self._pending is None:
            return
        self.last_round = self._pending
        self.score.record(self._pending.outcome)
        self.history.append(self._pending)
        self.history = self.history[-10:]
        self._pending = None
        self.phase = Phase.RESULT

    def stop_camera(self) -> None:
        # SHOOT is already committed; preserve that round if the stream ends.
        if self.phase == Phase.SHOOT:
            self._finish_round()
        elif self.active:
            self.phase = Phase.IDLE
        self.observation = None
        self.countdown_started = self.countdown_move = None
        self.stabilizer.reset()

    def cancel_round(self) -> bool:
        if self.phase not in {Phase.WAITING_FOR_HAND, Phase.COUNTDOWN}:
            return False
        self.phase = Phase.IDLE
        self.countdown_started = self.countdown_move = None
        self.stabilizer.reset()
        return True

    def reset_match(self, *, confirmed: bool = False) -> bool:
        if self.active and not confirmed:
            return False
        self.phase = Phase.IDLE
        self.score = Score()
        self.history.clear()
        self.last_round = self._pending = None
        self.countdown_started = self.countdown_move = self.shoot_at = None
        self.stabilizer.reset()
        return True

    def configure(self, confidence_threshold: float, stable_frames: int) -> bool:
        if self.active:
            return False
        from dataclasses import replace
        self.config = replace(self.config, confidence_threshold=confidence_threshold,
                              stable_frames=stable_frames)
        self.stabilizer = GestureStabilizer(self.config)
        return True

    def countdown_number(self, now: float) -> int:
        if self.countdown_started is None:
            return 3
        return max(1, math.ceil(self.config.countdown_seconds - (now - self.countdown_started)))

    def fresh_observation(self, now: float) -> Observation | None:
        if self.observation is None or now - self.observation.at > self.config.stale_seconds:
            return None
        return self.observation

    def feedback(self, now: float) -> str:
        observation = self.fresh_observation(now)
        if observation is not None and observation.error:
            return observation.error
        if observation is None or observation.hand_count == 0:
            return "No hand detected. Raise your hand in front of the camera."
        if observation.hand_count > 1:
            return "One player, one hand. Keep just one hand in view."
        if not observation.in_zone:
            return observation.position_hint
        if observation.move is None:
            return "Gesture not recognized. Try a fist, open palm, or victory sign."
        if observation.confidence < self.config.confidence_threshold:
            return "Gesture not recognized. Try again with your hand facing the camera."
        if self.stabilizer.stable is None:
            return f"{observation.move.value} detected! Hold your gesture."
        if self.phase == Phase.COUNTDOWN:
            return "Hold your gesture! Keep it steady until SHOOT!"
        return "You're ready! Make your move."
