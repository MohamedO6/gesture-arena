from concurrent.futures import ThreadPoolExecutor

from game import Move, Observation, Phase
from runtime import SharedArena


def test_camera_must_be_live_to_start():
    arena = SharedArena()
    assert not arena.start_round(1)
    arena.arm_camera(1)
    generation = arena.open_stream()
    arena.publish(Observation(1), generation)
    assert arena.snapshot(1).camera_live
    assert arena.start_round(1)
    assert arena.snapshot(1).game.phase == Phase.WAITING_FOR_HAND
    assert not arena.snapshot(2).camera_live


def test_old_callbacks_cannot_revive_stopped_camera():
    arena = SharedArena()
    arena.arm_camera(1)
    old = arena.open_stream()
    arena.stop_camera()
    arena.publish(Observation(2), old)
    assert not arena.snapshot(2).camera_live
    arena.arm_camera(3)
    current = arena.open_stream()
    arena.publish(Observation(3), current)
    arena.stream_ended(old)
    assert arena.snapshot(3).camera_live
    arena.stream_ended(current)
    assert not arena.snapshot(3).camera_live


def test_snapshot_is_detached_and_cannot_mutate_score():
    arena = SharedArena()
    snapshot = arena.snapshot(1)
    snapshot.game.score.player = 999
    assert arena.snapshot(1).game.score.player == 0


def test_concurrent_updates_reads_and_resets_are_safe():
    arena = SharedArena()
    arena.arm_camera(1)
    generation = arena.open_stream()

    def producer():
        for index in range(300):
            arena.publish(Observation(1 + index * .01, hand_count=1, in_zone=True,
                                      move=Move.ROCK, confidence=.95), generation)

    def reader():
        for index in range(300):
            snapshot = arena.snapshot(1 + index * .01)
            assert snapshot.game.score.total == (snapshot.game.score.player + snapshot.game.score.computer + snapshot.game.score.draws)

    def controller():
        for _ in range(50):
            arena.start_round(1)
            arena.reset_match(confirmed=True)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(f) for f in (producer, reader, controller)]
        for future in futures:
            future.result(timeout=10)
