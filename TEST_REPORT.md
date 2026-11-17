# Verification report

Run on **17 November 2026**, Windows x64, CPython **3.13.7**, using a fresh virtual environment and the pinned dependencies.

## Results

Full suite, including real-model integration:

```text
GESTURE_ARENA_MODEL_TESTS=1 python -m pytest -q
......................................................................   [100%]
70 passed in 24.20s
```

The environment variable syntax above is for POSIX shells. See the README for PowerShell commands.

- **65 automated unit and Streamlit application tests:** all nine outcomes; stable-frame/time requirements; countdown and invalid-gesture cancellation; stale, duplicate, and out-of-order frames; fair opponent inputs and sampling time; one-time scoring; replay; confirmed reset; history and win rate; safe concurrent reads/mutations; old-stream callback rejection; target-zone guidance; mirrored/annotated video; inference failures; model download failure/retry; and Streamlit controls with synthetic camera inputs.
- **5 real MediaPipe integration tests:** actual model initialization; ROCK from `fist.jpg`; SCISSORS from `victory.jpg`; PAPER from a single-hand crop of `right_hands.jpg`; no-hand rejection using `cats_and_dogs.jpg`; and a full scored round driven by actual predictions. The first three are parameterized cases, so the total is five tests. These use public [upstream MediaPipe assets](https://storage.googleapis.com/mediapipe-assets/fist.jpg), not a physical webcam.
- `python -m pip check`: **No broken requirements found.**
- Local Streamlit server: started successfully; `/_stcore/health` returned **ok**.
- Real browser startup: model showed **MODEL READY**, score initialized to zero, and Start round remained disabled while the camera was off.
- Visual/browser inspection: **1366 × 1000 desktop** and **390 × 844 mobile**. All three primary panels fit the mobile width; page width was 390 pixels with no horizontal overflow. Help expanded correctly. Static help/footer remained present across timed fragment refreshes after adding isolated fragment containers.
- Preview images are supplied beside the project folder: `gesture-arena-preview.jpg` and `gesture-arena-mobile.jpg`.

The official downloaded task bundle was 8,373,440 bytes, SHA-256:

```text
97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482
```

## Acceptance coverage and remaining live checks

This is **not a claim of complete physical-camera or deployed-network testing**. No personal camera was enabled, no browser camera permission was granted during verification, and no cloud deployment was performed.

| Requested behavior | Completed verification | Live check still needed |
|---|---|---|
| Webcam starts | App startup, transport configuration, disabled-until-live controls | Grant camera permission and confirm the intended device streams |
| Real-time hand detection | Actual model detects public sample images | Raise a hand in a live stream under normal lighting |
| Hand detected indicator | Recognition/telemetry pipeline and browser waiting state | Confirm live HAND DETECTED / IN THE ZONE updates |
| Three gestures | All three recognized by the actual model above threshold | Try all three with the user's hand/camera |
| Stabilized recognition | Frame count, time, invalid input, and duplicate-frame tests | Confirm comfortable response at the device's frame rate |
| Visible countdown | Clock-based phases/numbers and Streamlit controls | Hold each gesture through 3, 2, 1 |
| Complete round | Actual predictions drive SHOOT, RESULT, score, and history | Complete a physical-camera round |
| Independent computer move | Random choice gets all three moves, no player input; sampled once at SHOOT | Observe reveal timing in the live stream |
| Correct winner | All nine combinations tested | — |
| Score updates | One-time scoring, totals, win-rate denominator, control flow | Observe live score refresh |
| History | Last ten records and monotonically increasing round numbers tested | Observe colored live row after a round |
| Play again | Streamlit button tested; score/history retained | Repeat a live round |
| Reset match | Streamlit controls and active-round confirmation tested | — |
| Stop camera | Stop control, stale callback rejection, and stream-ended callback tested | Confirm browser camera indicator turns off and restart works |
| Responsive processing | Locked state/concurrency tests, mirrored frame callback, timed-fragment browser review | Assess live latency and responsiveness on target hardware |

Also test denied permissions, an unplugged camera, another app holding the camera, and a restrictive network. The app keeps game controls safe without valid frames and shows recovery guidance, but a unit test cannot verify the browser/OS-specific dialogs or a provider's TURN configuration. Community Cloud HTTPS, Linux deployment, remote ICE/TURN negotiation, and phone camera permissions remain deployment checks.

## Quick live acceptance pass

1. Run `streamlit run app.py`, enable the camera, and allow camera access.
2. Show one hand, then two hands; confirm only one hand can start a countdown.
3. Try rock, paper, and scissors. Move low or sideways to check the target guidance.
4. Start a countdown, lower your hand, and confirm it cancels without adding a round.
5. Complete three rounds, use Play again, and compare the moves, result, total, and history.
6. Reset during a waiting/countdown phase; use Keep playing once and confirm reset once.
7. Stop the camera, check the browser camera indicator, and re-enable it without losing existing match scores.
8. On the HTTPS deployment, repeat from another network/device; configure TURN if video cannot connect.

The ZIP intentionally excludes downloaded models, caches, virtual environments, and secrets. Its first launch downloads the model automatically.
