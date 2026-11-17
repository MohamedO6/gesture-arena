"""Gesture Arena — zero-video-upload browser game hosted by Streamlit.

The webcam, MediaPipe recognition, computer opponent and UI run client-side.
The Python process does not receive or process any camera frames.
"""
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Gesture Arena · Play with your hands",
    page_icon="✌️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ASSETS = Path(__file__).resolve().parent / "web"
st.html("""
<style>
[data-testid="stApp"] {background:#080f1c;}
[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1450px;padding:1rem 1rem 2rem;}
[data-testid="stAppToolbar"] {display:none;}
</style>
""")

arena = st.components.v2.component(
    "browser_gesture_arena",
    html=(ASSETS / "arena.html").read_text(encoding="utf-8"),
    css=(ASSETS / "arena.css").read_text(encoding="utf-8"),
    js=(ASSETS / "arena.js").read_text(encoding="utf-8"),
    isolate_styles=True,
)
arena(key="gesture_arena_browser")