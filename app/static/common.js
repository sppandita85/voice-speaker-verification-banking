// Shared helpers: a push-to-talk recorder and small fetch wrappers.

class Recorder {
  async start() {
    if (!this.stream) {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    }
    this.chunks = [];
    this.media = new MediaRecorder(this.stream);
    this.media.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.media.start();
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.media || this.media.state === "inactive") return resolve(null);
      this.media.onstop = () => resolve(new Blob(this.chunks, { type: this.media.mimeType || "audio/webm" }));
      this.media.stop();
    });
  }
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

async function postForm(url, form) {
  const r = await fetch(url, { method: "POST", body: form });
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

function playWav(b64) {
  if (!b64) return Promise.resolve();
  const audio = new Audio("data:audio/wav;base64," + b64);
  return audio.play().catch(() => {}); // autoplay can be blocked until the first click
}

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text) node.textContent = text;
  return node;
}

// Hold-to-talk on a button (mouse, touch, or the space bar).
function pushToTalk(button, onAudio) {
  const rec = new Recorder();
  let down = false;
  const start = async () => {
    if (down || button.disabled) return;
    down = true;
    try { await rec.start(); button.classList.add("recording"); button.dataset.label ??= button.textContent; button.textContent = "Recording… release to send"; }
    catch (e) { down = false; alert("Microphone not available: " + e.message); }
  };
  const stop = async () => {
    if (!down) return;
    down = false;
    button.classList.remove("recording");
    button.textContent = button.dataset.label;
    const blob = await rec.stop();
    if (blob && blob.size) onAudio(blob);
  };
  button.addEventListener("pointerdown", (e) => { e.preventDefault(); start(); });
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointerleave", stop);
  return { start, stop };
}
