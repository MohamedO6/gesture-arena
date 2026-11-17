# GESTURE ARENA — low-latency browser edition

**Your hands. Your moves. Challenge the computer.**

The 2026 browser edition replaces the older Python / WebRTC round-trip with **on-device MediaPipe Gesture Recognition**. Streamlit is used only as a page host. Your camera preview, hand model, game loop, scoring and UI all execute in your browser. **No camera frames are sent to the Streamlit Python server, recorded, or saved.**

## Play

1. Open the HTTPS Streamlit URL in a current Chrome, Edge, Safari, or Firefox browser.
2. Click **Enable camera**, allow camera access, and wait for **AI ready · On device**. The camera preview appears before the model finishes loading.
3. Click **Start round**, show one hand, and make a fist (rock), open palm (paper), or victory sign (scissors).
4. Hold your gesture through the brief countdown, then see the computer's random move and the result.
5. Click **Play again**. Scores and the last 10 rounds are stored locally in that browser (when storage is permitted).

If your camera or model isn't available, expand **Camera unavailable?** and play with the Rock / Paper / Scissors buttons or the R / P / S keyboard shortcuts.

## Run locally

Use Python 3.12+:

```sh
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`. Camera access requires a secure context, such as `localhost` or HTTPS. The server only needs `streamlit`; no Python MediaPipe, OpenCV, WebRTC, or Linux graphics libraries are needed.

## Deploy on Streamlit Community Cloud

Use `app.py` as the entrypoint for this repository on Streamlit Community Cloud. A push to `main` triggers a redeploy; if it doesn't, restart the app from Streamlit's app management controls, then hard-refresh your browser.

On the first use **per browser**, the browser downloads the pinned MediaPipe Tasks Vision Web SDK and Google's official Gesture Recognizer model (~8 MB). The user needs network access to `cdn.jsdelivr.net` and `storage.googleapis.com` for the initial load. Normal HTTP caching can make subsequent loads faster. WebGL GPU acceleration is attempted first; CPU inference is used automatically if GPU initialization fails.

## Why this version is faster

- `<video>` renders the webcam directly as a local browser media track, without a server round-trip or returned video encoding.
- MediaPipe performs inference on downscaled 256px frames (Fast mode; 320px in Balanced mode) while the visible camera preview remains full-sized.
- Inference is throttled and dynamically adapts to its measured cost; older video frames are discarded rather than queued.
- The computer opponent, countdown, gesture stabilization, history, and UI render on-device with no Streamlit timers or reruns.
- The model loads only after **Enable camera** is clicked.

Inference time depends on the player's hardware, browser, lighting, and power settings. MediaPipe calls are synchronous: slower devices may still show temporary UI pauses while inference runs. The app adapts its inference cadence to mitigate this. Model downloads require an internet connection; the camera itself is never uploaded.

## Project files

| Path | Role |
|---|---|
| `app.py` | Lightweight Streamlit page with a trusted V2 HTML/CSS/JS component |
| `web/arena.html` | Arena layout, camera, scoreboard, controls, and history |
| `web/arena.css` | Responsive game UI |
| `web/arena.js` | Browser camera access, MediaPipe Web SDK, gesture tracking, countdown and score |
| `requirements.txt` | Only the Streamlit dependency |
| `game.py`, `vision.py`, `runtime.py`, `ui.py` | Preserved legacy Python implementation, no longer used by the deployed app |

**Privacy & integrity:** The frontend downloads program code and the gesture model from the specified public CDN/model endpoints. It does not upload camera data to those services. The computer move is sampled independently of the player's move. No user input is passed as trusted HTML to the component.