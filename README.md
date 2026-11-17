# GESTURE ARENA

**Your hands. Your moves. Challenge the AI.**

A complete Python and Streamlit rock, paper, scissors game. Raise one hand, hold a gesture through the countdown, and face a fair random computer opponent. The camera is the controller; both moves, the winner, the score, and the last ten rounds appear in the arena.

## Run locally

Use **64-bit CPython 3.12 or 3.13**. The included dependency versions were selected for these Python versions; Python 3.11 is not compatible with the pinned NumPy version. Windows x64 is the validated development environment. macOS and Linux need a platform supported by the MediaPipe wheels.

From this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

On macOS/Linux, activate using `source .venv/bin/activate` instead. On Debian/Ubuntu install the OpenCV runtime libraries first:

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libglib2.0-0 libegl1 libgles2
```

Open **http://localhost:8501**. Localhost is a browser secure-context exception, so local HTTPS is not necessary. Using a plain HTTP LAN IP from another device generally will not grant camera access; use an HTTPS deployment for that device.

The first run downloads Google's official, versioned [Gesture Recognizer model](https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task) (approximately 8.4 MB) into `models/gesture_recognizer.task`. The folder must be writable, and the server needs outbound HTTPS to `storage.googleapis.com`. Downloads are checked as task archives and installed atomically; interrupted downloads can be retried. No model download is necessary on subsequent runs while that file remains. No manual HTML files, custom JavaScript, or Colab setup are needed.

## Play

1. Click **ENABLE CAMERA** and grant browser camera access. Select the intended camera in the WebRTC device picker if necessary. Audio is disabled.
2. Click **START ROUND**.
3. Raise **one hand** into the corner brackets. Keep your palm facing the camera and your whole hand in view.
4. Choose **✊ ROCK** (closed fist), **✋ PAPER** (open palm), or **✌️ SCISSORS** (victory sign).
5. Hold the same gesture through **3 → 2 → 1 → SHOOT!**. Moving out of the zone, changing your gesture, low confidence, an extra hand, or losing the hand cancels the countdown and waits for a fresh stable gesture.
6. The computer chooses at SHOOT. Both moves are revealed, and the winner and score update. Click **PLAY AGAIN** to keep the match going.

**CANCEL ROUND** preserves existing scores. **RESET MATCH** clears scores and history; an active round requires an inline confirmation. **STOP CAMERA** asks WebRTC to stop the browser media tracks and immediately invalidates late worker updates. A round already committed at SHOOT is retained. Closing the page triggers the processor's stream-ended cleanup.

The computer uses `random.choice(tuple(Move))` with equal probability and receives no player information. The computer move stays hidden until RESULT. Win rate is `player wins / all completed rounds × 100`; draws remain in the denominator. The score survives Streamlit reruns and camera restarts within the same browser session. Refreshing into a new session, a server restart, or a disconnected session expiring may clear it; there is no account or database persistence.

## Recognition and readiness

The official model's `Closed_Fist`, `Open_Palm`, and `Victory` labels map to the three game moves. Other labels are not accepted. Defaults are **65% confidence**, **six consecutive matching frames**, and **at least 0.3 seconds** of stability. Settings can be changed between rounds in **Camera help & settings**.

The palm center (wrist plus four knuckle bases) must fall within normalized bounds **x = 0.18–0.82, y = 0.12–0.76**. The entire hand must also remain inside the image with a small margin. The target brackets use those same bounds. This provides identical readiness criteria for a fist, palm, and victory sign. For faster single-player inference, MediaPipe tracks only one hand. Keep any other hands outside the frame; the fast mode cannot reliably reject a second hand.

Frames are mirrored in OpenCV exactly once. Green lines and cyan points show hand landmarks. The browser requests 384×288 video at 15 FPS (up to 20), and MediaPipe inference is capped at 384 pixels wide. The processed video preview still travels to the browser via WebRTC; network delay may remain. Low light, motion blur, a palm turned sideways, and fingers cropped out of view reduce accuracy. Six frames do not imply a fixed frame rate; both a frame count and a time requirement must be met.

## Deployment on Streamlit Community Cloud

1. Push the contents of this folder to a GitHub repository. Include `requirements.txt`, `packages.txt`, and `.streamlit/config.toml`. Do not commit `.venv/`, generated model files, or real TURN credentials.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app from that repository and select **app.py** as the entrypoint.
3. In advanced settings, select **Python 3.13** (or 3.12). `packages.txt` installs the Linux OpenCV libraries. If the project is in a subfolder, keep the dependency/configuration files in the locations described in the [Cloud file organization guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).
4. Add TURN credentials in the app's **Secrets** settings if the hosting network or your users' networks require a relay. See the example below.
5. Deploy and open the provided **HTTPS** URL. Grant camera access for that origin. Camera access from a phone also needs HTTPS. After a sleeping app wakes, allow time for model initialization.

See the official [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app) and [secrets guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management). Deployment requires your own hosting account; this deliverable does not publish the app.

### STUN, TURN, and WebRTC

The default ICE configuration includes `stun:stun.l.google.com:19302`. STUN helps discover network addresses but **does not guarantee a connection** through restrictive NAT, corporate firewalls, or cloud networks. Allow outbound STUN/UDP and the negotiated WebRTC traffic. A TURN relay is often necessary for reliable remote deployment; choose a provider that supports your hosting/network configuration, including TURN over TLS/TCP where UDP is blocked.

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` locally, or paste this structure into Cloud Secrets and replace the values:

```toml
[turn]
urls = ["turn:your-relay.example.com:3478", "turns:your-relay.example.com:5349?transport=tcp"]
username = "YOUR_TURN_USERNAME"
credential = "YOUR_TURN_CREDENTIAL"
```

