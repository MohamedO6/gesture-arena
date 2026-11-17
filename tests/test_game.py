from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from game import (GESTURE_MAP, GameConfig, GameEngine, GestureStabilizer, Move, Observation,
                  Outcome, Phase, Score, determine_winner, random_computer_move)


@pytest.fixture
def game():
    return GameEngine(GameConfig(stable_frames=3, stable_seconds=.1, countdown_seconds=.6,
                                 shoot_seconds=.1, stale_seconds=.4, max_frame_gap=.2),
                      choose_move=Mock(return_value=Move.SCISSORS))


def observation(at, move=Move.ROCK, **kwargs):
    return replace(Observation(at, hand_count=1, in_zone=True, move=move, confidence=.95), **kwargs)


def stable_hand(game, at=10., move=Move.ROCK):
    for index in range(4):
        game.observe(observation(at + index * .05, move))
    return at + .15


def finish(game, at=10., move=Move.ROCK):
    assert game.start_round()
    for index in range(25):
        now = at + index * .05
        game.observe(observation(now, move))
        game.tick(now)
    assert game.phase == Phase.RESULT


@pytest.mark.parametrize('player,computer,expected', [
    (Move.ROCK, Move.ROCK, Outcome.DRAW),
    (Move.ROCK, Move.PAPER, Outcome.LOSS),
    (Move.ROCK, Move.SCISSORS, Outcome.WIN),
    (Move.PAPER, Move.ROCK, Outcome.WIN),
    (Move.PAPER, Move.PAPER, Outcome.DRAW),
    (Move.PAPER, Move.SCISSORS, Outcome.LOSS),
    (Move.SCISSORS, Move.ROCK, Outcome.LOSS),
    (Move.SCISSORS, Move.PAPER, Outcome.WIN),
    (Move.SCISSORS, Move.SCISSORS, Outcome.DRAW),
])
def test_all_nine_combinations(player, computer, expected):
    assert determine_winner(player, computer) == expected


def test_official_gesture_mapping():
    assert GESTURE_MAP == {'Closed_Fist': Move.ROCK, 'Open_Palm': Move.PAPER, 'Victory': Move.SCISSORS}
    assert 'Thumb_Up' not in GESTURE_MAP


def test_random_opponent_uses_all_moves_without_player_input():
    with patch('game.random.choice', return_value=Move.PAPER) as choice:
        assert random_computer_move() == Move.PAPER
        choice.assert_called_once_with(tuple(Move))


def test_default_stability_requires_frames_and_time():
    stabilizer = GestureStabilizer(GameConfig())
    for index in range(6):
        assert stabilizer.update(observation(index * .01)) is None
    assert stabilizer.update(observation(.31)) == Move.ROCK
    stabilizer.reset()
    for index in range(5):
        assert stabilizer.update(observation(1 + index * .1)) is None
    assert stabilizer.update(observation(1.5)) == Move.ROCK


def test_start_requires_new_predictions(game):
    stable_hand(game)
    assert game.start_round()
    assert game.phase == Phase.WAITING_FOR_HAND
    assert game.stabilizer.stable is None
    game.tick(10.16)
    assert game.phase == Phase.WAITING_FOR_HAND
    game.observe(observation(10.2))
    assert game.phase == Phase.WAITING_FOR_HAND


def test_countdown_starts_after_stability(game):
    game.start_round()
    stable_hand(game)
    assert game.phase == Phase.COUNTDOWN
    assert game.countdown_move == Move.ROCK
    assert not game.start_round()
    game.choose_move.assert_not_called()


@pytest.mark.parametrize('invalid', [
    {'hand_count': 0}, {'hand_count': 2}, {'in_zone': False}, {'move': None},
    {'confidence': .64}, {'move': Move.PAPER}, {'error': 'Vision paused'},
])
def test_invalid_or_changed_hand_cancels_countdown(game, invalid):
    game.start_round()
    stable_hand(game)
    game.observe(observation(10.2, **invalid))
    assert game.phase == Phase.WAITING_FOR_HAND
    assert game.stabilizer.stable is None
    assert game.score.total == 0
    game.choose_move.assert_not_called()


def test_stale_camera_cancels_without_another_frame(game):
    game.start_round()
    stable_hand(game)
    game.tick(11.)
    assert game.phase == Phase.WAITING_FOR_HAND
    assert game.fresh_observation(11.) is None
    assert game.score.total == 0


