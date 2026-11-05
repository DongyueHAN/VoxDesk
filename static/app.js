"use strict";

/* ============================================================
 * 状态与工具
 * ============================================================ */
const $ = (id) => document.getElementById(id);
const APP = $("app");
const MSG = $("messages");
const LOG = $("log");
const WELCOME = $("welcome");
const PLAYER = $("player");
const LS = {
  mode: "voxdesk.mode",
  tts: "voxdesk.tts",
  web: "voxdesk.web",
  last: "voxdesk.lastChat",
};

const state = {
  mode: localStorage.getItem(LS.mode) === "companion" ? "companion" : "general",
  ttsOn: localStorage.getItem(LS.tts) !== "0",
  webOn: localStorage.getItem(LS.web) !== "0",
  currentId: null,
  archived: false,
  readOnly: false,
  busy: false,
  chats: [],
  archives: [],
  stats: { active: 0, archive: 0, limits: { active: 30, archive: 100, bytes: 1048576 } },
};

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderMarkdown(text) {
  let s = escapeHtml(text);
  const blocks = [];
  s = s.replace(/```([\s\S]*?)```/g, (_, code) => {
    blocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\n/g, "<br>");
  s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[Number(i)] || "");
  return s;
}

function formatTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(11, 16);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatBytes(n) {
  if (!n) return "0KB";
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}

function sourceLabel(s) {
  return s === "mic" ? "麦克风" : s === "desktop" ? "桌面音频" : "文字";
}

let toastTimer = null;
function toast(message, error = false) {
  const el = $("toast");
  el.textContent = String(message);
  el.classList.toggle("error", !!error);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  let data = {};
  try { data = await res.json(); } catch { /* 非 JSON */ }
  if (!res.ok || data.error) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/* ============================================================
 * 侧栏 / 会话列表
 * ============================================================ */
function updateStats() {
  const limits = state.stats?.limits || { active: 30, archive: 100, bytes: 1048576 };
  $("activeCount").textContent = `${state.chats.length}/${limits.active}`;
  $("archiveCount").textContent = `${state.archives.length}/${limits.archive}`;
  const total = (state.stats.active_bytes || 0) + (state.stats.archive_bytes || 0);
  $("storageText").textContent = `活跃 ${state.chats.length}/${limits.active} · 归档 ${state.archives.length}/${limits.archive} · ${formatBytes(total)}`;
}

function chatRow(item, archived) {
  const row = document.createElement("div");
  row.className = "chat-row" + (state.currentId === item.id && state.archived === archived ? " active" : "");
  row.title = item.title || "新对话";
  const main = document.createElement("div");
  main.className = "chat-row-main";
  const title = document.createElement("div");
  title.className = "chat-row-title";
  title.textContent = item.title || "新对话";
  const meta = document.createElement("div");
  meta.className = "chat-row-meta";
  meta.textContent = `${item.mode === "companion" ? "陪伴" : "通用"} · ${formatTime(item.updated_at)} · ${formatBytes(item.bytes)}`;
  main.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "chat-row-actions";
  const archiveBtn = document.createElement("button");
  archiveBtn.className = "mini-btn";
  archiveBtn.textContent = archived ? "↩" : "⇩";
  archiveBtn.title = archived ? "恢复" : "归档";
  archiveBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    try {
      if (archived) await restoreChat(item.id);
      else await archiveChat(item.id);
    } catch (err) { toast(err.message || String(err), true); }
  });
  const delBtn = document.createElement("button");
  delBtn.className = "mini-btn";
  delBtn.textContent = "×";
  delBtn.title = "删除";
  delBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    await deleteChat(item.id, archived);
  });
  actions.append(archiveBtn, delBtn);

  row.append(main, actions);
  row.addEventListener("click", () => loadChat(item.id, archived).catch((err) => toast(err.message, true)));
  return row;
}

function renderLists() {
  const active = $("chatList");
  active.innerHTML = "";
  if (!state.chats.length) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "还没有对话";
    active.appendChild(empty);
  } else {
    state.chats.forEach((item) => active.appendChild(chatRow(item, false)));
  }
  const archived = $("archiveList");
  archived.innerHTML = "";
  if (!state.archives.length) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "暂无归档";
    archived.appendChild(empty);
  } else {
    state.archives.forEach((item) => archived.appendChild(chatRow(item, true)));
  }
  updateStats();
}

