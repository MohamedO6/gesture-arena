"""Presentation only. Interactive controls remain native Streamlit widgets."""
from __future__ import annotations

from html import escape

import streamlit as st

from game import GameEngine, Move, Outcome, Phase

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root { --ink:#F8FAFC; --muted:#94A3B8; --blue:#3B82F6; --cyan:#22D3EE; --line:#25334C; }
html, body, [data-testid="stApp"] { font-family:Inter,system-ui,sans-serif; }
[data-testid="stApp"] { background:radial-gradient(ellipse at 80% 0%,#11213b 0%,#080D1A 48%); }
.block-container { max-width:1440px; padding:2.5rem 2.5rem 1rem; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"] { opacity:.4; }
[data-testid="stVerticalBlock"] { gap:.8rem; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:18px; }
.st-key-camera_card, .st-key-arena_card, .st-key-vision_card, .st-key-history_card {
 background:linear-gradient(135deg,#101A2D,#0d1628); border:1px solid var(--line)!important; border-radius:18px;
 padding:22px; overflow:hidden;
}
.st-key-camera_card { padding-bottom:18px; }
.brand { display:flex; align-items:center; gap:14px; margin-bottom:9px; }
.brandmark { width:48px; height:48px; border-radius:14px; display:grid; place-items:center;
 background:linear-gradient(140deg,#3B82F6,#2563eb); color:white; font-size:27px; }
.brand h1 { font-size:30px; letter-spacing:-1.1px; font-weight:900; padding:0; margin:0; line-height:1.1; }
.brand h1 span { color:#60a5fa; }
.subtitle { margin:0 0 20px; color:var(--muted); font-size:14px; }
.eyebrow { font-size:10px; font-weight:700; letter-spacing:2px; color:#7c91b2; margin-bottom:12px; }
.statusbar { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; padding-top:14px; }
.pill { display:inline-flex; align-items:center; gap:7px; border:1px solid var(--line); background:#101A2D;
 border-radius:30px; padding:7px 10px; font-size:10px; font-weight:600; letter-spacing:.4px; color:var(--muted); }
.dot { width:6px; height:6px; border-radius:50%; background:#64748b; }
.pill.good .dot { background:#22C55E; box-shadow:0 0 0 3px #22c55e12; }
.pill.good { color:#b5e8ce; } .pill.cyan .dot { background:var(--cyan); }
.scoreboard { display:grid; grid-template-columns:repeat(5,1fr); border:1px solid var(--line); border-radius:16px;
 background:#101a2dc9; margin-bottom:16px; overflow:hidden; }
.stat { padding:17px 24px; border-right:1px solid var(--line); }
.stat:last-child { border:0; } .stat-label { color:var(--muted); font-size:10px; font-weight:700; letter-spacing:1.2px; }
.stat-value { color:var(--ink); font-size:28px; font-weight:800; margin-top:7px; line-height:1; }
.stat-value.blue { color:#60A5FA; } .stat-value.cyan { color:var(--cyan); }
.stat-value small { font-size:17px; font-weight:600; }
.panel-heading { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:15px; }
.panel-title { font-size:11px; font-weight:800; letter-spacing:1.7px; color:#cbd5e1; }
.micro { font-size:10px; color:#7d90ae; } .live-tag { font-size:9px; color:#7e93b4; letter-spacing:1px; }
.camera-off { height:245px; border-radius:12px; background:linear-gradient(145deg,#14213A,#0a1221);
 border:1px solid #263955; display:flex; justify-content:center; align-items:center; flex-direction:column;
 position:relative; text-align:center; }
.camera-off:before { content:''; position:absolute; width:55%; height:65%; border:1px dashed #3b5074;
 border-radius:24px; opacity:.5; }
.camera-symbol { font-size:44px; opacity:.75; margin-bottom:10px; }
.camera-off strong { font-size:14px; } .camera-off p { font-size:12px; color:var(--muted); margin:7px 20px; }
.tip { display:flex; gap:10px; background:#14213A; color:#bdcce0; font-size:12px; line-height:1.6;
 padding:10px 12px; border-radius:9px; margin-top:3px; }
.tip b { color:var(--cyan); font-weight:600; }
.vision-layout { display:flex; align-items:center; gap:18px; }
.vision-emoji { background:#14213A; border:1px solid #2b3c58; width:80px; height:84px; flex-shrink:0;
 display:grid; place-items:center; border-radius:16px; font-size:43px; }
.vision-name { font-size:21px; font-weight:800; line-height:1.1; margin:4px 0 8px; }
.vision-sub { color:var(--muted); font-size:11px; line-height:1.7; }
.confidence-row { display:flex; justify-content:space-between; margin-top:17px; color:var(--muted); font-size:11px; }
.ready-row { display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px; margin-top:7px; }
.ready-label { font-size:9px; color:#7d90ae; letter-spacing:.8px; } .ready-label.on { color:#22C55E; }
.battle-meta { display:flex; justify-content:space-between; margin-bottom:20px; align-items:center; }
.round-pill { font-size:10px; border:1px solid #2b3b59; background:#14213A; border-radius:6px; padding:6px 9px; color:#a1b6d4; }
.battle { display:grid; grid-template-columns:1fr 42px 1fr; align-items:center; gap:8px; }
.player-card { min-height:188px; border:1px solid #2a4165; border-radius:14px; padding:17px 10px;
 text-align:center; background:linear-gradient(150deg,#162949,#111e35); }
.player-card.computer { background:linear-gradient(150deg,#1c2240,#131c31); border-color:#383c61; }
.player-card.winner { border-color:#22c55e; background:linear-gradient(150deg,#12382e,#111e35); }
.player-card.loser { border-color:#733b49; }
.avatar { font-size:12px; color:#7dd3fc; margin-bottom:10px; } .computer .avatar { color:#b4a9f4; }
.player-name { font-size:10px; letter-spacing:1.2px; font-weight:700; color:#bdcee5; }
.hand { font-family:'Segoe UI Emoji','Apple Color Emoji',sans-serif; font-size:62px; line-height:1.6; }
.move-name { font-size:13px; font-weight:800; letter-spacing:1px; color:#e2e8f0; }
.vs { font-size:16px; color:#6d83a6; font-style:italic; font-weight:900; text-align:center; }
.callout { text-align:center; padding:21px 10px 15px; min-height:130px; }
.callout-title { font-size:26px; font-weight:900; letter-spacing:-.8px; line-height:1.25; }
.callout p { color:var(--muted); font-size:12px; margin:9px 0 0; line-height:1.7; }
.countdown { font-size:62px; line-height:1.1; color:var(--cyan); font-weight:900; animation:pop .3s ease-out; }
.phase-track { display:flex; gap:5px; margin-top:12px; }
.phase-step { height:3px; flex:1; border-radius:10px; background:#24324a; } .phase-step.active { background:#3B82F6; }
.phase-labels { display:flex; justify-content:space-between; font-size:8px; letter-spacing:.6px; color:#6c809f; margin:7px 0 6px; }
.rule-strip { margin:17px 0 0; padding-top:16px; border-top:1px solid var(--line); text-align:center;
 color:#91a6c3; font-size:11px; line-height:1.8; }
.outcome-win { color:#22C55E; } .outcome-loss { color:#EF4444; } .outcome-draw { color:#FACC15; }
.result-pop { animation:pop .35s ease-out; } .sparks { font-size:17px; letter-spacing:12px; color:#FACC15; margin-bottom:4px; }
.history-table { width:100%; border-collapse:collapse; font-size:12px; }
.history-table th { text-align:left; color:#7d91ae; font-weight:500; font-size:10px; letter-spacing:.5px; padding:5px 12px 13px; }
.history-table td { padding:13px 12px; border-top:1px solid #22314a; color:#c8d5e6; }
.history-table .badge { border-radius:5px; padding:4px 9px; font-size:10px; font-weight:700; }
.badge.win { background:#22c55e14; color:#4ade80; } .badge.loss { background:#ef444414; color:#f87171; }
.badge.draw { background:#facc1514; color:#facc15; }
.empty-history { text-align:center; padding:25px 12px; color:#7d91ae; font-size:12px; }
.footer { color:#526683; font-size:10px; text-align:center; margin:26px 0 5px; line-height:1.8; }
[data-testid="stButton"] button { border-radius:10px; min-height:43px; font-size:12px; font-weight:700; letter-spacing:.4px;
 transition:background .15s,border-color .15s,transform .15s; }
[data-testid="stButton"] button:hover:enabled { transform:translateY(-1px); }
[data-testid="stButton"] button[kind="primary"] { background:linear-gradient(110deg,#3B82F6,#2563eb); border:1px solid #60a5fa50; }
[data-testid="stProgress"] > div > div > div { background:linear-gradient(90deg,#3B82F6,#22D3EE); }
[data-testid="stExpander"] { border-color:#25334C; border-radius:10px; }
[data-testid="stExpander"] summary { font-size:11px; color:#94A3B8; }
@keyframes pop { from { opacity:.5; transform:scale(.93); } to { opacity:1; transform:scale(1); } }
@media(max-width:800px) {
 .block-container { padding:1.5rem 1rem; } .brand h1 { font-size:26px; } .statusbar { justify-content:flex-start; padding-top:0; }
 .stat { padding:14px 10px; } .stat-label { font-size:8px; letter-spacing:.3px; } .stat-value { font-size:23px; }
 .st-key-camera_card, .st-key-arena_card, .st-key-vision_card, .st-key-history_card { padding:16px; }
 .hand { font-size:52px; } .player-card { min-height:170px; } .callout-title { font-size:23px; }
}
@media(max-width:420px) { .stat-value { font-size:20px; } .stat-label { font-size:7px; } .battle { gap:4px; grid-template-columns:1fr 30px 1fr; } }
@media(prefers-reduced-motion:reduce) { *, *:before, *:after { animation:none!important; transition:none!important; } }
</style>
"""


def install_styles(camera_requested: bool = False) -> None:
    st.html(CSS)
    if not camera_requested:
        # Preserve the mounted transport while hiding its empty native preview.
        st.html('<style>.st-key-camera_feed { display:none; }</style>')


def panel_heading(title: str, detail: str = "") -> None:
    st.html(f'<div class="panel-heading"><span class="panel-title">{escape(title)}</span>'
            f'<span class="micro">{escape(detail)}</span></div>')


def header() -> None:
    st.html('<div class="eyebrow">THE HANDS-ON ARCADE</div><div class="brand">'
            '<div class="brandmark">✌</div><h1>GESTURE <span>ARENA</span></h1></div>'
            '<p class="subtitle">Your hands. Your moves. Challenge the AI.</p>')


def status(model_ready: bool, camera_live: bool) -> None:
    def pill(label: str, ready: bool) -> str:
        return f'<span class="pill {"good" if ready else ""}"><i class="dot"></i>{label}</span>'
    st.html('<div class="statusbar">' + pill('MODEL READY' if model_ready else 'MODEL OFFLINE', model_ready)
            + pill('CAMERA LIVE' if camera_live else 'CAMERA OFF', camera_live) + '</div>')


def scoreboard(game: GameEngine) -> None:
    values = [('YOUR WINS', str(game.score.player), 'blue'), ('COMPUTER WINS', str(game.score.computer), ''),
              ('DRAWS', str(game.score.draws), ''), ('ROUNDS PLAYED', str(game.score.total), ''),
              ('YOUR WIN RATE', f'{game.score.win_rate:.0f}<small>%</small>', 'cyan')]
    st.html('<div class="scoreboard">' + ''.join(
        f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value {color}">{value}</div></div>'
        for label, value, color in values) + '</div>')


def camera_placeholder() -> None:
    st.html('<div class="camera-off"><div class="camera-symbol">✋</div><strong>Your hand is the controller.</strong>'
            '<p>Enable your camera. Step into the arena.</p></div>')


def vision_panel(game: GameEngine, now: float, camera_live: bool) -> None:
    observation = game.fresh_observation(now) if camera_live else None
    move = observation.move if observation and observation.hand_count == 1 else None
    confidence = max(0.0, min(1.0, observation.confidence)) if move else 0.0
    stable = game.stabilizer.stable is not None and camera_live
    hand = observation is not None and observation.hand_count > 0
    ready = bool(observation and observation.hand_count == 1 and observation.in_zone)
    panel_heading('AI VISION', 'LIVE RECOGNITION')
    name = move.value if move else ('SHOW ONE HAND' if hand else 'WAITING FOR YOU')
    detail = 'Gesture locked in · keep it steady' if stable else ('Hold a clear gesture to lock it in' if hand else 'Waiting for your hand...')
    st.html(f'<div class="vision-layout"><div class="vision-emoji">{move.emoji if move else "✋"}</div>'
            f'<div><div class="eyebrow" style="margin:0">{"STABLE GESTURE" if stable else "YOUR NEXT MOVE"}</div>'
            f'<div class="vision-name">{name}</div><div class="vision-sub">{detail}</div></div></div>'
            f'<div class="confidence-row"><span>Recognition confidence</span><strong>{confidence:.0%}</strong></div>')
    st.progress(confidence)
    st.html(f'<div class="ready-row"><span class="ready-label {"on" if hand else ""}">'
            f'● {"HAND DETECTED" if hand else "NO HAND DETECTED"}</span>'
            f'<span class="ready-label {"on" if ready else ""}">{"✓ IN THE ZONE" if ready else "○ HAND NOT READY"}</span></div>')
    message = game.feedback(now) if camera_live else 'Enable the camera to join the arena.'
    st.html(f'<div class="tip"><b>↗</b><span>{escape(message)}</span></div>')


def battle_panel(game: GameEngine, now: float, camera_live: bool) -> None:
    round_number = game.last_round.number if game.last_round else game.score.total + 1
    panel_heading('YOU VS COMPUTER', 'FAIR PLAY · RANDOM OPPONENT')
    phase_label = {Phase.IDLE: 'READY WHEN YOU ARE', Phase.WAITING_FOR_HAND: 'FIND YOUR MOVE',
                   Phase.COUNTDOWN: 'HOLD STEADY', Phase.SHOOT: 'MOVES LOCKED', Phase.RESULT: 'ROUND COMPLETE'}[game.phase]
    st.html(f'<div class="battle-meta"><span class="round-pill">ROUND {round_number:02d}</span>'
            f'<span class="live-tag">{phase_label}</span></div>')
    player: Move | None = None
    computer: Move | None = None
    player_class = computer_class = ''
    if game.phase == Phase.RESULT and game.last_round:
        player, computer = game.last_round.player, game.last_round.computer
        if game.last_round.outcome == Outcome.WIN:
            player_class, computer_class = 'winner', 'loser'
        elif game.last_round.outcome == Outcome.LOSS:
            player_class, computer_class = 'loser', 'winner'
    elif game.phase in {Phase.COUNTDOWN, Phase.SHOOT}:
        player = game.countdown_move
    elif game.phase == Phase.WAITING_FOR_HAND:
        player = game.stabilizer.stable

    def card(name: str, avatar: str, move: Move | None, classes: str, pending: str) -> str:
        return (f'<div class="player-card {classes}"><div class="avatar">{avatar}</div><div class="player-name">{name}</div>'
                f'<div class="hand">{move.emoji if move else "❔"}</div>'
                f'<div class="move-name">{move.value if move else pending}</div></div>')

    st.html('<div class="battle">' + card('YOU', '◉ PLAYER 01', player, player_class, 'YOUR MOVE')
            + '<div class="vs">VS</div>' + card('AI COMPUTER', '▣ THE CHALLENGER', computer,
                                               'computer ' + computer_class, 'HIDDEN') + '</div>')
    title, detail, tone = 'Make your move.', 'Three gestures. One showdown. Ready to play?', ''
    if not camera_live and game.phase == Phase.IDLE:
        detail = 'Enable your camera, then start your first round.'
    if game.phase == Phase.WAITING_FOR_HAND:
        title, detail = 'Raise your hand to start!', 'Choose ✊ rock, ✋ paper, or ✌️ scissors. Hold it inside the zone.'
    elif game.phase == Phase.COUNTDOWN:
        title = f'<div class="countdown">{game.countdown_number(now)}</div>'
        detail = f'{player.emoji if player else ""} {player.value if player else ""} DETECTED! Hold your gesture.'
    elif game.phase == Phase.SHOOT:
        title, detail, tone = 'SHOOT!', 'Your move is locked. Here comes the reveal…', 'outcome-draw'
    elif game.phase == Phase.RESULT and game.last_round:
        outcome = game.last_round.outcome
        title, detail, tone = {
            Outcome.WIN: ('YOU WIN!', 'A winning hand. Keep the momentum going.', 'outcome-win'),
            Outcome.LOSS: ('COMPUTER WINS!', 'Next round is yours. Take a breath and try again.', 'outcome-loss'),
            Outcome.DRAW: ("IT’S A DRAW!", 'Great minds, same move. Time for a rematch.', 'outcome-draw'),
        }[outcome]
    sparks = '<div class="sparks" aria-hidden="true">✦ ✧ ✦</div>' if tone == 'outcome-win' else ''
    st.html(f'<div class="callout"><div class="callout-title {tone} result-pop">{sparks}{title}</div>'
            f'<p>{escape(detail)}</p></div>')
    index = {Phase.IDLE: -1, Phase.WAITING_FOR_HAND: 0, Phase.COUNTDOWN: 1, Phase.SHOOT: 2, Phase.RESULT: 3}[game.phase]
    st.html('<div class="phase-track">' + ''.join(f'<div class="phase-step {"active" if i <= index else ""}"></div>' for i in range(4))
            + '</div><div class="phase-labels"><span>GET READY</span><span>HOLD</span><span>SHOOT</span><span>REVEAL</span></div>')


def history_panel(game: GameEngine) -> None:
    panel_heading('MATCH HISTORY', 'LAST 10 ROUNDS · NEWEST FIRST')
    if not game.history:
        st.html('<div class="empty-history">Every rivalry starts somewhere. Your first round goes here.</div>')
        return
    rows = ''.join(f'<tr><td>#{r.number:02d}</td><td>{r.player.emoji} {r.player.value.title()}</td>'
                   f'<td>{r.computer.emoji} {r.computer.value.title()}</td><td><span class="badge {r.outcome.value.lower()}">'
                   f'{r.outcome.value}</span></td></tr>' for r in reversed(game.history))
    st.html('<div style="overflow-x:auto"><table class="history-table"><thead><tr>'
            '<th>ROUND</th><th>YOU</th><th>COMPUTER</th><th>RESULT</th></tr></thead><tbody>' + rows + '</tbody></table></div>')
