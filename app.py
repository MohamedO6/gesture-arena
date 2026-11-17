"""GESTURE ARENA — run with: streamlit run app.py"""
from __future__ import annotations

import logging
import time

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from game import Phase
from runtime import SharedArena
from vision import ArenaVideoProcessor, ModelLoadError, VisionModel
import ui

st.set_page_config(page_title="Gesture Arena · Play with your hands", page_icon="✌️", layout="wide")
LOGGER = logging.getLogger(__name__)


@st.cache_resource(scope="session", on_release=lambda model: model.close(), show_spinner=False)
def load_model() -> VisionModel:
    return VisionModel()


def get_ice_servers() -> list[dict]:
    """TURN credentials belong in Streamlit secrets, never in committed source."""
    servers: list[dict] = [{"urls": ["stun:stun.l.google.com:19302"]}]
    try:
        turn = st.secrets.get("turn", {})
        if turn.get("urls") and turn.get("username") and turn.get("credential"):
            servers.append({"urls": list(turn["urls"]) if not isinstance(turn["urls"], str) else turn["urls"],
                            "username": turn["username"], "credential": turn["credential"]})
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    return servers


if "arena" not in st.session_state:
    # Workers receive this object itself; they never read st.session_state.
    st.session_state.arena = SharedArena()
    st.session_state.want_camera = False
    st.session_state.confirm_reset = False

arena: SharedArena = st.session_state.arena
ui.install_styles(st.session_state.want_camera)

model: VisionModel | None = None
model_error: str | None = None
try:
    with st.spinner("Preparing your challenger · loading hand recognition…"):
        model = load_model()
except ModelLoadError as exc:
    LOGGER.exception("Vision model unavailable")
    model_error = str(exc)
except Exception:
    LOGGER.exception("Unexpected model initialization error")
    model_error = "Hand recognition couldn't start. Check the installation steps in README.md and retry."


@st.fragment(run_every=0.5, key="status_fragment")
def live_status() -> None:
    ui.status(model is not None, arena.snapshot(time.monotonic()).camera_live)


@st.fragment(run_every=0.25, key="scores_fragment")
def live_scores() -> None:
    ui.scoreboard(arena.snapshot(time.monotonic()).game)


@st.fragment(run_every=0.25, key="vision_fragment")
def live_vision() -> None:
    now = time.monotonic()
    snapshot = arena.snapshot(now)
    with st.container(key="vision_card"):
        ui.vision_panel(snapshot.game, now, snapshot.camera_live)
        if snapshot.vision_error:
            st.warning(snapshot.vision_error)
        elif snapshot.camera_requested and not snapshot.camera_live:
            elapsed = now - (snapshot.requested_at or now)
            if elapsed > 18:
                st.warning("We aren't receiving camera video. Allow camera access, close other camera apps, "
                           "then stop and re-enable the camera. On a hosted app, the network may need TURN; see Camera help.")
            else:
                st.caption("Connecting your camera… Allow camera access if your browser asks.")


@st.fragment(run_every=0.12, key="battle_fragment")
def live_battle() -> None:
    now = time.monotonic()
    snapshot = arena.snapshot(now)
    game = snapshot.game
    with st.container(key="arena_card"):
        ui.battle_panel(game, now, snapshot.camera_live)
        label = "PLAY AGAIN" if game.phase == Phase.RESULT else "START ROUND"
        def start_action() -> None:
            arena.start_round(time.monotonic())
            st.session_state.confirm_reset = False

        def reset_action() -> None:
            st.session_state.confirm_reset = not arena.reset_match()

        def confirm_action() -> None:
            arena.reset_match(confirmed=True)
            st.session_state.confirm_reset = False

        def keep_action() -> None:
            st.session_state.confirm_reset = False

        st.button(label, type="primary", width="stretch", key="start_round", on_click=start_action,
                  disabled=game.active or not snapshot.camera_live or model is None or bool(snapshot.vision_error))
        if game.active:
            st.button("CANCEL ROUND", width="stretch", key="cancel_round", on_click=arena.cancel_round,
                      disabled=game.phase == Phase.SHOOT)
        reset_disabled = game.score.total == 0 and not game.active
        st.button("RESET MATCH", width="stretch", key="reset_match", on_click=reset_action, disabled=reset_disabled)
        if st.session_state.confirm_reset:
            st.warning("Reset this match? The active round, scores, and history will be cleared.")
            yes, no = st.columns(2)
            yes.button("YES, RESET", width="stretch", key="confirm_yes", on_click=confirm_action)
            no.button("KEEP PLAYING", width="stretch", key="confirm_no", on_click=keep_action)
        st.html('<div class="rule-strip">✊ Rock beats scissors &nbsp;·&nbsp; ✋ Paper beats rock &nbsp;·&nbsp; ✌️ Scissors beats paper</div>')


