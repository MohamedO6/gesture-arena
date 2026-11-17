import io
from types import SimpleNamespace as NS
from urllib.error import URLError
from unittest.mock import Mock
import zipfile

import av
import numpy as np
import pytest

from game import Move
from runtime import SharedArena
from vision import (ArenaVideoProcessor, ModelLoadError, classify_result, draw_overlay,
                    ensure_model, hand_readiness)


def landmarks(x=.5, y=.4):
    return [NS(x=x, y=y, z=0) for _ in range(21)]


def result(category='Closed_Fist', score=.95, hands=1):
    return NS(hand_landmarks=[landmarks() for _ in range(hands)],
              gestures=[[NS(category_name=category, score=score)] for _ in range(hands)])


@pytest.mark.parametrize('category,expected', [('Closed_Fist', Move.ROCK), ('Open_Palm', Move.PAPER),
                                             ('Victory', Move.SCISSORS), ('Thumb_Up', None), ('None', None)])
def test_model_categories(category, expected):
    detected = classify_result(result(category), 1)
    assert detected.move == expected
    assert detected.in_zone and detected.hand_count == 1
    assert detected.confidence == .95


@pytest.mark.parametrize('hands', [0, 2])
def test_no_hand_and_multiple_hands_are_not_classified(hands):
    detected = classify_result(result(hands=hands), 1)
    assert detected.hand_count == hands
    assert detected.move is None
    assert not detected.in_zone


@pytest.mark.parametrize('x,y,text', [(.5,.9,'higher'), (.5,.05,'lower'), (.1,.4,'center')])
def test_target_zone_instructions(x, y, text):
    ready, hint = hand_readiness(landmarks(x, y))
    assert not ready
    assert text in hint


def test_clipped_fingers_are_not_ready():
    hand = landmarks()
    hand[8].x = 1.1
    ready, hint = hand_readiness(hand)
    assert not ready
    assert 'whole hand' in hint


def test_processor_mirrors_and_publishes_without_streamlit_state():
    arena = SharedArena()
    arena.arm_camera(1)
    model = Mock()
    model.recognize.return_value = result(hands=0)
    processor = ArenaVideoProcessor(model, arena)
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    pixels[:, :320] = [0, 0, 255]
    processed = processor.recv(av.VideoFrame.from_ndarray(pixels, format='bgr24'))
    output = processed.to_ndarray(format='bgr24')
    assert tuple(output[0, 0]) == (0, 0, 0)
    assert tuple(output[0, 639]) == (0, 0, 255)
    assert arena.snapshot(__import__('time').monotonic()).camera_live
    processor.on_ended()
    assert not arena.snapshot(__import__('time').monotonic()).camera_live


def test_processor_recognition_failure_returns_video_and_friendly_error():
    arena = SharedArena()
    arena.arm_camera(1)
    model = Mock()
    model.recognize.side_effect = RuntimeError('bad inference')
    processor = ArenaVideoProcessor(model, arena)
    output = processor.recv(av.VideoFrame.from_ndarray(np.zeros((480,640,3), np.uint8), format='bgr24'))
    assert isinstance(output, av.VideoFrame)
    snapshot = arena.snapshot(__import__('time').monotonic())
    assert 'restart the camera' in snapshot.vision_error
    assert not arena.start_round(__import__('time').monotonic())


def test_landmark_overlay_changes_frame_and_keeps_dimensions():
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    recognized = result()
    output = draw_overlay(pixels, recognized, classify_result(recognized, 1))
    assert output.shape == (480, 640, 3)
    assert output.any()
    assert tuple(output[192, 320]) != (0, 0, 0)


def model_archive():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('dummy.tflite', b'0' * 1_100_000)
    return buffer.getvalue()


def test_model_download_is_atomic_and_cached(tmp_path, monkeypatch):
    opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(model_archive()))
    monkeypatch.setattr('vision.urllib.request.urlopen', opener)
    path = tmp_path / 'models' / 'model.task'
    assert ensure_model(path) == path
    assert zipfile.is_zipfile(path)
    ensure_model(path)
    assert opener.call_count == 1
    assert not list(path.parent.glob('*.part'))


def test_download_failure_can_be_retried(tmp_path, monkeypatch):
    opener = Mock(side_effect=URLError('offline'))
    monkeypatch.setattr('vision.urllib.request.urlopen', opener)
    path = tmp_path / 'model.task'
    with pytest.raises(ModelLoadError, match='internet connection'):
        ensure_model(path)
    assert not path.exists()
    opener.side_effect = lambda *args, **kwargs: io.BytesIO(model_archive())
    assert ensure_model(path).exists()


def test_incomplete_model_never_replaces_cache(tmp_path, monkeypatch):
    monkeypatch.setattr('vision.urllib.request.urlopen', lambda *args, **kwargs: io.BytesIO(b'broken'))
    path = tmp_path / 'model.task'
    with pytest.raises(ModelLoadError):
        ensure_model(path)
    assert not path.exists()
    assert not list(tmp_path.glob('*.part'))
