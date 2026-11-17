"""Smoke and architecture checks for the browser-based Gesture Arena."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_uses_client_side_component():
    source = (ROOT / 'app.py').read_text()
    assert 'st.components.v2.component' in source
    assert 'web' in source
    assert 'streamlit_webrtc' not in source
    assert 'VisionModel' not in source


def test_client_game_has_camera_recognition_and_manual_fallback():
    js = (ROOT / 'web' / 'arena.js').read_text()
    html = (ROOT / 'web' / 'arena.html').read_text()
    assert 'navigator.mediaDevices.getUserMedia' in js
    assert 'GestureRecognizer.createFromOptions' in js
    assert 'recognizeForVideo' in js
    assert 'requestAnimationFrame' in js
    assert 'localStorage' in js
    assert 'WebRtcMode' not in js
    assert 'data-move="ROCK"' in html
    assert 'data-move="PAPER"' in html
    assert 'data-move="SCISSORS"' in html


def test_streamlit_app_starts():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    assert not at.exception