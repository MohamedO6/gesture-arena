// Gesture Arena: all video, inference, scoring and rendering stay in this browser.
// Streamlit is only the page host. No video frame is sent to its Python server.
export default function (component) {
  const root = component.parentElement.querySelector('.ga-root');
  if (!root) return;
  const el = (id) => root.querySelector('#ga-' + id);
  const video = el('video');
  const overlay = el('overlay');
  const drawing = overlay.getContext('2d');
  const inferenceCanvas = document.createElement('canvas');
  const inferenceContext = inferenceCanvas.getContext('2d', {willReadFrequently: true});
  const quality = el('quality');
  const cameraBtn = el('camera-btn');
  const startBtn = el('start');
  const cancelBtn = el('cancel');
  const resetBtn = el('reset');
  const emojis = {ROCK:'✊', PAPER:'✋', SCISSORS:'✌️'};
  const labels = {Closed_Fist:'ROCK', Open_Palm:'PAPER', Victory:'SCISSORS'};
  const links = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],
    [5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[13,17],
    [0,17],[17,18],[18,19],[19,20]];
  const zone = {left:.12,top:.08,right:.88,bottom:.87};

  let disposed = false;
  let cameraStream = null;
  let streamToken = 0;
  let model = null;
  let loadModelPromise = null;
  let raf = 0;
  let cameraOn = false;
  let cameraStarting = false;
  let lastInference = 0;
  let lastVideoTime = -1;
  let inferenceCost = 0;
  let inferenceSamples = 0;
  let fpsClock = performance.now();
  let lastOverlay = null;
  let lastDisplay = 0;

  const game = {
    phase: 'IDLE', candidate:null, candidateSince:0, candidateFrames:0,
    chosen:null, countdownStart:0, validAt:0, countdownSeconds:2.1,
    player:0, computer:0, draws:0, history:[],
  };

  function text(id, value) {
    const node = el(id);
    if (node && node.textContent !== String(value)) node.textContent = String(value);
  }
  function message(value, isError=false) {
    text('camera-message', value);
    el('camera-message').classList.toggle('error', isError);
  }
  function setCameraUi(live, status) {
    cameraOn = live;
    el('camera-off').hidden = live;
    el('preview-chip').hidden = !live;
    el('dot').classList.toggle('on', live && !!model);
    text('connection', status);
    text('camera-btn', live || cameraStarting ? 'Stop camera' : 'Enable camera');
  }

  function updateScores() {
    const total = game.player + game.computer + game.draws;
    text('wins', game.player);
    text('losses', game.computer);
    text('draws', game.draws);
    text('rounds', total);
    text('winrate', total ? Math.round(game.player*100/total)+'%' : '0%');
    const history = el('history');
    if (!game.history.length) {
      history.className = 'ga-history-empty';
      history.textContent = 'No rounds yet. Your next win starts here.';
    } else {
      history.className = '';
      history.replaceChildren(...game.history.slice(-10).reverse().map((record) => {
        const row = document.createElement('div');
        row.className = 'ga-history-row';
        const number = document.createElement('span');
        number.textContent = '#' + record.number;
        const yours = document.createElement('span');
        yours.textContent = emojis[record.your] + ' ' + record.your;
        const computer = document.createElement('span');
        computer.textContent = emojis[record.cpu] + ' ' + record.cpu;
        const outcome = document.createElement('strong');
        outcome.textContent = record.outcome;
        outcome.className = record.outcome.toLowerCase();
        row.append(number,yours,computer,outcome);
        return row;
      }));
    }
    try { localStorage.setItem('gesture-arena-local-score-v2', JSON.stringify({
      player:game.player, computer:game.computer, draws:game.draws, history:game.history,
    })); } catch (_) { /* Private mode can deny storage. */ }
  }
  try {
    const saved = JSON.parse(localStorage.getItem('gesture-arena-local-score-v2') || 'null');
    if (saved && Number.isInteger(saved.player) && Number.isInteger(saved.computer)
        && Number.isInteger(saved.draws) && Array.isArray(saved.history)) {
      game.player = Math.max(0,saved.player);
      game.computer = Math.max(0,saved.computer);
      game.draws = Math.max(0,saved.draws);
      game.history = saved.history.slice(-10);
    }
  } catch (_) { /* Keep an empty scoreboard. */ }

  function updatePhase(name, count='READY?', instruction='') {
    game.phase = name;
    text('phase', name.replaceAll('_',' '));
    text('count',count);
    if (instruction) text('instruction',instruction);
    startBtn.disabled = name === 'WAITING' || name === 'COUNTDOWN';
    cancelBtn.disabled = name !== 'WAITING' && name !== 'COUNTDOWN';
    text('start', name === 'RESULT' ? 'Play again' : 'Start round');
  }
  function resetCandidates() {
    game.candidate = null;
    game.candidateSince = 0;
    game.candidateFrames = 0;
    game.chosen = null;
    game.countdownStart = 0;
    game.validAt = 0;
  }
  function startRound() {
    if (game.phase === 'WAITING' || game.phase === 'COUNTDOWN') return;
    if (!cameraOn || !model) {
      message('Enable your camera and wait for hand recognition, or use manual buttons below.',true);
      return;
    }
    resetCandidates();
    text('player-move','❔'); text('cpu-move','🤖');
    text('player-label','YOUR MOVE'); text('cpu-label','HIDDEN');
    updatePhase('WAITING','SHOW YOUR HAND', 'Make Rock, Paper or Scissors in front of the camera. Hold it briefly to start.');
  }
  function cancelRound() {
    if (game.phase === 'WAITING' || game.phase === 'COUNTDOWN') {
      resetCandidates();
      updatePhase('IDLE','READY?','Round cancelled. Press Start round to play again.');
    }
  }
  function randomIndex() {
    if (!globalThis.crypto?.getRandomValues) return Math.floor(Math.random()*3);
    const arr = new Uint32Array(1);
    const limit = 4294967295 - (4294967296 % 3);
    do { crypto.getRandomValues(arr); } while (arr[0] > limit);
    return arr[0] % 3;
  }
  function finishRound(yourMove) {
    if (!emojis[yourMove]) return;
    const cpu = ['ROCK','PAPER','SCISSORS'][randomIndex()];
    const win = (yourMove === 'ROCK' && cpu === 'SCISSORS')
      || (yourMove === 'PAPER' && cpu === 'ROCK')
      || (yourMove === 'SCISSORS' && cpu === 'PAPER');
    const outcome = yourMove === cpu ? 'DRAW' : win ? 'WIN' : 'LOSS';
    if (outcome === 'WIN') game.player++;
    else if (outcome === 'LOSS') game.computer++;
    else game.draws++;
    game.history.push({number:game.player+game.computer+game.draws,your:yourMove,cpu,outcome});
    game.history = game.history.slice(-10);
    text('player-move',emojis[yourMove]); text('cpu-move',emojis[cpu]);
    text('player-label',yourMove); text('cpu-label',cpu);
    const verdict = outcome === 'WIN' ? 'YOU WIN! 🎉' : outcome === 'LOSS' ? 'COMPUTER WINS' : 'IT’S A DRAW';
    updatePhase('RESULT',verdict, 'Your ' + yourMove + ' versus computer ' + cpu + '. Play again!');
    resetCandidates();
    updateScores();
  }
  function manualRound(move) {
    if (!emojis[move]) return;
    // Manual mode is deliberately independent of camera inference.
    finishRound(move);
  }
  function resetScore() {
    cancelRound();
    game.player=0; game.computer=0; game.draws=0; game.history=[];
    text('player-move','✊'); text('cpu-move','🤖');
    text('player-label','YOUR MOVE'); text('cpu-label','HIDDEN');
    updatePhase('IDLE','READY?','Score reset. Enable the camera or use manual controls to play.');
    updateScores();
  }

  function readGesture(result) {
    const hands = result.landmarks || [];
    if (!hands.length) return {move:null,valid:false,hint:'No hand detected — lift one hand into view.',landmarks:[]};
    const points = hands[0];
    const palm = [0,5,9,13,17].map(index => points[index]);
    const x = palm.reduce((sum,p)=>sum+p.x,0) / palm.length;
    const y = palm.reduce((sum,p)=>sum+p.y,0) / palm.length;
    const inside = x >= zone.left && x <= zone.right && y >= zone.top && y <= zone.bottom;
    const clipped = points.some(p=>p.x<.01 || p.x>.99 || p.y<.01 || p.y>.99);
    const category = result.gestures?.[0]?.[0];
    const move = labels[category?.categoryName] || null;
    const confidence = category?.score || 0;
    if (!inside || clipped) return {move,valid:false,landmarks:points,hint:'Move your whole hand toward the center of the camera.'};
    if (!move || confidence < .55) return {move:null,valid:false,landmarks:points,hint:'Try a fist ✊, open palm ✋, or victory sign ✌️.'};
    return {move,valid:true,landmarks:points,hint:'Gesture recognized · '+Math.round(confidence*100)+'% confidence'};
  }

  function drawOverlay(gesture) {
    const w=overlay.width,h=overlay.height;
    drawing.clearRect(0,0,w,h);
    const green=gesture?.valid ? '#3fedac' : '#7ab8ff';
    const corners=[
      [zone.left*w,zone.top*h,1,1],[zone.right*w,zone.top*h,-1,1],
      [zone.left*w,zone.bottom*h,1,-1],[zone.right*w,zone.bottom*h,-1,-1]
    ];
    drawing.lineWidth=3;drawing.strokeStyle=green;drawing.lineCap='round';
    for(const [x,y,dx,dy] of corners) {
      drawing.beginPath();drawing.moveTo(x+dx*31,y);drawing.lineTo(x,y);drawing.lineTo(x,y+dy*31);drawing.stroke();
    }
    if (!gesture?.landmarks?.length) return;
    const p=gesture.landmarks;
    drawing.lineWidth=2.5;
    for(const [a,b] of links) {
      drawing.beginPath();drawing.moveTo(p[a].x*w,p[a].y*h);
      drawing.lineTo(p[b].x*w,p[b].y*h);drawing.stroke();
    }
    drawing.fillStyle='#ffe08b';
    for(const point of p) {drawing.beginPath();drawing.arc(point.x*w,point.y*h,4,0,Math.PI*2);drawing.fill();}
  }
  function showGesture(gesture) {
    lastOverlay=gesture;
    drawOverlay(gesture);
    text('gesture-emoji', gesture.valid ? emojis[gesture.move] : '👋');
    text('gesture-name', gesture.valid ? gesture.move : 'Find your hand');
    text('gesture-help', gesture.hint);
  }
  function observe(gesture, now) {
    if (game.phase !== 'WAITING' && game.phase !== 'COUNTDOWN') return;
    if (gesture.valid) {
      if (game.candidate !== gesture.move) {
        game.candidate = gesture.move;
        game.candidateSince = now;
        game.candidateFrames = 1;
      } else game.candidateFrames++;
    } else {game.candidate=null;game.candidateFrames=0;}

    if (game.phase === 'WAITING' && gesture.valid && game.candidateFrames >= 2
      && now - game.candidateSince >= 140) {
      game.chosen = gesture.move;
      game.countdownStart = now;
      game.validAt = now;
      text('player-move',emojis[gesture.move]);
      text('player-label',gesture.move);
      updatePhase('COUNTDOWN','3','Hold '+gesture.move+' steady until SHOOT!');
    } else if (game.phase === 'COUNTDOWN') {
      if (gesture.valid && gesture.move === game.chosen) game.validAt = now;
      else if (now-game.validAt > 600) {
        resetCandidates();
        text('player-move','❔');
        updatePhase('WAITING','SHOW YOUR HAND','Gesture changed or disappeared. Hold a move to restart.');
      }
    }
  }
  function tick(now) {
    if (game.phase === 'COUNTDOWN') {
      const remaining = game.countdownSeconds*1000 - (now-game.countdownStart);
      if (now-game.validAt > 850) {
        resetCandidates();
        updatePhase('WAITING','SHOW YOUR HAND','Lost hand tracking. Move into the frame and try again.');
      } else if (remaining <= 0) {
        if (now-game.validAt <= 550) finishRound(game.chosen);
        else {resetCandidates();updatePhase('WAITING','SHOW YOUR HAND','Hold your hand steady to play.');}
      } else text('count',String(Math.ceil(remaining / 700)));
    }
  }
  function setInferenceSize() {
    const short=quality.value === 'balanced' ? 320 : 256;
    inferenceCanvas.width=short;
    inferenceCanvas.height=Math.round(short*3/4);
  }
  function streamLoop(now) {
    if (disposed || !cameraOn) return;
    raf=requestAnimationFrame(streamLoop);
    if (!model || video.readyState < 2) return;
    tick(now);
    // Adapt to measured inference time; drop older frames instead of queuing them.
    const minimum = quality.value === 'balanced' ? 67 : 90;
    const cadence = Math.max(minimum, Math.min(240, inferenceCost*2.4));
    if (now-lastInference < cadence || video.currentTime===lastVideoTime) return;
    lastInference=now;
    lastVideoTime=video.currentTime;
    try {
      const before=performance.now();
      inferenceContext.drawImage(video,0,0,inferenceCanvas.width,inferenceCanvas.height);
      const result=model.recognizeForVideo(inferenceCanvas, before);
      const end=performance.now();
      inferenceCost = inferenceCost ? inferenceCost*.8+(end-before)*.2 : end-before;
      inferenceSamples++;
      const gesture=readGesture(result);
      showGesture(gesture);
      observe(gesture,end);
      if(end-fpsClock>=1000) {
        text('fps',String(Math.round(inferenceSamples*1000/(end-fpsClock))));
        inferenceSamples=0;fpsClock=end;
      }
    } catch (e) {
      message('Recognition error: '+String(e?.message||e)+'. You can still play using manual controls.',true);
      console.error('Gesture Arena inference error',e);
      stopCamera();
    }
  }

  async function ensureModel() {
    if (model) return model;
    if (loadModelPromise) return loadModelPromise;
    loadModelPromise=(async()=>{
      const ver='1.2.3';
      const cdn='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@'+ver;
      const {FilesetResolver,GestureRecognizer}=await import(cdn+'/vision_bundle.mjs');
      const vision=await FilesetResolver.forVisionTasks(cdn+'/wasm');
      const modelUrl='https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task';
      const opts=(delegate)=>({
        baseOptions:{modelAssetPath:modelUrl,delegate},
        runningMode:'VIDEO',numHands:1,
        minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5,
      });
      try {return await GestureRecognizer.createFromOptions(vision,opts('GPU'));}
      catch (gpuError) {
        console.warn('GPU unavailable, using CPU MediaPipe',gpuError);
        return await GestureRecognizer.createFromOptions(vision,opts('CPU'));
      }
    })();
    try {
      const created=await loadModelPromise;
      if (disposed) {created.close();return null;}
      model=created;
      return model;
    } finally {loadModelPromise=null;}
  }
  async function enableCamera() {
    if (cameraOn || cameraStarting || disposed) return;
    const token=++streamToken;
    cameraStarting=true;
    text('camera-btn','Stop camera');
    message('Requesting camera permission…');
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraStarting=false;
      message('This browser cannot access the camera here. Use HTTPS or localhost, or manual controls.',true);
      setCameraUi(false,'Camera unavailable');return;
    }
    try {
      const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{
        width:{ideal:640},height:{ideal:480},frameRate:{ideal:30,max:30},facingMode:'user'
      }});
      if (token!==streamToken || disposed) {stream.getTracks().forEach(t=>t.stop());return;}
      cameraStream=stream;
      video.srcObject=stream;
      await video.play();
      if (token!==streamToken || disposed) {stream.getTracks().forEach(t=>t.stop());return;}
      cameraStarting=false;
      setCameraUi(true,'Loading on-device AI…');
      message('Camera preview is live instantly. Downloading recognition model on first use…');
      setInferenceSize();
      raf=requestAnimationFrame(streamLoop);
      const loaded=await ensureModel();
      if (token!==streamToken || disposed || !loaded) return;
      setCameraUi(true,'AI ready · On device');
      message('Ready! Press Start round, then hold ✊, ✋, or ✌️ toward the camera.');
      text('gesture-name','Show your hand');
      fpsClock=performance.now();
    } catch (error) {
      console.error('Gesture Arena camera/model startup error',error);
      if (token!==streamToken || disposed) return;
      const errorName=error?.name||'';
      const hint=errorName==='NotAllowedError' ? 'Allow camera access for this website.' :
        errorName==='NotFoundError' ? 'No camera was found on this device.' :
        'Camera or model failed to start: '+(error?.message||String(error));
      stopCamera();
      message(hint+' Manual controls remain available.',true);
    } finally {
      if (token===streamToken && !disposed) {
        cameraStarting=false;
        text('camera-btn',cameraOn?'Stop camera':'Enable camera');
      }
    }
  }
  function stopCamera() {
    ++streamToken;
    cameraStarting=false;
    cameraOn=false;
    cancelAnimationFrame(raf);
    if (cameraStream) {cameraStream.getTracks().forEach(track=>track.stop());cameraStream=null;}
    video.pause();video.srcObject=null;
    lastInference=0;lastVideoTime=-1;inferenceSamples=0;inferenceCost=0;
    drawOverlay(null);
    text('fps','—');text('gesture-emoji','👋');text('gesture-name','Waiting for camera');
    text('gesture-help','Keep one hand visible and face your palm toward the camera.');
    cancelRound();
    setCameraUi(false,'Camera off');
  }
  function onCameraClick() {
    if (cameraOn || cameraStarting) {stopCamera();message('Camera stopped. No video is being sent or saved.');}
    else enableCamera();
  }
  function onQualityChange() {setInferenceSize();lastInference=0;}
  function onKeydown(event) {
    if (disposed || event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    const move={r:'ROCK',p:'PAPER',s:'SCISSORS'}[event.key?.toLowerCase()];
    if (move) {event.preventDefault();manualRound(move);}
  }
  const manualButtons=[...root.querySelectorAll('[data-move]')];
  const buttonHandlers=manualButtons.map(button=>{
    const fn=()=>manualRound(button.dataset.move);
    button.addEventListener('click',fn);
    return fn;
  });
  cameraBtn.addEventListener('click',onCameraClick);
  startBtn.addEventListener('click',startRound);
  cancelBtn.addEventListener('click',cancelRound);
  resetBtn.addEventListener('click',resetScore);
  quality.addEventListener('change',onQualityChange);
  document.addEventListener('keydown',onKeydown);
  updateScores();setInferenceSize();setCameraUi(false,'Ready to play');
  updatePhase('IDLE','READY?','Enable your camera, press Start round, and show Rock, Paper or Scissors.');

  return () => {
    disposed=true;
    stopCamera();
    if(model) {try{model.close();}catch(_){}}
    cameraBtn.removeEventListener('click',onCameraClick);
    startBtn.removeEventListener('click',startRound);
    cancelBtn.removeEventListener('click',cancelRound);
    resetBtn.removeEventListener('click',resetScore);
    quality.removeEventListener('change',onQualityChange);
    document.removeEventListener('keydown',onKeydown);
    manualButtons.forEach((button,index)=>button.removeEventListener('click',buttonHandlers[index]));
  };
}