@st.fragment(run_every=0.5, key="history_fragment")
def live_history() -> None:
    with st.container(key="history_card"):
        ui.history_panel(arena.snapshot(time.monotonic()).game)


def toggle_camera() -> None:
    st.session_state.want_camera = not st.session_state.want_camera
    if st.session_state.want_camera:
        arena.arm_camera(time.monotonic())
    else:
        arena.stop_camera()
        st.session_state.confirm_reset = False


brand_column, status_column = st.columns([3, 2], vertical_alignment="center")
with brand_column:
    ui.header()
with status_column:
    with st.container(key="status_slot"):
        live_status()

if model_error:
    st.error(model_error)
    if st.button("RETRY HAND MODEL", key="retry_model"):
        load_model.clear()
        st.rerun()

with st.container(key="scores_slot"):
    live_scores()
camera_column, battle_column = st.columns([1, 1.13], gap="large")
with camera_column:
    with st.container(key="camera_card"):
        ui.panel_heading("YOUR CAMERA", "MIRRORED · AUDIO OFF")
        if not st.session_state.want_camera:
            ui.camera_placeholder()
        if model is not None:
            try:
                # Outside timed fragments: game updates never remount the camera.
                with st.container(key="camera_feed"):
                    webrtc_streamer(
                        key="gesture_camera",
                        mode=WebRtcMode.SENDRECV,
                        rtc_configuration={"iceServers": get_ice_servers()},
                        media_stream_constraints={"video": {"width": {"ideal": 640}, "height": {"ideal": 480},
                                                            "frameRate": {"ideal": 24, "max": 30}, "facingMode": "user"}, "audio": False},
                        desired_playing_state=st.session_state.want_camera,
                        video_processor_factory=lambda: ArenaVideoProcessor(model, arena),
                        async_processing=True,
                        video_html_attrs={"autoPlay": True, "controls": False, "muted": True,
                                          "style": {"width": "100%", "borderRadius": "12px"}},
                        media_toggle_controls=False,
                    )
            except Exception:
                LOGGER.exception("WebRTC initialization failed")
                arena.stop_camera()
                st.session_state.want_camera = False
                st.warning("The camera connection couldn't start. Check camera access and try again. "
                           "See Camera help for network requirements.")
        st.button("STOP CAMERA" if st.session_state.want_camera else "ENABLE CAMERA",
                  width="stretch", key="toggle_camera", on_click=toggle_camera, disabled=model is None)
        st.html('<div class="tip"><b>01</b><span>One hand in the brackets. Face your palm toward the camera, '
                'with a little room around your fingers.</span></div>')
    with st.container(key="vision_slot"):
        live_vision()

with battle_column:
    with st.container(key="battle_slot"):
        live_battle()
    with st.expander("HOW TO PLAY"):
        st.markdown("1. **Enable camera** and allow camera access.\n"
                    "2. Click **Start round**, then raise one hand into the brackets.\n"
                    "3. Choose **✊ rock**, **✋ paper**, or **✌️ scissors**. Hold it through **3 → 2 → 1 → SHOOT!**\n"
                    "4. See both moves, then **Play again**. The computer chooses randomly at SHOOT.")
        st.caption("Move out of the zone, change your gesture, or lower your hand to cancel a countdown. "
                   "Your camera video is processed by this app's Python server. It is not recorded or saved.")
    with st.expander("CAMERA HELP & SETTINGS"):
        st.markdown("**No picture?** Allow this site to use your camera and check that it is connected. "
                    "Close Zoom, Teams, or other apps using it. Stop and re-enable the camera after changing permissions.\n\n"
                    "**Can't connect?** Use `localhost` locally or HTTPS when deployed. On restrictive networks, "
                    "configure a TURN relay in Streamlit secrets (instructions in README.md). STUN alone cannot connect every network.")
        current = arena.snapshot(time.monotonic()).game
        threshold = st.slider("Recognition confidence", 50, 95, round(current.config.confidence_threshold * 100),
                              5, format="%d%%", key="confidence_setting")
        frames = st.slider("Matching frames to hold", 3, 15, current.config.stable_frames, key="frames_setting")
        if st.button("APPLY SETTINGS", key="apply_settings"):
            if arena.configure(threshold / 100, frames):
                st.success("Recognition settings saved.")
            else:
                st.info("Finish or cancel the active round before changing recognition settings.")
        st.caption("Defaults: 65% confidence · 6 matching frames · at least 0.3 seconds steady. "
                   "Raise confidence or frame count if recognition feels jumpy.")

with st.container(key="history_slot"):
    live_history()
st.html('<div class="footer">BUILT FOR YOUR NEXT WIN. &nbsp; ✊ &nbsp; ✋ &nbsp; ✌️<br>'
        'Gesture Arena · Fair random opponent · No video recording</div>')
