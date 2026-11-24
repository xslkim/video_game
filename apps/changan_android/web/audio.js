"use strict";

// A single mixer keeps an effect or a line of dialogue from taking Android
// media focus away from the currently visible film.
let audioContext;
const audioBuffers = new Map();
function readAsset(path, binary = false) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", path, true);
    if (binary) xhr.responseType = "arraybuffer";
    xhr.onload = () => {
      if (xhr.status !== 200) return reject(Error("资源读取失败 " + path + " " + xhr.status));
      try { resolve(binary ? xhr.response : JSON.parse(xhr.responseText)); }
      catch (e) { reject(e); }
    };
    xhr.onerror = () => reject(Error("无法读取资源 " + path));
    xhr.send();
  });
}
function mixer() {
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  return audioContext;
}
function audioBuffer(url) {
  if (!audioBuffers.has(url)) {
    const load = readAsset(url, true)
                     .then(data => new Promise((resolve, reject) => mixer().decodeAudioData(data, resolve, reject)));
    audioBuffers.set(url, load);
    load.catch(() => audioBuffers.delete(url));
  }
  const value = audioBuffers.get(url);
  audioBuffers.delete(url);
  audioBuffers.set(url, value);
  if (audioBuffers.size > 12) audioBuffers.delete(audioBuffers.keys().next().value);
  return value;
}
class SoundDeck {
  constructor() {
    if (typeof LanternAudio !== "undefined") return new NativeSoundDeck();
    this.url = "";
    this.buffer = null;
    this.node = null;
    this.gain = null;
    this.position = 0;
    this.begun = 0;
    this.version = 0;
    this.level = 1;
    this.speed = 1;
    this.loop = false;
    this.paused = true;
    this.ended = false;
    this.dataset = {};
  }
  set src(url) {
    this.pause();
    this.buffer = null;
    this.url = url;
    this.position = 0;
    this.speed = 1;
    this.ended = false;
  }
  get src() {
    return this.url;
  }
  set volume(v) {
    this.level = v;
    if (this.gain) this.gain.gain.value = v;
  }
  get currentTime() {
    return this.position + (this.node ? (mixer().currentTime - this.begun) * this.speed : 0);
  }
  set currentTime(v) {
    const playing = !this.paused;
    this.pause();
    this.position = v;
    if (playing) this.play().catch(error);
  }
  set playbackRate(v) {
    if (this.node) {
      this.position = this.currentTime;
      this.begun = mixer().currentTime;
      this.node.playbackRate.value = v;
    }
    this.speed = v;
  }
  get playbackRate() {
    return this.speed;
  }
  pause() {
    this.version++;
    this.position = this.currentTime;
    if (this.node) {
      this.node.onended = null;
      this.node.stop();
      this.node.disconnect();
      this.node = null;
    }
    if (this.gain) {
      this.gain.disconnect();
      this.gain = null;
    }
    this.paused = true;
  }
  async play() {
    if (!this.url || !this.paused) return;
    const token = ++this.version, context = mixer();
    this.paused = false;
    try {
      if (context.resume) await context.resume();
      const buffer = this.buffer || await audioBuffer(this.url);
      if (token !== this.version) return;
      this.buffer = buffer;
      this.ended = false;
      const node = context.createBufferSource(), gain = context.createGain();
      node.buffer = buffer;
      node.loop = this.loop;
      node.playbackRate.value = this.speed;
      gain.gain.value = this.level;
      node.connect(gain);
      gain.connect(context.destination);
      this.node = node;
      this.gain = gain;
      this.begun = context.currentTime;
      this.position %= buffer.duration;
      node.onended = () => {
        if (this.node === node) {
          node.disconnect();
          gain.disconnect();
          this.node = this.gain = null;
          this.paused = this.ended = true;
          this.position = 0;
        }
      };
      node.start(0, this.position);
    } catch (e) {
      if (token === this.version) this.paused = true;
      throw e;
    }
  }
}

class NativeSoundDeck {
  constructor() {
    this.handle = 0; this.url = ""; this.position = 0; this.level = 1;
    this.loop = false; this.playbackRate = 1; this.dataset = {};
  }
  set src(url) { this.pause(); this.url = url; this.position = 0; }
  get src() { return this.url; }
  get ended() { return !!this.handle && !LanternAudio.active(this.handle); }
  get paused() { return !this.handle || this.ended; }
  set volume(value) { this.level = value; if (this.handle) LanternAudio.volume(this.handle, value); }
  get volume() { return this.level; }
  get currentTime() { return this.handle ? LanternAudio.position(this.handle) / 1000 : this.position; }
  set currentTime(value) { const resume = !this.paused; this.pause(); this.position = value; if (resume) this.play(); }
  play() {
    if (this.url && this.paused) this.handle = LanternAudio.start(this.url, Math.round(this.position * 1000), this.loop, this.level);
    return Promise.resolve();
  }
  pause() {
    if (this.handle) { this.position = this.currentTime; LanternAudio.stop(this.handle); this.handle = 0; }
  }
}