def test_gap_cancels_even_if_next_frame_valid(game):
    game.start_round()
    stable_hand(game)
    game.observe(observation(10.8))
    assert game.phase == Phase.WAITING_FOR_HAND
    game.choose_move.assert_not_called()


def test_duplicate_and_out_of_order_frames_do_not_stabilize(game):
    game.start_round()
    for at in [10, 10, 9, 10, 10]:
        game.observe(observation(at))
    assert game.stabilizer.count == 1
    assert game.phase == Phase.WAITING_FOR_HAND


def test_shoot_choice_happens_once_and_reveal_counts_once(game):
    game.start_round()
    for index in range(15):
        game.observe(observation(10 + index * .05))
    game.choose_move.assert_called_once_with()
    assert game.phase == Phase.SHOOT
    assert game.last_round is None  # The opponent is not visible before reveal.
    assert game.score.total == 0
    game.tick(10.95)
    assert game.phase == Phase.RESULT
    assert game.last_round.player == Move.ROCK
    assert game.last_round.computer == Move.SCISSORS
    assert game.score.player == 1
    for now in (11, 12, 13):
        game.tick(now)
        game.observe(observation(now, Move.PAPER))
    game.choose_move.assert_called_once_with()
    assert game.score.total == len(game.history) == 1


def test_score_win_rate_includes_draws_in_denominator():
    score = Score()
    assert score.win_rate == 0
    for outcome in [Outcome.WIN, Outcome.WIN, Outcome.LOSS, Outcome.DRAW]:
        score.record(outcome)
    assert (score.player, score.computer, score.draws, score.total, score.win_rate) == (2, 1, 1, 4, 50)


def test_play_again_preserves_score_and_resets_moves(game):
    finish(game)
    assert game.start_round()
    assert game.score.total == 1
    assert len(game.history) == 1
    assert game.last_round is None
    assert game.phase == Phase.WAITING_FOR_HAND


def test_history_last_ten_keeps_actual_round_numbers(game):
    for index in range(12):
        finish(game, at=10 + index * 2)
    assert game.score.total == 12
    assert [r.number for r in game.history] == list(range(3, 13))


def test_reset_clears_all_match_data(game):
    finish(game)
    assert game.reset_match()
    assert game.phase == Phase.IDLE
    assert game.score.total == 0
    assert game.score.win_rate == 0
    assert game.history == []
    assert game.last_round is None


def test_active_reset_requires_confirmation(game):
    finish(game)
    game.start_round()
    stable_hand(game, 12)
    assert not game.reset_match()
    assert game.score.total == 1
    assert game.reset_match(confirmed=True)
    assert game.phase == Phase.IDLE
    assert game.score.total == 0


def test_cancel_preserves_match_and_camera_input(game):
    finish(game)
    game.start_round()
    stable_hand(game, 12)
    assert game.cancel_round()
    assert game.phase == Phase.IDLE
    assert game.score.total == 1
    assert game.observation is not None
    assert not game.cancel_round()


def test_camera_stop_cancels_uncommitted_round(game):
    game.start_round()
    stable_hand(game)
    game.stop_camera()
    assert game.phase == Phase.IDLE
    assert game.observation is None
    assert game.score.total == 0


def test_stop_at_shoot_keeps_committed_result(game):
    game.start_round()
    for index in range(15):
        game.observe(observation(10 + index * .05))
    assert game.phase == Phase.SHOOT
    assert not game.cancel_round()
    game.stop_camera()
    assert game.phase == Phase.RESULT
    assert game.score.total == 1


def test_settings_cannot_change_during_round(game):
    assert game.configure(.8, 8)
    assert game.config.confidence_threshold == .8
    game.start_round()
    assert not game.configure(.5, 3)
    assert game.config.confidence_threshold == .8


@pytest.mark.parametrize('kwargs', [
    {'confidence_threshold': 0}, {'confidence_threshold': 1.1}, {'stable_frames': 1},
    {'stable_seconds': 0}, {'countdown_seconds': -1}, {'stale_seconds': 0},
])
def test_bad_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        GameConfig(**kwargs)


def test_countdown_numbers_are_clock_based():
    game = GameEngine()
    game.start_round()
    for index in range(7):
        game.observe(observation(10 + index * .06))
    start = game.countdown_started
    assert start is not None
    assert [game.countdown_number(start + offset) for offset in [0, .5, 1, 1.5, 2, 2.9]] == [3, 3, 2, 2, 1, 1]
