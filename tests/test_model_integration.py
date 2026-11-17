"""Opt-in real-model checks using public upstream MediaPipe test images.

PowerShell: $env:GESTURE_ARENA_MODEL_TESTS='1'; python -m pytest tests/test_model_integration.py -v
Requires network access; does not access a physical camera or store user video.
"""
import os
from pathlib import Path
import time
import urllib.request

import cv2
import numpy as np
import pytest

from game import GameConfig, GameEngine, Move, Phase
from vision import VisionModel, classify_result

pytestmark = pytest.mark.skipif(os.environ.get('GESTURE_ARENA_MODEL_TESTS') != '1',
                                reason='Opt-in real MediaPipe model and public test-image download')
ASSET_BASE = 'https://storage.googleapis.com/mediapipe-assets/'


@pytest.fixture(scope='module')
def actual_model():
    model = VisionModel()
    yield model
    model.close()


@pytest.fixture(scope='module')
def assets(tmp_path_factory):
    path = tmp_path_factory.mktemp('upstream-mediapipe-images')
    for name in ('fist.jpg', 'victory.jpg', 'right_hands.jpg', 'cats_and_dogs.jpg'):
        (path / name).write_bytes(urllib.request.urlopen(ASSET_BASE + name, timeout=30).read())
    return path


def input_image(path: Path, crop=False):
    bgr = cv2.imread(str(path))
    assert bgr is not None
    if crop:
        bgr = bgr[:, bgr.shape[1] // 2:]
    # Public sample hands sit close to image edges; put them comfortably in the target.
    bgr = cv2.copyMakeBorder(bgr, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=(240,240,240))
    return cv2.cvtColor(cv2.flip(bgr, 1), cv2.COLOR_BGR2RGB)


@pytest.mark.parametrize('filename,crop,expected', [
    ('fist.jpg', False, Move.ROCK), ('victory.jpg', False, Move.SCISSORS), ('right_hands.jpg', True, Move.PAPER)
])
def test_real_model_recognizes_each_move(actual_model, assets, filename, crop, expected):
    blank = np.zeros((480, 640, 3), np.uint8)
    for _ in range(3):
        actual_model.recognize(blank, time.monotonic())
    rgb = input_image(assets / filename, crop)
    for _ in range(5):
        result = actual_model.recognize(rgb, time.monotonic())
    detected = classify_result(result, time.monotonic())
    assert detected.move == expected
    assert detected.valid(GameConfig()), detected


def test_real_model_no_hand(actual_model, assets):
    rgb = input_image(assets / 'cats_and_dogs.jpg')
    for _ in range(3):
        detected = classify_result(actual_model.recognize(rgb, time.monotonic()), time.monotonic())
    assert detected.hand_count == 0
    assert detected.move is None


def test_real_predictions_drive_complete_game(actual_model, assets):
    rgb = input_image(assets / 'fist.jpg')
    game = GameEngine(choose_move=lambda: Move.SCISSORS)
    assert game.start_round()
    # Virtual game times make this deterministic; inference still uses real VIDEO timestamps.
    for index in range(85):
        result = actual_model.recognize(rgb, time.monotonic())
        at = 10 + index * .05
        game.observe(classify_result(result, at))
        game.tick(at)
    assert game.phase == Phase.RESULT
    assert game.score.player == game.score.total == 1
    assert game.history[0].player == Move.ROCK