async function refreshLists() {
  try {
    const [a, b] = await Promise.all([api("/api/chats"), api("/api/chats?archived=1")]);
    state.chats = a.items || [];
    state.archives = b.items || [];
    state.stats = a.stats || state.stats;
    renderLists();
  } catch (err) {
    console.warn("refresh chats failed", err);
  }
}

/* ============================================================
 * 消息渲染
 * ============================================================ */
function hideWelcome(hide) { WELCOME.hidden = !!hide; }
function scrollBottom() { MSG.scrollTop = MSG.scrollHeight; }

function addSources(container, sources) {
  if (!sources || !sources.length) return;
  const wrap = document.createElement("div");
  wrap.className = "sources";
  sources.forEach((s, i) => {
    const a = document.createElement("a");
    a.className = "source-chip";
    a.href = s.url;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.title = s.title || s.url;
    const n = document.createElement("b");
    n.textContent = String(i + 1);
    a.append(n, document.createTextNode(` ${s.title || s.url}`));
    wrap.appendChild(a);
  });
  container.appendChild(wrap);
}

function addMeta(container, msg) {
  const parts = [];
  if (msg.role === "user") {
    parts.push(sourceLabel(msg.source));
    if (msg.asr_ms) parts.push(`ASR ${Math.round(msg.asr_ms)}ms`);
  } else {
    if (msg.model) parts.push(msg.model);
    if (msg.tool_rounds) parts.push(`联网 ${msg.tool_rounds} 次`);
    if (msg.llm_ms != null) parts.push(`LLM ${Math.round(msg.llm_ms)}ms`);
    if (msg.tts_ms != null) parts.push(`合成 ${Math.round(msg.tts_ms)}ms`);
  }
  parts.push(formatTime(msg.created_at));
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = parts.filter(Boolean).join(" · ");
  container.appendChild(meta);
}

function messageElement(role, text, msg = {}) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "user") {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdown(text);
    addSources(bubble, msg.sources);
  }
  wrap.appendChild(bubble);
  addMeta(wrap, { role, ...msg });

  if (role === "assistant") {
    const tools = document.createElement("div");
    tools.className = "msg-tools";
    const copy = document.createElement("button");
    copy.className = "tool-btn";
    copy.textContent = "复制";
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(text); toast("已复制"); }
      catch { toast("复制失败", true); }
    });
    tools.appendChild(copy);
    if (msg.audio) {
      const replay = document.createElement("button");
      replay.className = "tool-btn";
      replay.textContent = "重播";
      replay.addEventListener("click", () => { playAudio(msg.audio); });
      tools.appendChild(replay);
    }
    wrap.appendChild(tools);
  }
  return wrap;
}

function addUser(text, source = "text", asrMs = 0) {
  hideWelcome(true);
  const row = messageElement("user", text, { source, asr_ms: asrMs, created_at: new Date().toISOString() });
  LOG.appendChild(row);
  scrollBottom();
  return row;
}

function addAssistant(text, data = {}) {
  hideWelcome(true);
  const row = messageElement("assistant", text, data);
  LOG.appendChild(row);
  scrollBottom();
  return row;
}

function addThinking() {
  hideWelcome(true);
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const think = document.createElement("span");
  think.className = "thinking";
  think.innerHTML = "<i></i><i></i><i></i><span>思考中</span>";
  bubble.appendChild(think);
  wrap.appendChild(bubble);
  LOG.appendChild(wrap);
  scrollBottom();
  return wrap;
}

function addError(text) {
  hideWelcome(true);
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  const bubble = document.createElement("div");
  bubble.className = "error-bubble";
  bubble.textContent = `⚠ ${text}`;
  wrap.appendChild(bubble);
  LOG.appendChild(wrap);
  scrollBottom();
  return wrap;
}

function clearMessages(showWelcome = true) {
  LOG.innerHTML = "";
  hideWelcome(!showWelcome);
}

/* ============================================================
 * 会话打开/新建
 * ============================================================ */