TURN credentials are sent to the browser as required for ICE negotiation. Prefer scoped or short-lived credentials from your provider. Never publish the secrets file. For larger deployments, add a provider integration that refreshes expiring credentials. See the [streamlit-webrtc hosting guidance](https://github.com/whitphx/streamlit-webrtc#remote-hosting).

Camera video travels from the browser to **your Python app server** for recognition and back as an annotated preview. TURN relays transport that traffic when configured. The application does not record, save, or upload frames to a separate AI service. The model runs on the server CPU. The lower-resolution single-hand fast mode cuts inference work and video bandwidth, but it cannot eliminate WebRTC round-trip latency. Inter is loaded from Google Fonts, with a system-font fallback if external fonts are blocked.

## Architecture

| File | Responsibility |
|---|---|
| `app.py` | Native Streamlit layout, controls, session lifecycle, WebRTC configuration |
| `game.py` | Pure state machine, stabilization, countdown, fair opponent, scoring, history |
| `runtime.py` | Locked shared state, immutable snapshots, camera generation tokens |
| `vision.py` | Atomic model download, model lifecycle, hand readiness, frame processing |
| `ui.py` | Dark arcade styling and display-only cards/table |
| `tests/` | Rules, state transitions, threading, vision boundary, and Streamlit control tests |

`IDLE → WAITING_FOR_HAND → COUNTDOWN → SHOOT → RESULT`

- A `SharedArena` instance lives in `st.session_state`. All worker mutations and UI reads take the same lock. The worker holds a reference to that object and **never reads or writes `st.session_state` or calls Streamlit UI functions**.
- The model is a **session-scoped `st.cache_resource`**, initialized once per connected browser session, reused across full app reruns and camera restarts, and closed through `on_release`. Each session has its own VIDEO model/tracking state; users never share timestamps or hand tracking. The downloaded model file is shared safely within the server process.
- Inference and model cleanup share a separate model lock. VIDEO timestamps are strictly increasing, including after camera restart. The processor serializes inference and publishes observations after processing.
- Every countdown frame must remain valid. A frame gap over 0.45 seconds cancels it; a 0.70-second stale timeout also cancels if frames stop altogether. Only a **fresh valid frame** may commit SHOOT; a UI timer alone cannot finish the countdown on stale input.
- The opponent is sampled once at SHOOT, then the result appears after a short 0.35-second reveal beat. Repeated ticks and frames cannot score a round twice. History keeps ten records; score totals keep all completed rounds.
- Generation tokens reject late frames or end callbacks from older streams after a restart. Stop clears observations and cancels an uncommitted round.
- Timed **Streamlit fragments** refresh game displays and controls. The WebRTC component is outside timed fragments and has a stable key, so countdown refreshes do not recreate the stream. HTML/CSS is used only for presentation; all gameplay and recognition run in Python, and all controls use Streamlit widgets.
- There are no blocking sleeps in gameplay and no permanent polling loop on the UI thread.

## Troubleshooting

| Symptom | Action |
|---|---|
| Permission denied / no camera | Grant camera permission for this origin; check the camera is connected and enabled, then stop and re-enable it. The browser's WebRTC component shows its own device/permission errors. |
| Camera already in use | Close other camera apps, select another device, then reconnect. |
| Connecting but no video | Use localhost or HTTPS; check network restrictions and configure TURN. After 18 seconds without frames the game displays recovery guidance and keeps Start disabled. |
| Model download fails | Check outbound HTTPS to `storage.googleapis.com` and write access to `models/`; click Retry hand model. For offline setup, place the linked official model at the documented path before starting. |
| Model initialization fails | Reinstall the pinned requirements in a fresh Python 3.12/3.13 environment. On Linux install `packages.txt` system libraries. Check server logs for details. |
| Vision pauses during a stream | Stop and restart the camera. Reload the session if needed. The server logs the exception, while the UI shows recovery instructions. |
| Countdown never starts | Show one supported gesture in the target brackets; improve lighting, face your palm toward the camera, and keep fingers in view. |
| Countdown keeps restarting | Keep the same gesture steady; check confidence and reduce camera/CPU load. Adjust confidence or stability settings between rounds if needed. |
| Settings do not apply | Finish or cancel the active round, then apply settings. |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover all nine move combinations, official label mapping, random-choice inputs/timing, stability across frames and time, invalid/changed gestures, dropped/stale frames, duplicate observations, all round phases, one-time scoring, replay, reset confirmation, last-ten history, win-rate denominator, camera cancellation, safe concurrent state access, mirrored frame processing, model download failure/retry, and native Streamlit controls.

Streamlit control tests replace the model and WebRTC boundary with synthetic inputs. They do **not** establish that a real browser camera permission flow or remote ICE connection works. See `TEST_REPORT.md` for what was actually run and the remaining live-camera acceptance checklist.

To include the five real-model integration tests (downloads public upstream test images and the model if absent), use PowerShell:

```powershell
$env:GESTURE_ARENA_MODEL_TESTS = "1"
python -m pytest -q
```

On macOS/Linux: `GESTURE_ARENA_MODEL_TESTS=1 python -m pytest -q`. These tests use MediaPipe's public sample hands; they do not turn on your camera.

## References

- [MediaPipe Gesture Recognizer Python guide](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/python)
- [Streamlit fragments](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- [Streamlit resource caching](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource)
- [streamlit-webrtc project and thread-safety guidance](https://github.com/whitphx/streamlit-webrtc)

Dependency and model licenses remain those of their respective upstream projects. No existing detector source was attached to the brief, so this project supplies a new MediaPipe Tasks implementation using the requested gesture mappings.
