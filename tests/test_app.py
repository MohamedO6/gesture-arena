"""Native Streamlit controls tested with a synthetic camera/model boundary."""
from pathlib import Path
import time
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest
import streamlit as st
import streamlit_webrtc
import vision

from game import Move, Observation, Phase

APP = Path(__file__).resolve().parents[1] / 'app.py'


@pytest.fixture(autouse=True)
def isolated_resource_cache():
    # AppTest uses one test session identifier across independent AppTest objects.
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


@pytest.fixture
def app(monkeypatch):
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(vision, 'VisionModel', factory)
    monkeypatch.setattr(streamlit_webrtc, 'webrtc_streamer', lambda **kwargs: None)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    return at, factory


def connect(app):
    at, _ = app
    at.button(key='toggle_camera').click().run()
    arena = at.session_state['arena']
    generation = arena.open_stream()
    arena.publish(Observation(time.monotonic()), generation)
    at.run()
    assert not at.exception
    return arena, generation


def test_start_disabled_without_camera_and_model_cached_on_rerun(app):
    at, factory = app
    assert at.button(key='start_round').disabled
    at.run()
    assert not at.exception
    assert factory.call_count == 1
    connect(app)
    assert not at.button(key='start_round').disabled
    assert factory.call_count == 1


def test_play_round_play_again_reset_and_stop_controls(app):
    at, _ = app
    arena, generation = connect(app)
    at.button(key='start_round').click().run()
    assert arena.snapshot(time.monotonic()).game.phase == Phase.WAITING_FOR_HAND
    assert at.button(key='start_round').disabled
    at.button(key='cancel_round').click().run()
    assert arena.snapshot(time.monotonic()).game.phase == Phase.IDLE
    at.button(key='start_round').click().run()
    begin = time.monotonic()
    # Frames exercise the production state machine; no outcome is injected.
    for index in range(80):
        arena.publish(Observation(begin + index*.05, 1, True, Move.ROCK, .95), generation)
    arena.snapshot(begin + 4.1)
    at.run()
    assert not at.exception
    assert at.button(key='start_round').label == 'PLAY AGAIN'
    assert arena.snapshot(begin + 4.1).game.score.total == 1
    at.button(key='start_round').click().run()
    assert arena.snapshot(begin + 4.1).game.score.total == 1
    at.button(key='reset_match').click().run()
    assert at.session_state['confirm_reset']
    assert arena.snapshot(begin + 4.1).game.score.total == 1
    at.button(key='confirm_yes').click().run()
    assert arena.snapshot(begin + 4.1).game.score.total == 0
    assert not arena.snapshot(begin + 4.1).game.history
    at.button(key='toggle_camera').click().run()
    assert not at.exception
    assert not at.session_state['want_camera']
    assert at.button(key='start_round').disabled


def test_model_failure_has_retry_and_disables_camera(monkeypatch):
    factory = Mock(side_effect=vision.ModelLoadError('Model download unavailable. Check internet.'))
    monkeypatch.setattr(vision, 'VisionModel', factory)
    monkeypatch.setattr(streamlit_webrtc, 'webrtc_streamer', lambda **kwargs: None)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert 'Check internet' in at.error[0].value
    assert at.button(key='toggle_camera').disabled
    factory.side_effect = None
    factory.return_value = Mock()
    at.button(key='retry_model').click().run()
    assert not at.exception
    assert not at.button(key='toggle_camera').disabled