function setComposerEnabled(enabled) {
  $("textInput").disabled = !enabled;
  $("sendBtn").disabled = !enabled || state.busy || !$("textInput").value.trim();
  $("micBtn").disabled = !enabled;
  $("desktopBtn").disabled = !enabled;
  $("composer").classList.toggle("disabled", !enabled);
}

function applyMode(mode) {
  state.mode = mode === "companion" ? "companion" : "general";
  localStorage.setItem(LS.mode, state.mode);
  APP.classList.toggle("companion", state.mode === "companion");
  document.querySelectorAll("#modeSwitch button").forEach((btn) => {
    btn.classList.toggle("on", btn.dataset.mode === state.mode);
  });
  $("modeBadge").textContent = state.mode === "companion" ? "陪伴模式" : "通用模式";
  $("welcomeSub").textContent = state.mode === "companion"
    ? "按住 F2 说话，按 F3 开始/停止桌面音频。陪伴模式只支持语音输入，对话仍会保存。"
    : "输入文字，或按住 F2 说话；按 F3 开始/停止桌面音频。回答默认朗读。";
  $("textInput").placeholder = state.mode === "companion"
    ? "陪伴模式仅支持语音输入"
    : "发消息，Enter 发送，Shift+Enter 换行…";
}

function newChat() {
  state.currentId = null;
  state.archived = false;
  state.readOnly = false;
  localStorage.removeItem(LS.last);
  clearMessages(true);
  $("chatTitle").textContent = "新对话";
  $("readonlyBadge").hidden = true;
  setComposerEnabled(true);
  applyMode(state.mode);
  $("sendBtn").disabled = true; // 空输入不可发送
  $("textInput").focus();
}

async function loadChat(id, archived = false) {
  const data = await api(`/api/chats/${encodeURIComponent(id)}${archived ? "?archived=1" : ""}`);
  state.currentId = data.id;
  state.archived = archived;
  state.readOnly = archived;
  applyMode(data.mode || "general");
  $("chatTitle").textContent = data.title || "对话";
  $("readonlyBadge").hidden = !archived;
  clearMessages(false);
  if (archived) {
    const note = document.createElement("div");
    note.className = "readonly-note";
    note.textContent = "这条对话已归档，只读。可在左侧归档列表点 ↩ 恢复后继续。";
    LOG.appendChild(note);
  }
  for (const msg of data.messages || []) {
    if (msg.role === "user") {
      LOG.appendChild(messageElement("user", msg.text || "", msg));
    } else if (msg.role === "assistant") {
      LOG.appendChild(messageElement("assistant", msg.text || "", msg));
    }
  }
  setComposerEnabled(!archived);
  if (!archived) localStorage.setItem(LS.last, id);
  MSG.scrollTop = MSG.scrollHeight;
}

async function archiveChat(id) {
  const res = await api(`/api/chats/${encodeURIComponent(id)}/archive`, { method: "POST" });
  if (state.currentId === id) newChat();
  await refreshLists();
  if (res.purged && res.purged.length) toast(`归档已满，自动清理了 ${res.purged.length} 条最旧归档`);
  else toast("已归档");
}

async function restoreChat(id) {
  await api(`/api/chats/${encodeURIComponent(id)}/restore`, { method: "POST" });
  await refreshLists();
  if (state.currentId === id && state.archived) {
    await loadChat(id, false);
  }
  toast("已恢复到最近对话");
}

