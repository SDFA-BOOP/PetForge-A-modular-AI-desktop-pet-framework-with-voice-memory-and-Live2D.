(() => {
  const MODEL_URL = 'model/192549kQzMyJqkgeAeZQyT.model3.json';
  const canvas = document.getElementById('stage');
  const video = document.getElementById('camera');
  const status = document.getElementById('status');
  const characterBubble = document.getElementById('character-bubble');
  const cameraPanel = document.getElementById('camera-panel');
  const darkToggle = document.getElementById('dark-toggle');
  const amplitudeInput = document.getElementById('amplitude');
  const amplitudeValue = document.getElementById('amplitude-value');
  const orientationBadge = document.getElementById('orientation-badge');
  const modePortraitButton = document.getElementById('mode-portrait');
  const modeLandscapeButton = document.getElementById('mode-landscape');
  const modeValue = document.getElementById('mode-value');
  const motionPage = document.getElementById('motion-page');
  const motionOpen = document.getElementById('motion-open');
  const motionClose = document.getElementById('motion-close');
  const motionAmplitudeInput = document.getElementById('motion-amplitude');
  const motionAmplitudeValue = document.getElementById('motion-amplitude-value');
  const motionSpeedInput = document.getElementById('motion-speed');
  const motionSpeedValue = document.getElementById('motion-speed-value');
  const motionFollowInput = document.getElementById('motion-follow');
  const motionFollowValue = document.getElementById('motion-follow-value');
  const motionIdleInput = document.getElementById('motion-idle');
  const motionIdleValue = document.getElementById('motion-idle-value');
  const motionBreathInput = document.getElementById('motion-breath');
  const motionBreathValue = document.getElementById('motion-breath-value');
  const motionReset = document.getElementById('motion-reset');
  const characterScaleInput = document.getElementById('character-scale');
  const characterScaleValue = document.getElementById('character-scale-value');
  const characterXInput = document.getElementById('character-x');
  const characterXValue = document.getElementById('character-x-value');
  const characterYInput = document.getElementById('character-y');
  const characterYValue = document.getElementById('character-y-value');
  const orientationPage = document.getElementById('orientation-page');
  const orientationOpen = document.getElementById('orientation-open');
  const orientationClose = document.getElementById('orientation-close');
  const chatOpen = document.getElementById('chat-open');
  const chatClose = document.getElementById('chat-close');
  const chatPanel = document.getElementById('chat-panel');
  const chatMessages = document.getElementById('chat-messages');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatSend = document.getElementById('chat-send');
  const chatMic = document.getElementById('chat-mic');
  const chatCamera = document.getElementById('chat-camera');
  const photoCaptionDialog = document.getElementById('photo-caption-dialog');
  const photoCaptionImage = document.getElementById('photo-caption-image');
  const photoCaptionInput = document.getElementById('photo-caption-input');
  const photoCaptionSend = document.getElementById('photo-caption-send');
  const photoCaptionSkip = document.getElementById('photo-caption-skip');
  const chatVoice = document.getElementById('chat-voice');
  const chatMicAlways = document.getElementById('chat-mic-always');
  const micMeter = document.getElementById('mic-meter');
  const micMeterFill = document.getElementById('mic-meter-fill');
  const chatStatus = document.getElementById('chat-status');
  const bridgeUrlInput = document.getElementById('bridge-url');
  const bridgeStatus = document.getElementById('bridge-status');
  const bridgeTest = document.getElementById('bridge-test');
  const directModeToggle = document.getElementById('direct-mode');
  const apiKeyInput = document.getElementById('api-key');
  const apiKeyPaste = document.getElementById('api-key-paste');
  const apiBaseInput = document.getElementById('api-base');
  const apiModelInput = document.getElementById('api-model');
  const visionModelInput = document.getElementById('vision-model');
  const localVoiceToggle = document.getElementById('local-voice');
  const voiceOpen = document.getElementById('voice-open');
  const voiceClose = document.getElementById('voice-close');
  const voicePage = document.getElementById('voice-page');
  const voiceSpeedInput = document.getElementById('voice-speed');
  const voiceSpeedValue = document.getElementById('voice-speed-value');
  const voiceVolumeInput = document.getElementById('voice-volume');
  const voiceVolumeValue = document.getElementById('voice-volume-value');
  const voicePitchInput = document.getElementById('voice-pitch');
  const voicePitchValue = document.getElementById('voice-pitch-value');
  const voiceDeelectInput = document.getElementById('voice-deelect');
  const voiceDeelectValue = document.getElementById('voice-deelect-value');
  const voiceReset = document.getElementById('voice-reset');
  const gsvStatus = document.getElementById('gsv-status');
  const memoryClear = document.getElementById('memory-clear');
  const ttsProgress = document.getElementById('tts-progress');
  const ttsProgressText = document.getElementById('tts-progress-text');
  const ttsProgressFill = document.getElementById('tts-progress-fill');

  let app = null;
  let model = null;
  let modelBaseWidth = 1;
  let modelBaseHeight = 1;
  let coreModel = null;
  let classifier = null;
  let videoCapture = null;
  let faceTargetX = 0;
  let faceTargetY = 0;
  let faceX = 0;
  let faceY = 0;
  let faceVisible = false;
  let faceRawX = 0.5;
  let faceRawY = 0.5;
  let faceSeen = false;
  let faceMissFrames = 0;
  let lastStatusHide = 0;
  let openCvWorker = null;
  let openCvWorkerBusy = false;
  let animationAmplitude = 1;
  let darkMode = false;
  let displayMode = 'portrait';
  let motionSpeed = 1;
  let followStrength = 1;
  let idleAmplitude = 1;
  let breathAmplitude = 1;
  let characterScale = 1;
  let characterX = 0;
  let characterY = 0;
  let transformFrame = 0;
  let bridgeUrl = '';
  let chatBusy = false;
  let voiceAudio = null;
  let bubbleHideTimer = 0;
  let speechRecognition = null;
  let speechActive = false;
  let micAlwaysOn = false;
  let voiceAudioContext = null;
  let voiceMouthSource = null;
  let voiceMouthAnalyser = null;
  let voiceIsTalking = false;
  let voiceMouthLevel = 0;
  let voiceMouthPeak = 0;
  let nativeTtsSpeaking = false;
  let directMode = false;
  let apiKey = '';
  let apiBase = 'https://api.deepseek.com';
  let apiModel = 'deepseek-chat';
  let visionModel = 'deepseek-v4-flash-vision-exp';
  let localVoiceEnabled = true;
  let voiceSpeed = 1;
  let voiceVolume = 1;
  let voicePitch = 0;
  let voiceDeelect = 0;
  let directHistory = [];
  let memorySummary = '';
  let msgLog = [];
  let journal = {};
  let memoryMeta = {};
  const pendingApiRequests = {};
  let activeCameraStream = null;
  let pendingPhotoUrl = null;
  const DEFAULT_BRIDGE_URL = 'http://192.168.1.50:8765';

  window.addEventListener('error', (event) => {
    setStatus('运行错误：' + (event.message || '未知错误'));
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    setStatus('运行错误：' + (reason && reason.message ? reason.message : reason));
  });

  function setStatus(text, hideAfterMs = 0) {
    status.textContent = text;
    status.style.opacity = '1';
    if (hideAfterMs > 0) {
      lastStatusHide = Date.now() + hideAfterMs;
      window.setTimeout(() => {
        if (Date.now() >= lastStatusHide) status.style.opacity = '0';
      }, hideAfterMs);
    }
  }

  function readStored(key) {
    try { return window.localStorage.getItem(key); } catch (_) { return null; }
  }

  function storeValue(key, value) {
    try { window.localStorage.setItem(key, String(value)); } catch (_) {}
  }

  function getDeviceId() {
    let id = readStored('rikka.deviceId');
    if (!id) {
      id = 'ph-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
      storeValue('rikka.deviceId', id);
    }
    return id;
  }

  function persistHistory() {
    try { storeValue('rikka.history', JSON.stringify(directHistory)); } catch (_) {}
  }

  function saveMsgLog() { try { storeValue('rikka.msglog', JSON.stringify(msgLog)); } catch (_) {} }
  function saveJournal() { try { storeValue('rikka.journal', JSON.stringify(journal)); } catch (_) {} }
  function saveMemoryMeta() { try { storeValue('rikka.meta', JSON.stringify(memoryMeta)); } catch (_) {} }

  function appendMessage(role, content) {
    const m = { role, content, ts: Date.now() };
    msgLog.push(m);
    if (msgLog.length > 4000) msgLog = msgLog.slice(-4000);
    directHistory.push({ role, content });
    directHistory = directHistory.slice(-20);
    saveMsgLog();
    persistHistory();
  }

  function dateKey(ts) {
    const d = new Date(ts);
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + mm + '-' + dd;
  }
  function todayKey() { return dateKey(Date.now()); }

  const JOURNAL_PROMPT = '请把 {date} 的这段对话整理成一条记忆日志（用中文 3~6 句），记录：1) 聊了什么主题；2) 关于勇太（用户）的重要信息——喜好、状态、烦恼、提到的计划等；3) 你们互动的情况。只输出日志正文，不要解释、不要日期前缀。\n\n对话：\n{history}';

  const CONSOLIDATE_PROMPT = '下面是已有的长期记忆概括和一批超过30天的旧记忆日志，请合并成一段新的长期记忆概括（保留所有重要信息，用中文、尽量简洁）。只输出合并后的概括。\n\n已有长期记忆概括：\n{old_summary}\n\n旧记忆日志：\n{logs}';

  async function summarize(prompt) {
    return (await callNativeApi([{ role: 'user', content: prompt }])).trim();
  }

  async function maybeConsolidate() {
    const cutoff = dateKey(Date.now() - 30 * 86400000);
    const old = [];
    for (const d of Object.keys(journal).sort()) {
      if (d < cutoff) old.push(d + '：' + journal[d]);
    }
    if (!old.length) return;
    try {
      const merged = await summarize(CONSOLIDATE_PROMPT
        .replace('{old_summary}', memorySummary || '（暂无）')
        .replace('{logs}', old.join('\n')));
      if (merged) {
        memorySummary = merged.slice(0, 1200);
        storeValue('rikka.memory', memorySummary);
        for (const d of Object.keys(journal)) if (d < cutoff) delete journal[d];
        saveJournal();
      }
    } catch (_) {}
  }

  function pruneMsgLog() {
    const cutoff = Date.now() - 32 * 86400000;
    const before = msgLog.length;
    msgLog = msgLog.filter((m) => m.ts >= cutoff);
    if (msgLog.length !== before) saveMsgLog();
  }

  async function runDailyMaintenance() {
    if (!apiKey) return;
    const today = todayKey();
    if (memoryMeta.lastDaily === today) { await maybeConsolidate(); return; }
    memoryMeta.lastDaily = today;
    saveMemoryMeta();
    try {
      const byDay = {};
      for (const m of msgLog) {
        const d = dateKey(m.ts);
        if (d === today) continue;
        (byDay[d] = byDay[d] || []).push(m);
      }
      const days = Object.keys(byDay).sort();
      let done = 0;
      for (const d of days) {
        if (done >= 8) break;
        if (journal[d]) continue;
        const history = byDay[d]
          .map((m) => (m.role === 'user' ? '勇太：' : '六花：') + m.content)
          .join('\n')
          .slice(-6000);
        try {
          const content = await summarize(JOURNAL_PROMPT.replace('{date}', d).replace('{history}', history));
          if (content) { journal[d] = content; saveJournal(); }
        } catch (_) {}
        done++;
      }
      await maybeConsolidate();
      pruneMsgLog();
    } catch (_) {}
  }

  function applyDarkMode(enabled) {
    darkMode = !!enabled;
    document.body.classList.toggle('dark', darkMode);
    if (darkToggle) darkToggle.checked = darkMode;
    storeValue('rikka.dark', darkMode ? '1' : '0');
  }

  function clampNumber(value, minimum, maximum, fallback) {
    const parsed = Number(value);
    const safe = Number.isFinite(parsed) ? parsed : fallback;
    return Math.max(minimum, Math.min(maximum, safe));
  }

  function updateAmplitude(value) {
    animationAmplitude = clampNumber(value, 0.2, 2, 1);
    if (amplitudeInput) amplitudeInput.value = String(animationAmplitude);
    if (amplitudeValue) amplitudeValue.textContent = animationAmplitude.toFixed(2) + '×';
    if (motionAmplitudeInput) motionAmplitudeInput.value = String(animationAmplitude);
    if (motionAmplitudeValue) motionAmplitudeValue.textContent = animationAmplitude.toFixed(2) + '×';
    storeValue('rikka.amplitude', animationAmplitude.toFixed(2));
  }

  function updateMotionSpeed(value) {
    motionSpeed = clampNumber(value, 0.2, 2.5, 1);
    if (motionSpeedInput) motionSpeedInput.value = String(motionSpeed);
    if (motionSpeedValue) motionSpeedValue.textContent = motionSpeed.toFixed(2) + '×';
    storeValue('rikka.motionSpeed', motionSpeed.toFixed(2));
  }

  function updateFollowStrength(value) {
    followStrength = clampNumber(value, 0, 2, 1);
    if (motionFollowInput) motionFollowInput.value = String(followStrength);
    if (motionFollowValue) motionFollowValue.textContent = followStrength.toFixed(2) + '×';
    storeValue('rikka.followStrength', followStrength.toFixed(2));
  }

  function updateIdleAmplitude(value) {
    idleAmplitude = clampNumber(value, 0, 2, 1);
    if (motionIdleInput) motionIdleInput.value = String(idleAmplitude);
    if (motionIdleValue) motionIdleValue.textContent = idleAmplitude.toFixed(2) + '×';
    storeValue('rikka.idleAmplitude', idleAmplitude.toFixed(2));
  }

  function updateBreathAmplitude(value) {
    breathAmplitude = clampNumber(value, 0, 2, 1);
    if (motionBreathInput) motionBreathInput.value = String(breathAmplitude);
    if (motionBreathValue) motionBreathValue.textContent = breathAmplitude.toFixed(2) + '×';
    storeValue('rikka.breathAmplitude', breathAmplitude.toFixed(2));
  }

  function updateCharacterScale(value) {
    characterScale = clampNumber(value, 0.55, 1.65, 1);
    if (characterScaleInput) characterScaleInput.value = String(characterScale);
    if (characterScaleValue) characterScaleValue.textContent = characterScale.toFixed(2) + '×';
    storeValue('rikka.characterScale', characterScale.toFixed(2));
    scheduleModelTransform();
  }

  function updateCharacterX(value) {
    characterX = clampNumber(value, -0.35, 0.35, 0);
    if (characterXInput) characterXInput.value = String(characterX);
    if (characterXValue) characterXValue.textContent = characterX.toFixed(2);
    storeValue('rikka.characterX', characterX.toFixed(2));
    scheduleModelTransform();
  }

  function updateCharacterY(value) {
    characterY = clampNumber(value, -0.35, 0.35, 0);
    if (characterYInput) characterYInput.value = String(characterY);
    if (characterYValue) characterYValue.textContent = characterY.toFixed(2);
    storeValue('rikka.characterY', characterY.toFixed(2));
    scheduleModelTransform();
  }
  function setOrientationPageOpen(open) {
    if (!orientationPage) return;
    orientationPage.hidden = !open;
    if (open) {
      if (motionPage) motionPage.hidden = true;
    } else if (motionPage) {
      motionPage.hidden = false;
    }
  }
  function setMotionPageOpen(open) {
    if (!motionPage) return;
    motionPage.hidden = !open;
  }

  function resetMotionSettings() {
    applyDarkMode(false);
    applyDisplayMode('portrait');
    updateCharacterScale(1);
    updateCharacterX(0);
    updateCharacterY(0);
    updateAmplitude(1);
    updateMotionSpeed(1);
    updateFollowStrength(1);
    updateIdleAmplitude(1);
    updateBreathAmplitude(1);
  }

  function applyDisplayMode(mode) {
    displayMode = mode === 'landscape' ? 'landscape' : 'portrait';
    const bigHead = displayMode === 'landscape';
    document.body.classList.toggle('landscape-mode', bigHead);
    if (modePortraitButton) modePortraitButton.classList.toggle('active', !bigHead);
    if (modeLandscapeButton) modeLandscapeButton.classList.toggle('active', bigHead);
    if (modeValue) modeValue.textContent = bigHead ? '横屏 · 大头' : '竖屏 · 全身';
    storeValue('rikka.displayMode', displayMode);
    if (window.NativeFaceBridge && typeof window.NativeFaceBridge.setOrientation === 'function') {
      try { window.NativeFaceBridge.setOrientation(bigHead ? 'landscape' : 'portrait'); } catch (_) {}
    }
    refreshLayoutSoon();
  }
  function normalizeBridgeUrl(value) {
    let url = String(value || '').trim();
    if (!url) return '';
    if (!/^https?:\/\//i.test(url)) url = 'http://' + url;
    return url.replace(/\/+$/, '');
  }

  function setBridgeState(text, ok) {
    if (bridgeStatus) bridgeStatus.textContent = text;
    if (chatStatus) chatStatus.textContent = text;
    if (bridgeStatus) bridgeStatus.style.color = ok ? '#34d399' : '';
  }

  function showCharacterBubble(text, durationMs) {
    if (!characterBubble || !text) return;
    characterBubble.textContent = text;
    characterBubble.hidden = false;
    if (bubbleHideTimer) {
      window.clearTimeout(bubbleHideTimer);
      bubbleHideTimer = 0;
    }
    bubbleHideTimer = window.setTimeout(() => {
      characterBubble.hidden = true;
    }, durationMs || 7000);
  }
  function appendChatBubble(text, role) {
    if (!chatMessages) return;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + (role || 'system');
    bubble.textContent = text;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function restoreChatHistory() {
    if (!chatMessages || !msgLog || !msgLog.length) return;
    chatMessages.innerHTML = '';
    const recent = msgLog.slice(-20);
    for (const m of recent) {
      appendChatBubble(m.content, m.role || 'user');
    }
  }

  async function fetchJson(url, options, timeoutMs) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs || 180000);
    try {
      const response = await fetch(url, Object.assign({}, options || {}, { signal: controller.signal }));
      const text = await response.text();
      let data = {};
      if (text) {
        try { data = JSON.parse(text); } catch (_) { data = { error: text }; }
      }
      if (!response.ok) throw new Error(data.error || ('HTTP ' + response.status));
      return data;
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error('请求超时');
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function detachMouthAnalyser() {
    if (voiceMouthSource) {
      try { voiceMouthSource.disconnect(); } catch (_) {}
      voiceMouthSource = null;
    }
    voiceMouthAnalyser = null;
    voiceIsTalking = false;
    voiceMouthLevel = 0;
    voiceMouthPeak = 0;
  }

  function attachMouthAnalyser(audio) {
    detachMouthAnalyser();
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      if (!voiceAudioContext) voiceAudioContext = new AudioContextClass();
      if (voiceAudioContext.state === 'suspended') voiceAudioContext.resume();
      voiceMouthSource = voiceAudioContext.createMediaElementSource(audio);
      voiceMouthAnalyser = voiceAudioContext.createAnalyser();
      voiceMouthAnalyser.fftSize = 256;
      voiceMouthSource.connect(voiceMouthAnalyser);
      voiceMouthAnalyser.connect(voiceAudioContext.destination);
      voiceIsTalking = true;
    } catch (error) {
      console.warn('嘴型分析初始化失败', error);
    }
  }

  function playChatAudio(data) {
    let objectUrl = null;
    try {
      detachMouthAnalyser();
      if (voiceAudio) {
        voiceAudio.pause();
        voiceAudio = null;
      }
      let url = '';
      if (data && data.audio_base64) {
        const blob = new Blob([base64ToBytes(data.audio_base64)], {
          type: data.audio_mime || 'audio/mpeg',
        });
        objectUrl = URL.createObjectURL(blob);
        url = objectUrl;
      } else if (data && data.audio_url) {
        url = new URL(data.audio_url, bridgeUrl + '/').href;
      }
      if (!url) return;
      voiceAudio = new Audio(url);
      voiceAudio.onended = () => {
        detachMouthAnalyser();
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      };
      attachMouthAnalyser(voiceAudio);
      voiceAudio.play().catch((error) => {
        detachMouthAnalyser();
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        appendChatBubble('语音播放失败：' + (error.message || error), 'system');
      });
    } catch (error) {
      detachMouthAnalyser();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      appendChatBubble('语音播放失败：' + (error.message || error), 'system');
    }
  }
  async function syncMemoryToBridge() {
    const base = normalizeBridgeUrl(bridgeUrlInput ? bridgeUrlInput.value : bridgeUrl);
    if (!base) return false;
    try {
      const result = await fetchJson(base + '/memory/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({
          device_id: getDeviceId(),
          messages: msgLog,
          journal: journal,
          summary: memorySummary,
          synced_at: new Date().toISOString(),
        }),
      }, 30000);
      if (result && result.ok) {
        console.log('[memory] synced to bridge:', result.synced_at, 'messages:', result.message_count);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }
  async function testBridgeConnection() {
    const base = normalizeBridgeUrl(bridgeUrlInput ? bridgeUrlInput.value : bridgeUrl);
    if (!base) {
      setBridgeState('请先填写电脑地址', false);
      return;
    }
    bridgeUrl = base;
    storeValue('rikka.bridgeUrl', bridgeUrl);
    if (bridgeUrlInput) bridgeUrlInput.value = bridgeUrl;
    setBridgeState('正在测试…', false);
    try {
      const data = await fetchJson(bridgeUrl + '/health', { method: 'GET' }, 6000);
      const backend = data.effective_tts === 'gpt_sovits' ? 'GPT-SoVITS' : 'Edge TTS';
      setBridgeState('已连接 · ' + backend, true);
      syncMemoryToBridge();
    } catch (error) {
      setBridgeState('连接失败：' + (error.message || error), false);
    }
  }

  async function sendChatMessage(event) {
    if (event) event.preventDefault();
    if (!chatInput) return;
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    await postChat(text, text);
  }

  const DIRECT_SYSTEM_PROMPT = [
    '你是小鸟游六花，动画《中二病也要谈恋爱！》的女主角，正通过手机陪伴勇太。',
    '用中文回复，保持中二、可爱、简洁的少女语气。',
    '每次回复 1~3 句，只输出可以直接朗读的台词，不要动作描写、旁白或括号内容。',
    '可以偶尔使用邪王真眼、不可视境界线、契约者等设定，但保持自然。',
    '【称呼规则】把用户视为「勇太」（富樫勇太），他是你最重要的「契约者」与「暗焰魔导师」。',
    '自称用「我」，称呼对方一律直接叫「勇太」，偶尔可叫「契约者」「暗焰魔导师」；不要用「吾」「汝」等古文词，也不要过度傲娇。',
  ].join('\n');

  const TRANSLATE_TO_JA_PROMPT = [
    '你是日语翻译，把中文台词翻译成自然口语化的日语，用于日语语音合成。',
    '要求：',
    '1) 全程只用日语，不要夹带中文；',
    '2) 称呼用户为「勇太」（富樫勇太），自称用「私」，保持少女可爱的语气；',
    '3) 只输出日语台词本身，不要解释、不要动作描写、不要括号。',
  ].join('\n');

  function callNativeApi(messages, modelOverride) {
    return new Promise((resolve, reject) => {
      if (!window.NativeApi || typeof window.NativeApi.chat !== 'function') {
        reject(new Error('当前设备不支持手机直连 API'));
        return;
      }
      const requestId = 'api-' + Date.now() + '-' + Math.random().toString(16).slice(2);
      const timer = window.setTimeout(() => {
        delete pendingApiRequests[requestId];
        reject(new Error('API 请求超时'));
      }, 150000);
      pendingApiRequests[requestId] = { resolve, reject, timer };
      window.NativeApi.chat(JSON.stringify({
        requestId: requestId,
        apiKey: apiKey,
        baseUrl: apiBase,
        model: modelOverride || apiModel,
        messages: messages,
      }));
    });
  }

  window.onNativeApiResult = (requestId, resultJson) => {
    const pending = pendingApiRequests[requestId];
    if (!pending) return;
    window.clearTimeout(pending.timer);
    delete pendingApiRequests[requestId];
    try {
      const result = JSON.parse(resultJson || '{}');
      if (result.ok) pending.resolve(result.reply || '');
      else pending.reject(new Error(result.error || 'API 请求失败'));
    } catch (error) {
      pending.reject(error);
    }
  };

  function showTtsProgress(text, percent) {
    if (ttsProgress) ttsProgress.hidden = false;
    if (ttsProgressText) ttsProgressText.textContent = text || '配音中…';
    if (typeof percent === 'number' && ttsProgressFill) {
      ttsProgressFill.style.width = Math.max(0, Math.min(100, percent)) + '%';
    }
  }

  function hideTtsProgress() {
    if (ttsProgress) ttsProgress.hidden = true;
  }

  window.onNativeTtsState = (state) => {
    nativeTtsSpeaking = state === 'start';
    if (state === 'done' || state === 'error') nativeTtsSpeaking = false;

    if (state === 'synthesizing') {
      showTtsProgress('配音中…', 0);
    } else if (state === 'start') {
      showTtsProgress('播放中…', 100);
    } else {
      hideTtsProgress();
    }
  };

  window.onNativeTtsProgress = (percent) => {
    const p = Math.max(0, Math.min(100, Number(percent) || 0));
    if (ttsProgress && !ttsProgress.hidden) {
      if (ttsProgressText) ttsProgressText.textContent = '配音中… ' + p + '%';
      if (ttsProgressFill) ttsProgressFill.style.width = p + '%';
    }
  };

  window.onNativeBridgeDiscovered = (ip, port) => {
    if (!ip) return;
    const url = normalizeBridgeUrl('http://' + ip + ':' + port);
    if (!url) return;
    const previous = bridgeUrl;
    bridgeUrl = url;
    if (bridgeUrlInput) bridgeUrlInput.value = bridgeUrl;
    storeValue('rikka.bridgeUrl', bridgeUrl);
    if (!directMode && previous !== url) {
      setBridgeState('已发现电脑 · ' + ip, true);
      syncMemoryToBridge();
    }
  };

  window.onNativeGsvStatus = (status, detail) => {
    if (!gsvStatus) return;
    const labels = {
      loading: '加载中…',
      copying: '复制模型…',
      ready: '已就绪',
      error: '加载失败',
    };
    let text = labels[status] || status || '未知状态';
    if (status === 'copying' && detail) text += '：' + detail;
    if (status === 'error' && detail) text += '：' + detail;
    gsvStatus.textContent = text;
    gsvStatus.className = 'gsv-status ' + (status === 'ready' ? 'ok' : status === 'error' ? 'err' : 'busy');
  };

  function sanitizeJapaneseReply(text) {
    if (!text) return text;
    const zhOnly = '你们这个吗吧呢呀啊哦嘛啥咱谁怎咋么哪哟啦咯呗喽';
    let out = '';
    for (const ch of text) {
      if (!zhOnly.includes(ch)) out += ch;
    }
    return out.trim();
  }

  async function translateToJapanese(text) {
    const messages = [{ role: 'system', content: TRANSLATE_TO_JA_PROMPT }, { role: 'user', content: text }];
    const ja = (await callNativeApi(messages)).trim();
    return sanitizeJapaneseReply(ja);
  }

  async function translateAndSpeak(zh) {
    try {
      showTtsProgress('翻译中…', 0);
      const ja = await translateToJapanese(zh);
      if (!ja) { hideTtsProgress(); return; }
      if (window.NativeTts && typeof window.NativeTts.speak === 'function') {
        window.NativeTts.speak(ja);
      }
    } catch (e) {
      hideTtsProgress();
    }
  }

  const VISION_PROMPT = [
    '你是小鸟游六花。用户（勇太）刚刚上传了一张照片并配文。',
    '请观察图片内容，用六花的中二人设和语气用中文回复勇太。',
    '回复 1~3 句话，只输出可以直接朗读的台词，禁止动作描写、神态描写或旁白。',
  ].join('\n');

  async function postDirectChatWithImage(text, imageDataUrl) {
    if (!apiKey) {
      appendChatBubble('请先在设置里填写 API Key。', 'system');
      setBridgeState('直连模式缺少 API Key', false);
      return;
    }
    appendChatBubble(text, 'user');
    chatBusy = true;
    if (chatSend) chatSend.disabled = true;
    setBridgeState('手机正在分析照片…', false);
    try {
      const systemContent = DIRECT_SYSTEM_PROMPT + (memorySummary ? '\n\n【你记得的关于勇太的信息】\n' + memorySummary : '');
      const messages = [{ role: 'system', content: systemContent }]
        .concat(directHistory.slice(-10))
        .concat([{
          role: 'user',
          content: [
            { type: 'text', text: VISION_PROMPT + '\n勇太的配文：' + text },
            { type: 'image_url', image_url: { url: imageDataUrl } },
          ],
        }]);
      const reply = (await callNativeApi(messages, visionModel)).trim();
      if (!reply) throw new Error('API 返回空回复');
      appendMessage('user', text);
      appendMessage('assistant', reply);
      appendChatBubble(reply, 'assistant');
      showCharacterBubble(reply, 8000);
      if (!chatVoice || chatVoice.checked) translateAndSpeak(reply);
      setBridgeState('手机直连 · 六花已回复', true);
    } catch (error) {
      appendChatBubble('照片分析失败：' + (error.message || error), 'system');
      setBridgeState('照片分析失败', false);
    } finally {
      chatBusy = false;
      if (chatSend) chatSend.disabled = false;
    }
  }
  async function postDirectChat(text, displayText) {
    if (!apiKey) {
      appendChatBubble('请先在设置里填写 API Key。', 'system');
      setBridgeState('直连模式缺少 API Key', false);
      return;
    }
    appendChatBubble(displayText || text, 'user');
    chatBusy = true;
    if (chatSend) chatSend.disabled = true;
    setBridgeState('手机正在请求 API…', false);
    try {
      const systemContent = DIRECT_SYSTEM_PROMPT + (memorySummary ? '\n\n【你记得的关于勇太的信息】\n' + memorySummary : '');
      const messages = [{ role: 'system', content: systemContent }]
        .concat(directHistory.slice(-10))
        .concat([{ role: 'user', content: text }]);
      const reply = (await callNativeApi(messages)).trim();
      if (!reply) throw new Error('API 返回空回复');
      appendMessage('user', text);
      appendMessage('assistant', reply);
      appendChatBubble(reply, 'assistant');
      showCharacterBubble(reply, 8000);
      if (!chatVoice || chatVoice.checked) {
        translateAndSpeak(reply);
      }
      setBridgeState('手机直连 · 六花已回复', true);
    } catch (error) {
      appendChatBubble('直连 API 失败：' + (error.message || error), 'system');
      setBridgeState('直连 API 失败', false);
    } finally {
      chatBusy = false;
      if (chatSend) chatSend.disabled = false;
      if (chatInput) chatInput.focus();
    }
  }
  async function postChat(text, displayText, imageUrl) {
    if (chatBusy) return;
    if (directMode) {
      await postDirectChat(text, displayText);
      return;
    }
    const base = normalizeBridgeUrl(bridgeUrlInput ? bridgeUrlInput.value : bridgeUrl);
    if (!base) {
      appendChatBubble('请先在设置里填写电脑桥接地址。', 'system');
      setBridgeState('未连接电脑', false);
      return;
    }
    bridgeUrl = base;
    storeValue('rikka.bridgeUrl', bridgeUrl);
    if (bridgeUrlInput) bridgeUrlInput.value = bridgeUrl;
    appendChatBubble(displayText || text, 'user');
    chatBusy = true;
    if (chatSend) chatSend.disabled = true;
    setBridgeState('电脑思考中…', false);
    try {
      const data = await fetchJson(bridgeUrl + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({
          text: text,
          image_url: imageUrl || null,
          speak: !chatVoice || chatVoice.checked,
        }),
      }, 180000);
      appendChatBubble(data.reply || '（电脑没有返回文字）', 'assistant');
      showCharacterBubble(data.speech_text || data.reply || '', 8000);
      if (data.audio_error) appendChatBubble('文字回复成功，但配音失败：' + data.audio_error, 'system');
      if (data.audio_url || data.audio_base64) playChatAudio(data);
      setBridgeState('已连接 · 六花已回复', true);
    } catch (error) {
      appendChatBubble('发送失败：' + (error.message || error), 'system');
      setBridgeState('连接失败', false);
    } finally {
      chatBusy = false;
      if (chatSend) chatSend.disabled = false;
      if (chatInput) chatInput.focus();
    }
  }
  function setChatPanelOpen(open) {
    if (!chatPanel) return;
    chatPanel.hidden = !open;
    if (open) {
      if (motionPage) motionPage.hidden = true;
      if (orientationPage) orientationPage.hidden = true;
      if (chatInput) window.setTimeout(() => chatInput.focus(), 80);
    }
  }

  function setSpeechActive(active) {
    speechActive = !!active;
    if (chatMic) chatMic.classList.toggle('listening', speechActive);
    if (chatInput) chatInput.placeholder = speechActive ? '正在听你说…' : '对六花说点什么…';
  }

  function showImageBubble(src) {
    if (!chatMessages || !src) return;
    const image = document.createElement('img');
    image.className = 'chat-image';
    image.src = src;
    chatMessages.appendChild(image);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function openPhotoCaption(imageUrl) {
    pendingPhotoUrl = imageUrl;
    if (photoCaptionImage) photoCaptionImage.src = imageUrl;
    if (photoCaptionInput) photoCaptionInput.value = '';
    if (photoCaptionDialog) photoCaptionDialog.hidden = false;
    if (photoCaptionInput) window.setTimeout(() => photoCaptionInput.focus(), 80);
  }

  function closePhotoCaption() {
    if (photoCaptionDialog) photoCaptionDialog.hidden = true;
  }

  function sendPhotoCaption() {
    const imageUrl = pendingPhotoUrl;
    closePhotoCaption();
    if (!imageUrl) return;
    const caption = (photoCaptionInput ? photoCaptionInput.value : '').trim() || '看看这张照片';
    if (directMode) {
      postDirectChatWithImage(caption, imageUrl);
    } else {
      postChat(caption + '\n[用户上传的图片地址：' + imageUrl + ']', caption);
    }
  }
  async function uploadPhoto(dataUrl, filename) {
    if (directMode) {
      showImageBubble(dataUrl);
      openPhotoCaption(dataUrl);
      return;
    }
    const base = normalizeBridgeUrl(bridgeUrlInput ? bridgeUrlInput.value : bridgeUrl);
    if (!base) {
      appendChatBubble('请先在设置里填写电脑桥接地址。', 'system');
      return;
    }
    bridgeUrl = base;
    storeValue('rikka.bridgeUrl', bridgeUrl);
    const comma = dataUrl.indexOf(',');
    const dataBase64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
    appendChatBubble('正在上传照片…', 'system');
    try {
      const result = await fetchJson(bridgeUrl + '/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ filename: filename || 'camera.jpg', data_base64: dataBase64 }),
      }, 60000);
      const uploadedUrl = new URL(result.url, bridgeUrl + '/').href;
      showImageBubble(uploadedUrl);
      appendChatBubble('照片已上传', 'system');
      openPhotoCaption(uploadedUrl);
      setBridgeState('照片已上传', true);
    } catch (error) {
      appendChatBubble('照片上传失败：' + (error.message || error), 'system');
      setBridgeState('照片上传失败', false);
    }
  }

  function capturePhotoUpload() {
    if (window.NativePhoto && typeof window.NativePhoto.capturePhoto === 'function') {
      stopCameraStream();
      window.NativePhoto.capturePhoto();
      return;
    }
    appendChatBubble('当前设备不支持拍照上传。', 'system');
  }

  window.onNativePhotoCaptured = (base64) => {
    if (base64) uploadPhoto('data:image/jpeg;base64,' + base64, 'camera.jpg');
  };

  window.onNativePhotoReturned = () => {
    restartCameraAfterPhoto();
  };

  window.onNativePhotoError = (message) => {
    appendChatBubble('拍照失败：' + (message || '未知错误'), 'system');
  };
  function startVoiceInput() {
    if (speechActive) return;
    setSpeechActive(true);
    if (window.NativeSpeech && typeof window.NativeSpeech.startListening === 'function') {
      try {
        window.NativeSpeech.startListening();
        return;
      } catch (error) {
        setSpeechActive(false);
        appendChatBubble('语音输入启动失败：' + (error.message || error), 'system');
        return;
      }
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechActive(false);
      appendChatBubble('当前设备不支持语音识别，请使用安卓自带键盘语音输入。', 'system');
      return;
    }
    try {
      speechRecognition = new Recognition();
      speechRecognition.lang = 'zh-CN';
      speechRecognition.interimResults = true;
      speechRecognition.continuous = false;
      speechRecognition.onresult = (event) => {
        let text = '';
        for (let i = 0; i < event.results.length; i += 1) text += event.results[i][0].transcript;
        if (chatInput) chatInput.value = text;
      };
      speechRecognition.onerror = (event) => {
        setSpeechActive(false);
        appendChatBubble('语音输入失败：' + (event.error || '未知错误'), 'system');
      };
      speechRecognition.onend = () => setSpeechActive(false);
      speechRecognition.start();
    } catch (error) {
      setSpeechActive(false);
      appendChatBubble('语音输入启动失败：' + (error.message || error), 'system');
    }
  }

  window.onNativeSpeechPartial = (text) => {
    if (chatInput && text) chatInput.value = text;
  };

  window.onNativeSpeechFinal = (text) => {
    const value = (text || '').trim();
    if (value) {
      if (micAlwaysOn) {
        if (chatInput) chatInput.value = value;
        sendChatMessage();
      } else if (chatInput) {
        chatInput.value = value;
        chatInput.focus();
      }
    }
    setSpeechActive(false);
  };

  window.onNativeSpeechLevel = (level) => {
    const numeric = Math.max(0, Math.min(1, Number(level) || 0));
    if (micMeterFill) micMeterFill.style.width = Math.round(numeric * 100) + '%';
    if (micMeter) micMeter.classList.toggle('active', numeric > 0.02);
  };

  window.onNativeSpeechEnd = () => {
    setSpeechActive(false);
  };

  window.onNativeSpeechError = (message) => {
    setSpeechActive(false);
    appendChatBubble('语音输入失败：' + (message || '未识别到声音'), 'system');
  };
  function pushVoiceConfig() {
    if (window.NativeTts && typeof window.NativeTts.setVoiceConfig === 'function') {
      window.NativeTts.setVoiceConfig(JSON.stringify({
        localVoice: localVoiceEnabled,
        speed: voiceSpeed,
        volume: voiceVolume,
        pitch: voicePitch,
        deElect: voiceDeelect / 100,
      }));
    }
  }
  function setupBridgeControls() {
    const storedUrl = readStored('rikka.bridgeUrl');
    directMode = readStored('rikka.directMode') === '1';
    apiKey = readStored('rikka.apiKey') || '';
    apiBase = readStored('rikka.apiBase') || 'https://api.deepseek.com';
    apiModel = readStored('rikka.apiModel') || 'deepseek-chat';
    try { msgLog = JSON.parse(readStored('rikka.msglog') || '[]'); } catch (_) { msgLog = []; }
    try { journal = JSON.parse(readStored('rikka.journal') || '{}'); } catch (_) { journal = {}; }
    try { memoryMeta = JSON.parse(readStored('rikka.meta') || '{}'); } catch (_) { memoryMeta = {}; }
    memorySummary = readStored('rikka.memory') || '';
    directHistory = msgLog.slice(-20).map((m) => ({ role: m.role, content: m.content }));
    restoreChatHistory();
    if (!directMode) syncMemoryToBridge();
    window.setInterval(() => { if (!directMode) syncMemoryToBridge(); }, 60000);
    if (directModeToggle) directModeToggle.checked = directMode;
    if (apiKeyInput) apiKeyInput.value = apiKey;
    if (apiBaseInput) apiBaseInput.value = apiBase;
    if (apiModelInput) apiModelInput.value = apiModel;
    if (directModeToggle) directModeToggle.addEventListener('change', () => {
      directMode = !!directModeToggle.checked;
      storeValue('rikka.directMode', directMode ? '1' : '0');
      setBridgeState(directMode ? '手机直连模式' : '电脑桥接模式', false);
    });
    if (apiKeyInput) apiKeyInput.addEventListener('change', () => {
      apiKey = apiKeyInput.value.trim();
      storeValue('rikka.apiKey', apiKey);
    });
    if (apiKeyPaste && window.NativeClipboard && typeof window.NativeClipboard.readText === 'function') {
      apiKeyPaste.addEventListener('click', () => {
        try {
          const text = window.NativeClipboard.readText();
          if (text) {
            apiKey = text.trim();
            if (apiKeyInput) apiKeyInput.value = apiKey;
            storeValue('rikka.apiKey', apiKey);
          }
        } catch (_) {}
      });
    }
    if (apiBaseInput) apiBaseInput.addEventListener('change', () => {
      apiBase = apiBaseInput.value.trim() || 'https://api.deepseek.com';
      storeValue('rikka.apiBase', apiBase);
    });
    if (apiModelInput) apiModelInput.addEventListener('change', () => {
      apiModel = apiModelInput.value.trim() || 'deepseek-chat';
      storeValue('rikka.apiModel', apiModel);
    });
    visionModel = readStored('rikka.visionModel') || 'deepseek-v4-flash-vision-exp';
    if (visionModelInput) {
      visionModelInput.value = visionModel;
      visionModelInput.addEventListener('change', () => {
        visionModel = visionModelInput.value.trim() || 'deepseek-v4-flash-vision-exp';
        storeValue('rikka.visionModel', visionModel);
      });
    }

    localVoiceEnabled = readStored('rikka.localVoice') !== '0';
    voiceSpeed = parseFloat(readStored('rikka.voiceSpeed') || '1') || 1;
    voiceVolume = parseFloat(readStored('rikka.voiceVolume') || '1') || 1;
    voicePitch = parseInt(readStored('rikka.voicePitch') || '0', 10) || 0;
    voiceDeelect = parseInt(readStored('rikka.voiceDeelect') || '0', 10) || 0;
    if (localVoiceToggle) {
      localVoiceToggle.checked = localVoiceEnabled;
      localVoiceToggle.addEventListener('change', () => {
        localVoiceEnabled = !!localVoiceToggle.checked;
        storeValue('rikka.localVoice', localVoiceEnabled ? '1' : '0');
        pushVoiceConfig();
      });
    }
    if (voiceSpeedInput) {
      voiceSpeedInput.value = voiceSpeed;
      if (voiceSpeedValue) voiceSpeedValue.textContent = voiceSpeed.toFixed(2) + '×';
      voiceSpeedInput.addEventListener('input', () => {
        voiceSpeed = parseFloat(voiceSpeedInput.value) || 1;
        if (voiceSpeedValue) voiceSpeedValue.textContent = voiceSpeed.toFixed(2) + '×';
        storeValue('rikka.voiceSpeed', String(voiceSpeed));
        pushVoiceConfig();
      });
    }
    if (voiceVolumeInput) {
      voiceVolumeInput.value = Math.round(voiceVolume * 100);
      if (voiceVolumeValue) voiceVolumeValue.textContent = Math.round(voiceVolume * 100) + '%';
      voiceVolumeInput.addEventListener('input', () => {
        voiceVolume = (parseFloat(voiceVolumeInput.value) || 0) / 100;
        if (voiceVolumeValue) voiceVolumeValue.textContent = Math.round(voiceVolume * 100) + '%';
        storeValue('rikka.voiceVolume', String(voiceVolume));
        pushVoiceConfig();
      });
    }
    if (voicePitchInput) {
      voicePitchInput.value = voicePitch;
      if (voicePitchValue) voicePitchValue.textContent = String(voicePitch);
      voicePitchInput.addEventListener('input', () => {
        voicePitch = parseInt(voicePitchInput.value, 10) || 0;
        if (voicePitchValue) voicePitchValue.textContent = String(voicePitch);
        storeValue('rikka.voicePitch', String(voicePitch));
        pushVoiceConfig();
      });
    }
    if (voiceDeelectInput) {
      voiceDeelectInput.value = voiceDeelect;
      if (voiceDeelectValue) voiceDeelectValue.textContent = voiceDeelect + '%';
      voiceDeelectInput.addEventListener('input', () => {
        voiceDeelect = parseInt(voiceDeelectInput.value, 10) || 0;
        if (voiceDeelectValue) voiceDeelectValue.textContent = voiceDeelect + '%';
        storeValue('rikka.voiceDeelect', String(voiceDeelect));
        pushVoiceConfig();
      });
    }
    if (voiceReset) {
      voiceReset.addEventListener('click', () => {
        voiceSpeed = 1; voiceVolume = 1; voicePitch = 0; voiceDeelect = 0;
        if (voiceSpeedInput) { voiceSpeedInput.value = 1; if (voiceSpeedValue) voiceSpeedValue.textContent = '1.00×'; }
        if (voiceVolumeInput) { voiceVolumeInput.value = 100; if (voiceVolumeValue) voiceVolumeValue.textContent = '100%'; }
        if (voicePitchInput) { voicePitchInput.value = 0; if (voicePitchValue) voicePitchValue.textContent = '0'; }
        if (voiceDeelectInput) { voiceDeelectInput.value = 0; if (voiceDeelectValue) voiceDeelectValue.textContent = '0%'; }
        storeValue('rikka.voiceSpeed', '1');
        storeValue('rikka.voiceVolume', '1');
        storeValue('rikka.voicePitch', '0');
        storeValue('rikka.voiceDeelect', '0');
        pushVoiceConfig();
      });
    }
    if (voiceOpen && voicePage) {
      voiceOpen.addEventListener('click', () => { voicePage.hidden = false; });
      voiceClose.addEventListener('click', () => { voicePage.hidden = true; });
      voicePage.addEventListener('click', (event) => { if (event.target === voicePage) voicePage.hidden = true; });
    }
    if (memoryClear) {
      memoryClear.addEventListener('click', () => {
        directHistory = [];
        memorySummary = '';
        msgLog = [];
        journal = {};
        persistHistory();
        saveMsgLog();
        saveJournal();
        storeValue('rikka.memory', '');
        storeValue('rikka.meta', '{}');
        appendChatBubble('聊天记忆已清空', 'system');
      });
    }
    pushVoiceConfig();
    runDailyMaintenance();
    if (window.NativeDiscovery && typeof window.NativeDiscovery.start === 'function') {
      window.NativeDiscovery.start();
    }
    bridgeUrl = normalizeBridgeUrl(storedUrl || DEFAULT_BRIDGE_URL);
    if (bridgeUrlInput) {
      bridgeUrlInput.value = bridgeUrl;
      bridgeUrlInput.addEventListener('change', () => {
        bridgeUrl = normalizeBridgeUrl(bridgeUrlInput.value);
        bridgeUrlInput.value = bridgeUrl;
        storeValue('rikka.bridgeUrl', bridgeUrl);
        setBridgeState('未测试', false);
      });
    }
    if (chatVoice) {
      chatVoice.checked = readStored('rikka.chatVoice') !== '0';
      chatVoice.addEventListener('change', () => storeValue('rikka.chatVoice', chatVoice.checked ? '1' : '0'));
    }
    if (chatOpen) chatOpen.addEventListener('click', () => setChatPanelOpen(true));
    if (chatClose) chatClose.addEventListener('click', () => setChatPanelOpen(false));
    if (chatPanel) {
      chatPanel.addEventListener('click', (event) => {
        if (event.target === chatPanel) setChatPanelOpen(false);
      });
    }
    if (chatForm) chatForm.addEventListener('submit', sendChatMessage);
    if (bridgeTest) bridgeTest.addEventListener('click', testBridgeConnection);
    if (chatMic) chatMic.addEventListener('click', startVoiceInput);
    if (chatCamera) chatCamera.addEventListener('click', capturePhotoUpload);
    if (photoCaptionSend) photoCaptionSend.addEventListener('click', sendPhotoCaption);
    if (photoCaptionSkip) photoCaptionSkip.addEventListener('click', closePhotoCaption);
    if (photoCaptionDialog) photoCaptionDialog.addEventListener('click', (event) => { if (event.target === photoCaptionDialog) closePhotoCaption(); });
    micAlwaysOn = readStored('rikka.micAlwaysOn') === '1';
    if (chatMicAlways) chatMicAlways.checked = micAlwaysOn;
    if (window.NativeSpeech && typeof window.NativeSpeech.setContinuous === 'function') {
      window.NativeSpeech.setContinuous(micAlwaysOn);
    }
    if (chatMicAlways) {
      chatMicAlways.addEventListener('change', () => {
        micAlwaysOn = !!chatMicAlways.checked;
        storeValue('rikka.micAlwaysOn', micAlwaysOn ? '1' : '0');
        if (window.NativeSpeech && typeof window.NativeSpeech.setContinuous === 'function') {
          window.NativeSpeech.setContinuous(micAlwaysOn);
        }
        if (!micAlwaysOn) {
          if (window.NativeSpeech && typeof window.NativeSpeech.stopListening === 'function') window.NativeSpeech.stopListening();
          setSpeechActive(false);
          if (micMeterFill) micMeterFill.style.width = '0%';
        }
      });
    }
  }
  function setupControls() {
    const storedDark = readStored('rikka.dark');
    const storedAmplitude = Number(readStored('rikka.amplitude'));
    const storedMode = readStored('rikka.displayMode');
    const storedSpeed = Number(readStored('rikka.motionSpeed'));
    const storedFollow = Number(readStored('rikka.followStrength'));
    const storedIdle = Number(readStored('rikka.idleAmplitude'));
    const storedBreath = Number(readStored('rikka.breathAmplitude'));
    const storedCharacterScale = Number(readStored('rikka.characterScale'));
    const storedCharacterX = Number(readStored('rikka.characterX'));
    const storedCharacterY = Number(readStored('rikka.characterY'));
    applyDarkMode(storedDark === '1');
    updateAmplitude(Number.isFinite(storedAmplitude) && storedAmplitude > 0 ? storedAmplitude : 1);
    updateMotionSpeed(Number.isFinite(storedSpeed) && storedSpeed > 0 ? storedSpeed : 1);
    updateFollowStrength(Number.isFinite(storedFollow) ? storedFollow : 1);
    updateIdleAmplitude(Number.isFinite(storedIdle) ? storedIdle : 1);
    updateBreathAmplitude(Number.isFinite(storedBreath) ? storedBreath : 1);
    updateCharacterScale(Number.isFinite(storedCharacterScale) && storedCharacterScale > 0 ? storedCharacterScale : 1);
    updateCharacterX(Number.isFinite(storedCharacterX) ? storedCharacterX : 0);
    updateCharacterY(Number.isFinite(storedCharacterY) ? storedCharacterY : 0);
    applyDisplayMode(storedMode === 'landscape' ? 'landscape' : 'portrait');
    if (darkToggle) {
      darkToggle.addEventListener('change', () => applyDarkMode(darkToggle.checked));
    }
    if (amplitudeInput) {
      amplitudeInput.addEventListener('input', () => updateAmplitude(amplitudeInput.value));
    }
    if (motionAmplitudeInput) {
      motionAmplitudeInput.addEventListener('input', () => updateAmplitude(motionAmplitudeInput.value));
    }
    if (motionSpeedInput) {
      motionSpeedInput.addEventListener('input', () => updateMotionSpeed(motionSpeedInput.value));
    }
    if (motionFollowInput) {
      motionFollowInput.addEventListener('input', () => updateFollowStrength(motionFollowInput.value));
    }
    if (motionIdleInput) {
      motionIdleInput.addEventListener('input', () => updateIdleAmplitude(motionIdleInput.value));
    }
    if (motionBreathInput) {
      motionBreathInput.addEventListener('input', () => updateBreathAmplitude(motionBreathInput.value));
    }
    if (motionOpen) {
      motionOpen.addEventListener('click', () => setMotionPageOpen(true));
    }
    if (motionClose) {
      motionClose.addEventListener('click', () => setMotionPageOpen(false));
    }
    if (motionPage) {
      motionPage.addEventListener('click', (event) => {
        if (event.target === motionPage) setMotionPageOpen(false);
      });
    }
    if (orientationOpen) {
      orientationOpen.addEventListener('click', () => setOrientationPageOpen(true));
    }
    if (orientationClose) {
      orientationClose.addEventListener('click', () => setOrientationPageOpen(false));
    }
    if (orientationPage) {
      orientationPage.addEventListener('click', (event) => {
        if (event.target === orientationPage) setOrientationPageOpen(false);
      });
    }
    if (motionReset) {
      motionReset.addEventListener('click', resetMotionSettings);
    }
    if (modePortraitButton) {
      modePortraitButton.addEventListener('click', () => applyDisplayMode('portrait'));
    }
    if (modeLandscapeButton) {
      modeLandscapeButton.addEventListener('click', () => applyDisplayMode('landscape'));
    }
    if (characterScaleInput) {
      characterScaleInput.addEventListener('input', () => updateCharacterScale(characterScaleInput.value));
    }
    if (characterXInput) {
      characterXInput.addEventListener('input', () => updateCharacterX(characterXInput.value));
    }
    if (characterYInput) {
      characterYInput.addEventListener('input', () => updateCharacterY(characterYInput.value));
    }
  }
  function refreshLayoutSoon() {
    [0, 80, 240, 520, 900].forEach((delay) => window.setTimeout(layoutModel, delay));
  }

  function applyModelTransform() {
    if (!model || !app) return;
    const w = Math.max(1, window.innerWidth || app.screen.width);
    const h = Math.max(1, window.innerHeight || app.screen.height);
    const baseW = modelBaseWidth;
    const baseH = modelBaseHeight;
    const bigHead = displayMode === 'landscape';
    const baseScale = Math.min(w / baseW, h / baseH);
    const baseY = bigHead ? 0.94 : 0.54;
    model.scale.set(baseScale * (bigHead ? 1.85 : 0.94) * characterScale);
    model.position.set(w * (0.5 + characterX), h * (baseY + characterY));
    document.body.classList.toggle('landscape-mode', bigHead);
    if (orientationBadge) orientationBadge.textContent = bigHead ? '横屏 · 大头' : '竖屏 · 全身';
  }

  function scheduleModelTransform() {
    if (transformFrame) return;
    transformFrame = window.requestAnimationFrame(() => {
      transformFrame = 0;
      applyModelTransform();
    });
  }

  function layoutModel() {
    if (!model || !app) return;
    const w = Math.max(1, window.innerWidth || app.screen.width);
    const h = Math.max(1, window.innerHeight || app.screen.height);
    if (app.renderer && typeof app.renderer.resize === 'function') {
      app.renderer.resize(w, h);
    }
    applyModelTransform();
  }
  async function initLive2D() {
    if (!window.PIXI || !PIXI.Application) throw new Error('PIXI 渲染库未加载');
    if (!PIXI.live2d || !PIXI.live2d.Live2DModel) throw new Error('Live2D 插件未加载');
    setStatus('正在创建 WebGL 渲染器…');
    app = new PIXI.Application({
      view: canvas,
      resizeTo: window,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    });

    setStatus('正在下载并解析模型…');
    model = await PIXI.live2d.Live2DModel.from(MODEL_URL);
    model.anchor.set(0.5, 0.5);
    modelBaseWidth = Math.max(1, model.width);
    modelBaseHeight = Math.max(1, model.height);
    model.autoUpdate = false;
    if (model.internalModel && model.internalModel.motionManager) {
      try {
        model.internalModel.motionManager.stopAllMotions();
      } catch (_) {}
    }
    app.stage.addChild(model);
    coreModel = model.internalModel.coreModel;
    layoutModel();
    window.addEventListener('resize', layoutModel);
  }

  function waitForOpenCv(timeoutMs) {
    return new Promise((resolve, reject) => {
      const startedAt = Date.now();
      let hooked = false;
      const check = () => {
        if (window.__opencvAbortReason) {
          reject(new Error('OpenCV 初始化中止：' + window.__opencvAbortReason));
          return;
        }
        const cv = window.cv;
        if (cv && cv.Mat) {
          resolve(cv);
          return;
        }
        if (cv && !hooked) {
          hooked = true;
          const previousReady = cv.onRuntimeInitialized;
          cv.onRuntimeInitialized = () => {
            if (typeof previousReady === 'function') {
              try { previousReady(); } catch (_) {}
            }
            resolve(cv);
          };
          const previousAbort = cv.onAbort;
          cv.onAbort = (reason) => {
            if (typeof previousAbort === 'function') {
              try { previousAbort(reason); } catch (_) {}
            }
            reject(new Error('OpenCV 初始化中止：' + reason));
          };
        }
        if (Date.now() - startedAt >= timeoutMs) {
          reject(new Error('OpenCV 初始化超时'));
          return;
        }
        window.setTimeout(check, 100);
      };
      check();
    });
  }

  async function initOpenCv() {
    if (!window.WebAssembly) {
      throw new Error('当前 WebView 不支持 WebAssembly');
    }
    const cv = await waitForOpenCv(25000);
    if (!window.FACE_CASCADE_XML) {
      throw new Error('缺少人脸模型数据');
    }
    const xmlBytes = new TextEncoder().encode(window.FACE_CASCADE_XML);
    cv.FS_createDataFile('/', 'haarcascade_frontalface_default.xml', xmlBytes, true, false, false);
    classifier = new cv.CascadeClassifier();
    if (!classifier.load('haarcascade_frontalface_default.xml')) {
      throw new Error('OpenCV 人脸模型加载失败');
    }
    return cv;
  }
  function stopCameraStream() {
    if (activeCameraStream) {
      try {
        activeCameraStream.getTracks().forEach((track) => track.stop());
      } catch (_) {}
      activeCameraStream = null;
    }
    if (video) video.srcObject = null;
    if (cameraPanel) cameraPanel.classList.remove('found');
  }

  async function restartCameraAfterPhoto() {
    try {
      stopCameraStream();
      await initCamera();
      setStatus('人物跟随已恢复', 1400);
    } catch (error) {
      console.warn('拍照后重启前置摄像头失败', error);
      setStatus('前置摄像头重启失败：' + (error.message || error));
    }
  }
  async function initCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('当前 WebView 不支持摄像头');
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: 'user',
        width: { ideal: 640 },
        height: { ideal: 480 },
        frameRate: { ideal: 24, max: 30 },
      },
    });
    activeCameraStream = stream;
    video.srcObject = stream;
    await video.play();
    await new Promise((resolve) => {
      if (video.videoWidth > 0) return resolve();
      video.onloadedmetadata = resolve;
    });
  }

  function detectFaces(cv) {
    if (!classifier || !video.videoWidth || !video.videoHeight) return;
    const src = new cv.Mat(video.videoHeight, video.videoWidth, cv.CV_8UC4);
    const gray = new cv.Mat();
    const faces = new cv.RectVector();
    try {
      if (!videoCapture) videoCapture = new cv.VideoCapture(video);
      videoCapture.read(src);
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
      cv.equalizeHist(gray, gray);
      classifier.detectMultiScale(gray, faces, 1.1, 3, 0, new cv.Size(64, 64));

      let best = null;
      for (let i = 0; i < faces.size(); i += 1) {
        const r = faces.get(i);
        if (!best || r.width * r.height > best.width * best.height) best = r;
      }

      if (best) {
        const rawX = (best.x + best.width * 0.5) / video.videoWidth;
        const mirroredX = 1.0 - rawX;
        const rawY = (best.y + best.height * 0.5) / video.videoHeight;
        faceTargetX = Math.max(-1, Math.min(1, (mirroredX - 0.5) * 2));
        faceTargetY = Math.max(-1, Math.min(1, (rawY - 0.5) * 2));
        faceVisible = true;
      } else {
        faceTargetX = 0;
        faceTargetY = 0;
        faceVisible = false;
      }
      cameraPanel.classList.toggle('found', faceVisible);
    } finally {
      src.delete();
      gray.delete();
      faces.delete();
    }
  }

  function setParameter(id, value) {
    if (coreModel && typeof coreModel.setParameterValueById === 'function') {
      coreModel.setParameterValueById(id, value);
    }
  }

  function animateModel(deltaMs) {
    if (!model || !coreModel) return;
    const t = performance.now() / 1000;
    const dx = faceTargetX - faceX;
    const dy = faceTargetY - faceY;
    const followX = Math.min(0.34, 0.18 + Math.abs(dx) * 1.0);
    const followY = Math.min(0.30, 0.16 + Math.abs(dy) * 0.9);
    if (Math.abs(dx) > 0.0015) faceX += dx * followX;
    if (Math.abs(dy) > 0.0015) faceY += dy * followY;
    const amplitude = animationAmplitude;
    const phase = t * motionSpeed;
    const followGain = followStrength;
    const idleGain = idleAmplitude;
    const breathGain = breathAmplitude;
    setParameter('ParamAngleX', faceX * 36 * amplitude * followGain);
    setParameter('ParamAngleY', -faceY * 28 * amplitude * followGain);
    setParameter('ParamAngleZ', faceX * 5 * amplitude * followGain);
    setParameter('ParamHairFront', 0.32 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 3.8));
    setParameter('Param3', 2.4 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4));
    setParameter('Param', 1.0 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4 + 0.5));
    setParameter('Param2', -1.0 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4 + 0.5));
    let mouth = 0.5 + 0.12 * amplitude * breathGain * Math.sin(phase * Math.PI * 2 / 5.8);
    if (nativeTtsSpeaking) {
      const target = 0.55 + 0.45 * Math.sin(t * 18.0);
      voiceMouthLevel += (target - voiceMouthLevel) * 0.45;
      mouth = Math.pow(Math.max(0, Math.min(1, voiceMouthLevel)), 0.65);
    } else if (voiceIsTalking && voiceMouthAnalyser) {
      const samples = new Uint8Array(voiceMouthAnalyser.fftSize || 256);
      voiceMouthAnalyser.getByteTimeDomainData(samples);
      let energy = 0;
      for (let i = 0; i < samples.length; i += 1) {
        const value = (samples[i] - 128) / 128;
        energy += value * value;
      }
      const rms = Math.sqrt(energy / samples.length);
      if (rms > voiceMouthPeak) {
        voiceMouthPeak += (rms - voiceMouthPeak) * 0.35;
      } else {
        voiceMouthPeak *= 0.995;
      }
      const normalized = voiceMouthPeak > 1e-6
        ? Math.max(0, Math.min(1, rms / (voiceMouthPeak * 0.75)))
        : 0;
      const target = Math.sqrt(normalized);
      const dt = Math.max(0, deltaMs || 16) / 1000;
      voiceMouthLevel += (target - voiceMouthLevel) * Math.min(1, dt * 24);
      mouth = Math.pow(Math.max(0, Math.min(1, voiceMouthLevel)), 0.65);
    } else {
      voiceMouthLevel *= 0.92;
    }
    setParameter('Param4', -30 + 60 * mouth);
    model.update(deltaMs / 1000);
  }

  function loadArrayBuffer(url) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.responseType = 'arraybuffer';
      xhr.timeout = 45000;
      xhr.onload = () => {
        if ((xhr.status >= 200 && xhr.status < 300) || xhr.status === 0) {
          resolve(xhr.response);
          return;
        }
        reject(new Error('WASM 下载失败，HTTP ' + xhr.status));
      };
      xhr.onerror = () => reject(new Error('WASM 下载失败'));
      xhr.ontimeout = () => reject(new Error('WASM 下载超时'));
      xhr.send();
    });
  }
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error('加载失败：' + src));
      document.head.appendChild(script);
    });
  }

  function withTimeout(promise, timeoutMs, message) {
    return Promise.race([
      promise,
      new Promise((_, reject) => {
        window.setTimeout(() => reject(new Error(message)), timeoutMs);
      }),
    ]);
  }

  function startNativeFaceTracking() {
    if (!window.NativeFaceBridge || typeof window.NativeFaceBridge.detect !== 'function') {
      throw new Error('OpenCV 不可用，且安卓原生人脸检测不可用');
    }
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    const tick = () => {
      if (!video.videoWidth || !video.videoHeight) return;
      const videoWidth = video.videoWidth;
      const videoHeight = video.videoHeight;
      let width = 320;
      let height = Math.round(width * videoHeight / videoWidth);
      if (height > 320) {
        height = 320;
        width = Math.round(height * videoWidth / videoHeight);
      }
      width -= width % 2;
      height -= height % 2;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      context.drawImage(video, 0, 0, width, height);
      try {
        const result = JSON.parse(window.NativeFaceBridge.detect(canvas.toDataURL('image/jpeg', 0.72)));
        applyFaceResult(result);
      } catch (error) {
        console.warn('原生人脸检测失败', error);
        applyFaceResult({ found: false });
      }
    };
    tick();
    window.setInterval(tick, 240);
  }
  function applyFaceResult(result) {
    if (result && result.found) {
      const nextX = clampNumber(result.x, 0, 1, 0.5);
      const nextY = clampNumber(result.y, 0, 1, 0.5);
      if (!faceSeen) {
        faceRawX = nextX;
        faceRawY = nextY;
        faceSeen = true;
      } else {
        const rawDeltaX = nextX - faceRawX;
        const rawDeltaY = nextY - faceRawY;
        const rawAlphaX = Math.min(0.72, 0.32 + Math.abs(rawDeltaX) * 5.5);
        const rawAlphaY = Math.min(0.72, 0.32 + Math.abs(rawDeltaY) * 5.5);
        if (Math.abs(rawDeltaX) > 0.0015) faceRawX += rawDeltaX * rawAlphaX;
        if (Math.abs(rawDeltaY) > 0.0015) faceRawY += rawDeltaY * rawAlphaY;
      }
      faceMissFrames = 0;
      const mirroredX = 1.0 - faceRawX;
      const targetX = Math.max(-1, Math.min(1, (mirroredX - 0.5) * 2));
      const targetY = Math.max(-1, Math.min(1, (faceRawY - 0.5) * 2));
      const targetDeltaX = targetX - faceTargetX;
      const targetDeltaY = targetY - faceTargetY;
      const targetAlphaX = Math.min(0.64, 0.26 + Math.abs(targetDeltaX) * 2.4);
      const targetAlphaY = Math.min(0.58, 0.23 + Math.abs(targetDeltaY) * 2.2);
      faceTargetX += targetDeltaX * targetAlphaX;
      faceTargetY += targetDeltaY * targetAlphaY;
      faceVisible = true;
    } else {
      faceMissFrames += 1;
      if (faceMissFrames < 3) return;
      faceSeen = false;
      faceTargetX += (0 - faceTargetX) * 0.10;
      faceTargetY += (0 - faceTargetY) * 0.10;
      faceVisible = false;
    }
    cameraPanel.classList.toggle('found', faceVisible);
  }
  function getCaptureSize(maxSize) {
    const videoWidth = video.videoWidth;
    const videoHeight = video.videoHeight;
    let width = maxSize;
    let height = Math.round(width * videoHeight / videoWidth);
    if (height > maxSize) {
      height = maxSize;
      width = Math.round(height * videoWidth / videoHeight);
    }
    width -= width % 2;
    height -= height % 2;
    return { width: Math.max(2, width), height: Math.max(2, height) };
  }

  function startOpenCvWorker(wasmBuffer) {
    return new Promise((resolve, reject) => {
      if (!window.Worker) {
        reject(new Error('当前 WebView 不支持 Web Worker'));
        return;
      }
      const worker = new Worker('lib/opencv-worker.js');
      let settled = false;
      const timer = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        worker.terminate();
        reject(new Error('OpenCV Worker 初始化超时'));
      }, 25000);

      worker.onmessage = (event) => {
        const message = event.data || {};
        if (message.type === 'ready') {
          if (settled) return;
          settled = true;
          window.clearTimeout(timer);
          openCvWorker = worker;
          resolve(worker);
          return;
        }
        if (message.type === 'face') {
          openCvWorkerBusy = false;
          applyFaceResult(message);
          return;
        }
        if (message.type === 'error') {
          if (!settled) {
            settled = true;
            window.clearTimeout(timer);
            worker.terminate();
            reject(new Error(message.message || 'OpenCV Worker 错误'));
          } else {
            openCvWorkerBusy = false;
            console.warn('OpenCV Worker:', message.message);
          }
        }
      };

      worker.onerror = (event) => {
        const message = event && event.message ? event.message : 'OpenCV Worker 错误';
        if (!settled) {
          settled = true;
          window.clearTimeout(timer);
          worker.terminate();
          reject(new Error(message));
        } else {
          openCvWorkerBusy = false;
          console.warn('OpenCV Worker:', message);
        }
      };

      worker.postMessage({ type: 'init', wasm: wasmBuffer }, [wasmBuffer]);
    });
  }

  function startWorkerFaceTracking(worker) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d', { willReadFrequently: true });
    const tick = () => {
      if (openCvWorkerBusy || !video.videoWidth || !video.videoHeight) return;
      const size = getCaptureSize(320);
      if (canvas.width !== size.width || canvas.height !== size.height) {
        canvas.width = size.width;
        canvas.height = size.height;
      }
      context.drawImage(video, 0, 0, size.width, size.height);
      const imageData = context.getImageData(0, 0, size.width, size.height);
      openCvWorkerBusy = true;
      worker.postMessage({
        type: 'frame',
        width: size.width,
        height: size.height,
        buffer: imageData.data.buffer,
      }, [imageData.data.buffer]);
    };
    tick();
    window.setInterval(tick, 160);
  }
  async function main() {
    try {
      setStatus('正在加载 Live2D…');
      await withTimeout(initLive2D(), 45000, 'Live2D 加载超时');
      let worker = null;
      try {
        setStatus('正在下载 OpenCV WASM…');
        const openCvWasm = await withTimeout(loadArrayBuffer('lib/opencv.wasm'), 45000, 'OpenCV WASM 下载超时');
        setStatus('正在后台初始化 OpenCV…');
        worker = await startOpenCvWorker(openCvWasm);
      } catch (openCvError) {
        console.warn('OpenCV 不可用，尝试原生兜底', openCvError);
        if (!window.NativeFaceBridge) throw openCvError;
        setStatus('OpenCV 不可用，正在切换原生人脸追踪…');
      }
      setStatus('请允许摄像头权限…');
      await initCamera();
      if (worker) {
        startWorkerFaceTracking(worker);
      } else {
        startNativeFaceTracking();
      }
      app.ticker.add(() => animateModel(app.ticker.deltaMS));
      setStatus(worker ? '人物跟随已启动' : '人物跟随已启动（原生模式）', 2200);
    } catch (err) {
      console.error(err);
      setStatus('Demo 启动失败：' + (err && err.message ? err.message : err));
    }
  }

  setupControls();
  setupBridgeControls();
  window.addEventListener('orientationchange', refreshLayoutSoon);
  if (window.visualViewport) window.visualViewport.addEventListener('resize', layoutModel);
  main();
})();