async function deleteChat(id, archived) {
  if (!window.confirm("确定删除这条对话？删除后不可恢复。")) return;
  try {
    await api(`/api/chats/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (state.currentId === id) newChat();
    await refreshLists();
    toast("已删除");
  } catch (err) { toast(err.message, true); }
}

/* ============================================================
 * 发送对话
 * ============================================================ */
async function submit(text, source = "text", asrMs = 0) {
  const value = String(text || "").trim();
  if (!value || state.busy || state.readOnly) return;
  if (state.mode === "companion" && source === "text") {
    toast("陪伴模式只支持语音输入", true);
    return;
  }
  state.busy = true;
  $("sendBtn").disabled = true;
  addUser(value, source, asrMs);
  const thinking = addThinking();
  const t0 = performance.now();
  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.currentId || "",
        text: value,
        mode: state.mode,
        speak: state.ttsOn,
        web: state.webOn,
        source,
        asr_ms: asrMs || 0,
      }),
    });
    thinking.remove();
    state.currentId = data.conversation_id;
    localStorage.setItem(LS.last, state.currentId);
    state.archived = false;
    state.readOnly = false;
    $("readonlyBadge").hidden = true;
    setComposerEnabled(true);
    if ($("chatTitle").textContent === "新对话") {
      $("chatTitle").textContent = value.slice(0, 24);
    }
    const msgData = {
      sources: data.sources || [],
      model: data.model,
      tool_rounds: data.tool_rounds,
      llm_ms: data.llm_ms,
      tts_ms: data.tts_ms,
      first_token_ms: data.first_token_ms,
      audio: data.audio || null,
      created_at: new Date().toISOString(),
    };
    addAssistant(data.reply || "（空回复）", msgData);
    if (data.tts_error) toast(`文字已保存；朗读失败：${data.tts_error}`, true);
    if (data.audio && state.ttsOn) playAudio(data.audio);
    await refreshLists();
    const end = Math.round(performance.now() - t0);
    $("connState").textContent = `联网工具 · ${data.web ? "已用" : "关"} · 端到端 ${end}ms`;
  } catch (err) {
    thinking.remove();
    addError(err.message || String(err));
    if (err.status === 409) toast("活跃对话已达 30 条，请先归档或删除", true);
    else if (err.status === 413) toast("单会话已达 1MB，请归档并新开", true);
    else toast(err.message || "请求失败", true);
  } finally {
    state.busy = false;
    $("sendBtn").disabled = state.readOnly || !$("textInput").value.trim();
    $("textInput").focus();
  }
}

/* ============================================================
 * TTS 播放
 * ============================================================ */
function playAudio(url) {
  if (!url) return;
  PLAYER.src = url;
  PLAYER.play().then(() => { $("stopTTS").hidden = false; }).catch(() => {
    toast("浏览器拦截了自动播放，点一下页面再试", true);
  });
}
function stopAudio() {
  try { PLAYER.pause(); PLAYER.currentTime = 0; } catch { /* ignore */ }
  $("stopTTS").hidden = true;
}
PLAYER.addEventListener("ended", () => { $("stopTTS").hidden = true; });
PLAYER.addEventListener("pause", () => { $("stopTTS").hidden = true; });

/* ============================================================
 * 录音：麦克风 / 桌面音频
 * ============================================================ */
const recorder = {
  ctx: null, stream: null, source: null, processor: null, mute: null,
  chunks: [], kind: null, startedAt: 0, timer: null, autoStop: null, keyHeld: false,
};

function ensureAudioContext() {
  if (!recorder.ctx) {
    recorder.ctx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return recorder.ctx;
}

function updateVoiceUI(kind) {
  const panel = $("voicePanel");
  const micBtn = $("micBtn");
  const desktopBtn = $("desktopBtn");
  if (kind) {
    panel.hidden = false;
    $("voiceText").textContent = kind === "mic" ? "正在听（麦克风）…" : "正在听（桌面音频）…";
    micBtn.classList.toggle("recording", kind === "mic");
    desktopBtn.classList.toggle("recording", kind === "desktop");
    micBtn.querySelector(".round-label").textContent = kind === "mic" ? "停止" : "语音";
    desktopBtn.querySelector(".round-label").textContent = kind === "desktop" ? "停止" : "桌面";
  } else {
    panel.hidden = true;
    micBtn.classList.remove("recording");
    desktopBtn.classList.remove("recording");
    micBtn.querySelector(".round-label").textContent = "语音";
    desktopBtn.querySelector(".round-label").textContent = "桌面";
  }
}

function resample16k(input, srcRate) {
  if (srcRate === 16000) return input;
  const n = Math.max(1, Math.floor(input.length * 16000 / srcRate));
  const out = new Float32Array(n);
  const ratio = srcRate / 16000;
  for (let i = 0; i < n; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const f = pos - i0;
    const a = input[i0] || 0;
    const b = input[Math.min(i0 + 1, input.length - 1)] || 0;
    out[i] = a * (1 - f) + b * f;
  }
  return out;
}

function toPcm16(input) {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const v = Math.max(-1, Math.min(1, input[i]));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out;
}

async function startRecording(kind) {
  if (state.readOnly || state.busy) return;
  if (recorder.stream) {
    await stopRecording(true);
    return;
  }
  stopAudio();
  let stream;
  try {
    if (kind === "desktop") {
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      if (!stream.getAudioTracks().length) {
        stream.getTracks().forEach((t) => t.stop());
        toast("没有捕获到系统音频。共享时请勾选“分享系统音频/音频”", true);
        return;
      }
      // 保留 video track：部分浏览器一旦停止 video，会连带终止整个共享会话/音频。
    } else {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    }
  } catch (err) {
    const name = err && err.name ? err.name : "Error";
    toast(name === "NotAllowedError" ? "麦克风/屏幕共享被拒绝，请检查浏览器权限" : `无法打开音频：${name}`, true);
    return;
  }

  const ctx = ensureAudioContext();
  try { await ctx.resume(); } catch { /* ignore */ }
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0;
  source.connect(processor);
  processor.connect(mute);
  mute.connect(ctx.destination);

  recorder.stream = stream;
  recorder.source = source;
  recorder.processor = processor;
  recorder.mute = mute;
  recorder.chunks = [];
  recorder.kind = kind;
  recorder.startedAt = performance.now();
  processor.onaudioprocess = (event) => {
    if (!recorder.stream) return;
    const data = event.inputBuffer.getChannelData(0);
    recorder.chunks.push(new Float32Array(data));
    // 最多录 30 秒
    const total = recorder.chunks.reduce((n, c) => n + c.length, 0);
    if (total > recorder.ctx.sampleRate * 30) stopRecording(true);
  };

  updateVoiceUI(kind);
  clearInterval(recorder.timer);
  recorder.timer = setInterval(() => {
    const sec = (performance.now() - recorder.startedAt) / 1000;
    $("voiceTimer").textContent = `${sec.toFixed(1)}s`;
  }, 100);
  recorder.autoStop = setTimeout(() => { if (recorder.stream) stopRecording(true); }, 30000);
}

async function stopRecording(send = true) {
  if (!recorder.stream) return;
  const kind = recorder.kind;
  const sampleRate = recorder.ctx.sampleRate;
  clearInterval(recorder.timer);
  clearTimeout(recorder.autoStop);
  recorder.timer = null;
  recorder.autoStop = null;

  try { recorder.processor.onaudioprocess = null; } catch { /* ignore */ }
  for (const node of [recorder.processor, recorder.source, recorder.mute]) {
    try { node && node.disconnect(); } catch { /* ignore */ }
  }
  recorder.stream.getTracks().forEach((t) => t.stop());
  const chunks = recorder.chunks;
  const started = recorder.startedAt;
  recorder.stream = null;
  recorder.source = null;
  recorder.processor = null;
  recorder.mute = null;
  recorder.chunks = [];
  recorder.kind = null;
  recorder.keyHeld = false;
  updateVoiceUI(null);

  const duration = (performance.now() - started) / 1000;
  if (!send || duration < 0.35) {
    if (send) toast("录音太短，已忽略");
    return;
  }

  let total = 0;
  for (const c of chunks) total += c.length;
  const merged = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) { merged.set(c, offset); offset += c.length; }

  const pcm = toPcm16(resample16k(merged, sampleRate));
  const panel = $("voicePanel");
  panel.hidden = false;
  $("voiceText").textContent = "正在转写…";
  $("voiceTimer").textContent = "";
  try {
    const res = await fetch("/api/asr", {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: pcm.buffer,
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
    const text = String(data.text || "").trim();
    if (!text) {
      toast("没有识别到文字，请再说一次", true);
      return;
    }
    await submit(text, kind, data.asr_ms || 0);
  } catch (err) {
    toast(`语音识别失败：${err.message || err}`, true);
  } finally {
    panel.hidden = true;
  }
}

async function toggleRecording(kind) {
  if (recorder.stream) {
    await stopRecording(true);
  } else {
    await startRecording(kind);
  }
}

async function toggleDesktopRecording() {
  if (recorder.stream) {
    if (recorder.kind === "desktop") {
      await stopRecording(true);
      return;
    }
    // 麦克风正在录时按 F3：丢弃当前麦克风录音，切换到桌面音频
    await stopRecording(false);
  }
  await startRecording("desktop");
}

/* ============================================================
 * 设置 / 事件
 * ============================================================ */
function syncSettingsUI() {
  $("ttsToggle").checked = state.ttsOn;
  $("webToggle").checked = state.webOn;
  $("connState").textContent = `联网工具 · ${state.webOn ? "开" : "关"}`;
}

async function showHealth() {
  try {
    const h = await api("/api/health");
    const store = h.store || {};
    toast(`ASR ${h.asr_loaded ? "✓" : "…"} · TTS ${h.tts_loaded ? "✓" : "…"} · 模型 ${h.model || h.default_model} · 会话 ${store.active || 0}/${(store.limits || {}).active || 30}`);
  } catch (err) { toast(`服务不可用：${err.message}`, true); }
}

function bind() {
  $("newChat").addEventListener("click", newChat);
  $("sendBtn").addEventListener("click", () => {
    const text = $("textInput").value.trim();
    if (!text) return;
    $("textInput").value = "";
    autoGrow();
    submit(text, "text", 0);
  });
  $("textInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $("sendBtn").click();
    }
  });
  $("textInput").addEventListener("input", () => {
    autoGrow();
    $("sendBtn").disabled = state.readOnly || state.busy || !$("textInput").value.trim();
  });
  $("micBtn").addEventListener("click", () => toggleRecording("mic"));
  $("desktopBtn").addEventListener("click", () => toggleRecording("desktop"));
  $("stopTTS").addEventListener("click", stopAudio);
  $("healthBtn").addEventListener("click", showHealth);
  $("ttsToggle").addEventListener("change", (e) => {
    state.ttsOn = e.target.checked;
    localStorage.setItem(LS.tts, state.ttsOn ? "1" : "0");
    if (!state.ttsOn) stopAudio();
  });
  $("webToggle").addEventListener("change", (e) => {
    state.webOn = e.target.checked;
    localStorage.setItem(LS.web, state.webOn ? "1" : "0");
    syncSettingsUI();
  });
  document.querySelectorAll("#modeSwitch button").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.mode === state.mode) return;
      applyMode(btn.dataset.mode);
      newChat();
      toast(btn.dataset.mode === "companion" ? "已切换到陪伴模式：只能用语音输入" : "已切换到通用模式");
    });
  });
  $("openSidebar").addEventListener("click", () => $("sidebar").classList.add("open"));
  $("closeSidebar").addEventListener("click", () => $("sidebar").classList.remove("open"));
  $("suggestions").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-text]");
    if (btn) submit(btn.dataset.text, "text", 0);
  });

  // 页面聚焦时的全局热键（浏览器无法注册系统级热键）
  // F2 = 按住说话；F3 = 按一下开始桌面录音，再按一下停止并发送。
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { stopAudio(); if (recorder.stream) stopRecording(false); return; }
    if (e.key === "F3") {
      e.preventDefault();
      if (e.repeat) return;
      toggleDesktopRecording();
      return;
    }
    if (e.key !== "F2") return;
    e.preventDefault();
    if (e.repeat) return;
    if (recorder.stream) {
      if (recorder.kind === "mic") recorder.keyHeld = true;
      return;
    }
    recorder.keyHeld = true;
    startRecording("mic");
  });
  window.addEventListener("keyup", (e) => {
    if (e.key !== "F2") return;
    if (recorder.stream && recorder.keyHeld) {
      recorder.keyHeld = false;
      stopRecording(true);
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && recorder.stream) stopRecording(false);
  });
  window.addEventListener("beforeunload", () => { try { stopAudio(); } catch { /* ignore */ } });
}

function autoGrow() {
  const el = $("textInput");
  el.style.height = "auto";
  el.style.height = `${Math.min(180, Math.max(34, el.scrollHeight))}px`;
}

async function init() {
  syncSettingsUI();
  applyMode(state.mode);
  bind();
  autoGrow();
  await refreshLists();
  const last = localStorage.getItem(LS.last);
  if (last && state.chats.some((c) => c.id === last)) {
    try { await loadChat(last, false); }
    catch { newChat(); }
  } else {
    newChat();
  }
  setComposerEnabled(!state.readOnly);
  $("textInput").focus();
}

init().catch((err) => {
  console.error(err);
  toast(`初始化失败：${err.message || err}`, true);
});
