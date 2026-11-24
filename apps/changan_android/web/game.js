"use strict";
const $ = id => document.getElementById(id);
const nativeFilm = typeof LanternFilm !== "undefined";
let filmAtlas = null, softwareFilm = false;
const htmlFilm = $("film");
const compatiblePlayer = {
  dataset: {},
  get currentTime() { return filmAtlas ? filmAtlas.frame / filmAtlas.data.fps : LanternFilm.milliseconds() / 1000; },
  get readyState() { return filmAtlas || LanternFilm.status() > 0 ? 4 : 0; },
  get ended() { return filmAtlas ? filmAtlas.ended : LanternFilm.status() === 3; },
  get paused() { return filmAtlas ? filmAtlas.paused : LanternFilm.status() === 2; },
  set volume(value) { if (filmAtlas) filmAtlas.audio.volume = value; else LanternFilm.volume(value); },
  set playbackRate(value) { if (filmAtlas) filmAtlas.rate = value; },
  pause() {
    if (filmAtlas) { filmAtlas.paused = true; filmAtlas.audio.pause(); }
    else LanternFilm.playing(false);
  },
  play() {
    if (filmAtlas) { filmAtlas.paused = false; return filmAtlas.audio.play(); }
    LanternFilm.playing(true); return Promise.resolve();
  }
};
let film = nativeFilm ? compatiblePlayer : htmlFilm;
const fx = $("effects"),
      ctx = fx.getContext("2d");
const profiles = {
  easy: {label: "简单", lives: 5, cap: 15, bonus: -1, margin: 24, reload: .4, warn: 1.4, flight: 1.3},
  normal: {label: "普通", lives: 3, cap: 20, bonus: 0, margin: 12, reload: .6, warn: 1, flight: 1},
  hard: {label: "困难", lives: 3, cap: 25, bonus: 1, margin: 0, reload: .8, warn: .65, flight: .7}
};
const diagnostic = new URL(location.href).searchParams.get("qa") || "";
const qa = diagnostic === "gun" ? "" : diagnostic;
let probeDecoderFailure = diagnostic === "codec";
const key = diagnostic ? "changan-campaign-qa-v1" : "changan-campaign-v1";
let bundle, stages, stage, current, index = 0, mode = "menu", paused = false, run = 0, gen = 0, gun = false;
let compose, streetTime = 0, clipAudio = new SoundDeck(), aim = {x: -1, y: -1}, particles = [],
             masks = new Map(), tracks = new Map(), last = performance.now();
let mainMusic = new SoundDeck(), voice = new SoundDeck(), musicName = "", saved = {}, difficulty = "normal",
    captions = true;
let score, health, charge, ammo, combo, reloadLeft = 0, manualMenu = null, viewFrame = -1,
                                        pauseOnReady = false;
let effectTime = 0;
let lowEffects = nativeFilm || (navigator.deviceMemory != null && navigator.deviceMemory <= 2);
let lastSurface = "";
const volumes = {
  music: .60,
  effects: .80,
  voice: 1
};
const freshScore = () => ({points: 0, hits: 0, shots: 0, combo: 0, damage: 0, purified: 0});
function info(msg) {
  console.info("CHANGAN " + msg);
}
window.addEventListener("error", event => info("ERROR " + event.message + " " + event.lineno));
window.addEventListener("unhandledrejection", event => info("ERROR " + String(event.reason)));
let stick = {x: 0, y: 0}, pad = false;
window.stickAim = (x, y) => {
  pad = true;
  stick = {x: Math.abs(x) > .13 ? x : 0, y: Math.abs(y) > .13 ? y : 0};
};
window.padAction = action => {
  pad = true;
  if (aim.x < 0) aim = {x: 640, y: 360};
  if (action === "start") {
    if (mode === "loading") pauseOnReady = true;
    else if (mode === "menu" || mode === "failure")
      $("begin").click();
    else
      setPaused(!paused);
    return;
  }
  if (paused || mode === "menu" || mode === "failure") {
    if (action === "shoot")
      (document.activeElement?.tagName === "BUTTON" ? document.activeElement : $("begin")).click();
    return;
  }
  if (action === "reload")
    reload();
  else if (action === "special")
    shoot(aim, true);
  else if (mode === "film")
    finishChoice("skip");
  else
    shoot(aim);
};
function show(id, yes) {
  if (id === "border") {
    $("gunBand").hidden = !yes;
    if (yes) sizeGunBorder();
  }
  if ((nativeFilm || softwareFilm) && id === "film") {
    if (nativeFilm) document.documentElement.classList.toggle("native-film", yes);
    yes = false;
  }
  $(id).hidden = !yes;
}
function sizeGunBorder() {
  const unit = $("screen").getBoundingClientRect().width / 1920;
  $("border").style.borderWidth = 24 * unit + "px";
  $("gunBand").style.boxShadow = "inset 0 0 0 " + 72 * unit + "px rgb(8,10,12)";
}
window.addEventListener("resize", sizeGunBorder);
function error(e) {
  mode = "menu";
  paused = true;
  for (const v of [film, clipAudio, voice, mainMusic]) v.pause();
  show("menu", true);
  $("details").textContent = "无法继续播放　" + e.message;
  info("ERROR " + (e.stack || e.name + " " + e.message));
}
const cueVisits = new Map();
function sound(name) {
  const index = cueVisits.get(name) || 0;
  cueVisits.set(name, (index + 1) % 3);
  const base = "foley/" + name, src = bundle.audio[base + "_" + (index + 1)] || bundle.audio[base];
  if (src) {
    const a = new SoundDeck();
    a.src = src;
    a.volume = volumes.effects;
    a.play().catch(() => {});
  }
}
function bgm(name) {
  if (!name) {
    mainMusic.pause();
    musicName = "";
    return;
  }
  if (name !== musicName) {
    const url = bundle.audio["music/" + name];
    if (!url) return;
    mainMusic.src = url;
    musicName = name;
    mainMusic.loop = true;
  }
  mainMusic.volume = volumes.music;
  if (!paused) mainMusic.play().catch(() => {});
}
function burst(p, kind) {
  particles.push({p: {...p}, kind, t: effectTime});
  sound(kind);
}
function buttons() {
  show("hud", mode === "trial" || mode === "combat" || mode === "film");
  show("actions", mode === "film" || mode === "combat" || (mode === "trial" && current && !current.story));
  $("actions").classList.toggle("cinema", mode === "film");
  show("thunder", mode !== "film");
  show("skip", mode === "film");
  show("border", gun);
}
function refresh() {
  const pf = profiles[difficulty];
  $("difficulty").textContent = (saved.next && saved.next !== "@complete" ? "新局难度　" : "难度　") + pf.label;
  $("captions").textContent = "字幕　" + (captions ? "开" : "关");
  $("gun").textContent = "TVGun　" + (gun ? "开" : "关");
  $("quality").textContent = "画质　" + (lowEffects ? "省电" : "标准");
  for (const [id, label] of Object.entries({music: "配乐", effects: "音效", voice: "对白"}))
    $(id + "Volume").textContent = label + " " + Math.round(volumes[id] * 100) + "%";
  if (score)
    $("status").textContent = "生命 " + health + "　 符箭 " + ammo + "/8　 雷符 " + charge + "/" + pf.cap +
        "　 " + score.points + " 分";
}
function title() {
  pauseOnReady = false;
  mode = "menu";
  paused = false;
  current = null;
  lastSurface = "";
  aim = {x: -1, y: -1};
  particles = [];
  voice.pause();
  bgm(saved.next === "@complete" ? "credits" : "title");
  film.pause();
  show("film", false);
  show("composite", false);
  show("subtitle", false);
  show("instruction", false);
  buttons();
  show("menu", true);
  show("prefs", true);
  const completed = saved.next === "@complete", resume = saved.next && !completed;
  $("chapter").textContent =
      completed ? "上元灯记" : (stages.find(s => s.id === saved.next) || stages[0]).heading;
  $("begin").textContent = resume ? "继续巡灯" : "开始巡灯";
  show("new", !!resume);
  if (completed) {
    const all = Object.values(saved.scores || {}), total = freshScore();
    for (const s of all)
      for (const k of Object.keys(total))
        total[k] = k === "combo" ? Math.max(s[k], total[k]) : total[k] + s[k];
    $("details").textContent = "五章巡灯已毕　总评 " + grade(total) + "　总得分 " + total.points + "　" +
        all.map(s => s.grade || "").join(" · ");
  } else
    $("details").textContent = resume ? "继续巡灯　" + profiles[saved.difficulty || "normal"].label + "难度" : "";
  refresh();
  $("begin").focus();
}
function prefs() {
  localStorage.setItem(key + "-options", JSON.stringify({difficulty, captions, volumes, lowEffects}));
}
function sizeCanvases() {
  const canvas = $("composite");
  canvas.width = lowEffects ? 640 : 960;
  canvas.height = lowEffects ? 360 : 540;
  fx.width = lowEffects ? 640 : 1280;
  fx.height = lowEffects ? 360 : 720;
  ctx.setTransform(fx.width / 1280, 0, 0, fx.height / 720, 0, 0);
}
$("quality").onclick = () => {
  lowEffects = !lowEffects;
  sizeCanvases();
  prefs();
  refresh();
};
for (const id of Object.keys(volumes))
  $(id + "Volume").onclick = () => {
    volumes[id] = ((Math.round(volumes[id] * 100) + 20) % 120) / 100;
    mainMusic.volume = volumes.music;
    clipAudio.volume = volumes.effects;
    voice.volume = volumes.voice;
    prefs();
    refresh();
  };
function persist(next) {
  saved.next = next;
  saved.difficulty = difficulty;
  saved.health = health;
  saved.charge = charge;
  saved.arrows = ammo;
  saved.reloadRemaining = reloadLeft;
  saved.scores[stage.chapter] = Object.assign({}, score);
  localStorage.setItem(key, JSON.stringify(saved));
  info("checkpoint " + next);
}
function grade(s) {
  const a = s.hits / Math.max(1, s.shots);
  return a >= .9 && !s.damage && s.purified ? "S" : a >= .75 && s.damage <= 2 ? "A" : a >= .5 ? "B" : "C";
}
function setPaused(yes) {
  if (!["combat", "trial", "film"].includes(mode) || paused === yes) return;
  paused = yes;
  if (!yes && current) current.progressAt = performance.now();
  for (const v of [film, clipAudio, mainMusic, voice]) {
    if (yes) {
      v.dataset.resume = !v.paused && !v.ended ? "1" : "";
      v.pause();
    } else if (v.dataset.resume === "1") {
      Promise.resolve(v.play()).catch(e => {
        if (v === film && current?.video === film) current.progressAt = -1000000;
        else error(e);
      });
      v.dataset.resume = "";
    }
  }
  show("menu", yes);
  show("prefs", false);
  if (yes) {
    $("chapter").textContent = stage.heading;
    $("details").textContent = "巡灯暂停";
    $("begin").textContent = "继续";
    $("new").textContent = "返回标题";
    show("new", true);
  }
}
window.pauseGame = () => {
  if (mode === "loading")
    pauseOnReady = true;
  else
    setPaused(true);
};
window.togglePause = () => setPaused(!paused);
function menuDecision(label, detail) {
  mode = "failure";
  show("menu", true);
  buttons();
  show("prefs", false);
  show("new", true);
  $("begin").textContent = label;
  $("new").textContent = "返回标题";
  $("details").textContent = detail;
  if (qa) return Promise.resolve(true);
  return new Promise(resolve => {
    manualMenu = resolve;
  });
}
function abandon() {
  run++;
  gen++;
  if (current && current.resolve) current.resolve("quit");
  if (manualMenu) {
    manualMenu(false);
    manualMenu = null;
  }
  title();
}
function goNew() {
  saved = {next: stages[0].id, difficulty, health: profiles[difficulty].lives, charge: 0, scores: {}};
  localStorage.setItem(key, JSON.stringify(saved));
  launch();
}
$("begin").onclick = () => {
  if (manualMenu) {
    manualMenu(true);
    manualMenu = null;
    show("menu", false);
    return;
  }
  if (paused) {
    setPaused(false);
    return;
  }
  if (saved.next && saved.next !== "@complete")
    launch();
  else
    goNew();
};
$("new").onclick = () => {
  if (paused || mode === "failure") {
    abandon();
    return;
  }
  goNew();
};
$("difficulty").onclick = () => {
  difficulty = Object.keys(profiles)[(Object.keys(profiles).indexOf(difficulty) + 1) % 3];
  if (saved.next === "@complete") saved.difficulty = difficulty;
  prefs();
  refresh();
};
$("captions").onclick = () => {
  captions = !captions;
  prefs();
  refresh();
};
$("gun").onclick = () => {
  const next = !gun;
  if (!window.LanternDevice || window.LanternDevice.gunMode(next)) {
    gun = next;
    buttons();
    refresh();
  }
};
$("pause").onclick = () => setPaused(true);
$("reload").onclick = reload;
$("thunder").onclick = () => shoot(aim, true);
$("skip").onclick = () => {
  if (mode === "film" && current) current.resolve("skip");
};
function waitFor(v, event) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => finish(Error("媒体加载超时 " + v.currentSrc)), 20000);
    function finish(e) {
      clearTimeout(timer);
      v.removeEventListener(event, ok);
      v.removeEventListener("error", bad);
      if (e)
        reject(e);
      else
        resolve();
    }
    const ok = () => finish(),
          bad = () => finish(Error("媒体解码失败 " + v.currentSrc + " " + v.error?.code));
    v.addEventListener(event, ok, {once: true});
    v.addEventListener("error", bad, {once: true});
  });
}
async function startVideo(v, url, label, offset = 0) {
  const requested = performance.now();
  if (nativeFilm || softwareFilm) {
    if (!softwareFilm) {
      LanternFilm.open(url, Math.round(offset * 1000 / 24));
      while (performance.now() - requested < 3000 && LanternFilm.status() >= 0 &&
             LanternFilm.milliseconds() <= Math.round(offset * 1000 / 24))
        await new Promise(resolve => setTimeout(resolve, 32));
      softwareFilm = LanternFilm.status() < 0 || LanternFilm.milliseconds() <= Math.round(offset * 1000 / 24);
    }
    if (softwareFilm) {
      if (nativeFilm) LanternFilm.playing(false);
      else {
        htmlFilm.pause();
        if (htmlFilm.frameCallback != null) {
          htmlFilm.cancelVideoFrameCallback(htmlFilm.frameCallback);
          htmlFilm.frameCallback = null;
        }
        if (htmlFilm.hasAttribute("src")) { htmlFilm.removeAttribute("src"); htmlFilm.load(); }
        show("film", false);
      }
      if (filmAtlas) filmAtlas.audio.pause();
      const data = bundle.legacyFilms[label], frame = Math.min(data.frames - 1, Math.floor(offset * data.fps / 24));
      await atlasPage(data.pages[Math.floor(frame / 12)]).ready;
      drawAtlas(compose, data, frame);
      filmAtlas = {data, frame, playhead: frame, rate: 1, audio: new SoundDeck(), paused: false, ended: false};
      film = compatiblePlayer;
      filmAtlas.audio.src = data.audio;
      filmAtlas.audio.currentTime = frame / data.fps;
      filmAtlas.audio.play().catch(() => {});
    }
    if (qa) info("firstFrame " + (softwareFilm ? "filmAtlas" : "native") + " " + label + " " +
                 Math.round(performance.now() - requested));
    if (paused) film.pause();
    return;
  }
  try {
    await openHtmlVideo(v, url, label, offset, requested);
  } catch (e) {
    softwareFilm = true;
    info("decoderFallback " + label + " " + (e.message || e));
    await startVideo(v, url, label, offset);
  }
}
async function openHtmlVideo(v, url, label, offset, requested) {
  if (v.frameCallback != null) v.cancelVideoFrameCallback(v.frameCallback);
  v.presentedFrame = null;
  const ready = waitFor(v, "loadeddata");
  // In this explicit QA route a non-video asset exercises the real media error event.
  if (probeDecoderFailure && label === "tower_crow_pass_3") {
    probeDecoderFailure = false;
    v.src = "poster.jpg";
  } else v.src = url;
  v.load();
  await ready;
  if (offset) {
    const seek = waitFor(v, "seeked");
    v.currentTime = offset / 24;
    await seek;
  }
  if (v.requestVideoFrameCallback) {
    const shown = (_, meta) => {
      if (qa && v.presentedFrame == null) info("firstFrame video " + label + " " + Math.round(performance.now() - requested));
      v.presentedFrame = Math.max(0, Math.round(meta.mediaTime * 24));
      v.frameCallback = v.requestVideoFrameCallback(shown);
    };
    v.frameCallback = v.requestVideoFrameCallback(shown);
  }
  v.playbackRate = 1;
  let alarm;
  try {
    await Promise.race([v.play(), new Promise((_, reject) => {
      alarm = setTimeout(() => reject(Error("视频播放未开始")), 5000);
    })]);
  } finally { clearTimeout(alarm); }
  if (paused) v.pause();
}
function frameOf(v) {
  return v.presentedFrame ?? Math.max(0, Math.floor(v.currentTime * 24 + .0001));
}
function finishChoice(value) {
  if (current?.resolve) current.resolve(value);
}
function holdScene() {
  if (!compose) compose = $("composite").getContext("2d", {alpha: false});
  if (!nativeFilm && !film.error && lastSurface === "film" && film.readyState >= 2 && film.videoWidth)
    compose.drawImage(film, 0, 0, compose.canvas.width, compose.canvas.height);
  show("composite", !!lastSurface && (!nativeFilm || lastSurface === "atlas"));
}
async function oneFilm(id, subtitle = "", speech = "", choice = null) {
  const serial = ++gen;
  mode = "loading";
  const source = bundle.films[id];
  if (!source) throw Error("未找到镜头 " + id);
  holdScene();
  show("film", true);
  show("instruction", false);
  show("subtitle", !!(subtitle && captions));
  $("subtitle").textContent = subtitle;
  await startVideo(film, source, id);
  if (serial !== gen) return "quit";
  lastSurface = filmAtlas ? "atlas" : "film";
  show("composite", !!filmAtlas);
  film.volume = id === "aying_help" ? volumes.voice : volumes.effects;
  voice.pause();
  if (speech && bundle.audio["voice/" + speech]) {
    voice.src = bundle.audio["voice/" + speech];
    voice.volume = volumes.voice;
    voice.play().catch(() => {});
  }
  mode = choice ? "trial" : "film";
  if (qa) info("film " + id);
  current = choice || {};
  current.video = film;
  current.filmId = id;
  viewFrame = 0;
  buttons();
  refresh();
  if (pauseOnReady) {
    pauseOnReady = false;
    setPaused(true);
  }
  const outcome = await new Promise(resolve => {
    current.resolve = result => {
      current.resolve = null;
      resolve(result);
    };
  });
  if (serial !== gen) return "quit";
  voice.pause();
  film.pause();
  show("instruction", false);
  show("subtitle", false);
  current = null;
  return outcome;
}
async function readRegions(id) {
  const data = tracks.get(id) || await readAsset(bundle.regions[id]);
  tracks.delete(id);
  tracks.set(id, data);
  if (tracks.size > 8) tracks.delete(tracks.keys().next().value);
  return data;
}
async function loadMasks(bank) {
  if (masks.has(bank)) return masks.get(bank);
  const data = bundle.banks[bank], result = {};
  await Promise.all(
      Object.entries(data.level.clips).filter(([, c]) => c.windows?.length).map(async ([id, c]) => {
        result[id] = readMask(await readAsset("masks/" + bank + "/" + id + ".mask", true), c);
      }));
  masks.set(bank, result);
  return result;
}
function reload() {
  if (paused || ammo === 8 || reloadLeft > 0 ||
      !(mode === "film" || mode === "combat" || (mode === "trial" && !current?.story)))
    return;
  reloadLeft = profiles[difficulty].reload;
  sound("reload");
}
function polygonFor(choice, id, f) {
  const keyframes = choice.regions[id];
  return keyframes[Math.min(Math.max(f, 0), keyframes.length - 1)].polygon;
}
function center(poly) {
  return {
    x: poly.reduce((s, p) => s + p[0], 0) / poly.length,
    y: poly.reduce((s, p) => s + p[1], 0) / poly.length
  };
}
function allowedZone(choice, id, f) {
  const w = choice.step.zone_windows?.[id];
  return !w || (f >= w[0] && f < w[1]);
}
function shoot(p, special = false, when = performance.now()) {
  if (paused || !current || !current.resolve || (!current.story && reloadLeft > 0) || current.pending || current.recovering) return;
  const r = profiles[difficulty];
  let f = viewFrame;
  if (current.presented?.length) {
    const shown = [...current.presented].reverse().find(sample => sample.time <= when);
    if (!shown) return;
    f = shown.frame;
  }
  if (mode === "trial") {
    const t = current;
    if (f < t.begin || f >= t.end) return;
    if (performance.now() - (t.lastHit ?? -1000) < 150) return;
    if (special) {
      if (t.story || t.spent || charge !== r.cap || !allowedZone(t, t.step.answer, f)) return;
      if (!t.step.expose && !t.step.thunder_strike) return;
      t.spent = true;
      charge = 0;
      burst(center(polygonFor(t, t.step.answer, f)), "special");
      if (t.step.expose) {
        t.exposed = true;
        if (nativeFilm) {
          t.holdUntil = effectTime + Math.max(0, 3000 - (t.end - f) * 1000 / 24);
          film.pause();
        } else film.playbackRate = Math.min(1, (t.end - f) / 72);
      } else {
        t.specialDamage = Math.min(2, (t.step.strength || 1) - (t.partial || 0));
        if ((t.partial || 0) + t.specialDamage >= (t.step.strength || 1)) {
          t.specialFinish = true;
          deferHit(t, t.step.answer, 270);
        }
      }
      refresh();
      return;
    }
    if (!t.story) {
      if (!ammo) {
        sound("ready");
        return;
      }
      ammo--;
    }
    score.shots++;
    sound("shot");
    let region =
        t.step.zones.find(id => allowedZone(t, id, f) && inPolygon(polygonFor(t, id, f), p)) || "miss";
    if (region === "miss" && r.margin)
      region = t.step.zones.find(
                   id => t.step.outcomes[id].points > 0 && allowedZone(t, id, f) &&
                       nearPolygon(polygonFor(t, id, f), p, r.margin)) ||
          "miss";
    if (!t.story && (region === "miss" || t.step.guards?.includes(region))) {
      combo = 0;
      charge = Math.max(0, charge - 2);
      burst(p, "miss");
      refresh();
      return;
    }
    if (!t.story && region === t.step.answer &&
        (t.partial || 0) + (t.specialDamage || 0) + 1 < (t.step.strength || 1)) {
      t.partial = (t.partial || 0) + 1;
      t.lastHit = performance.now();
      score.hits++;
      score.points += 25;
      score.combo = Math.max(score.combo, ++combo);
      charge = Math.min(r.cap, charge + 1);
      burst(p, "hit");
      refresh();
      return;
    }
    t.hitFrame = f;
    burst(p, region === "miss" ? "miss" : "hit");
    deferHit(t, region, 270);
    return;
  }
  if (mode !== "combat") return;
  const c = current, w = c.clip.windows?.find(v => v.begin <= f && f < v.end && v.node === c.match.node);
  if (!w) return;
  const m = c.match, n = c.level.nodes[m.node];
  if (special && (charge < r.cap || w.kind !== "target")) return;
  if (!special) {
    if (!ammo) {
      sound("ready");
      return;
    }
    ammo--;
    score.shots++;
    sound("shot");
    if (!hitsMask(
            c.spans?.[f] || [], p,
            w.kind === "civilian" ? 0 : (c.level.selectable_difficulty ? r.margin : 0))) {
      combo = 0;
      charge = Math.max(0, charge - 2);
      burst(p, "miss");
      refresh();
      return;
    }
    if (w.kind === "civilian") {
      combo = charge = 0;
      score.points = Math.max(0, score.points - 100);
      if (difficulty !== "easy") {
        health--;
        score.damage++;
      }
      burst(p, "civilian");
      c.resolve(health > 0 ? w.hit : "@failed");
      return;
    }
    score.hits++;
    score.combo = Math.max(score.combo, ++combo);
    charge = Math.min(r.cap, charge + 1);
  } else
    charge = 0;
  let next = w.hit, cue = "intercept";
  if (w.kind === "projectile")
    score.points += 150;
  else {
    m.hp -= special ? 2 : 1;
    cue = special ? "special" : "hit";
    if (m.hp > 0)
      next = n.flinch;
    else {
      score.purified++;
      const speed = 1 + .5 * Math.max(0, 1 - (performance.now() - m.open) / 1800);
      score.points +=
          Math.round(n.score * (c.level.selectable_difficulty ? speed * Math.min(3, 1 + .05 * combo) : 1));
      m.node++;
      m.open = 0;
      m.hp = c.level.nodes[m.node] ? strength(c.level.nodes[m.node]) : 0;
      cue = special ? "special" : "purify";
    }
  }
  burst(p, cue);
  refresh();
  clipAudio.pause();
  deferHit(c, next, n.hp > 1 ? 120 : 50);
}
function deferHit(scene, outcome, delay) {
  scene.pending = true;
  scene.outcome = outcome;
  scene.finishAt = effectTime + delay;
}
function strength(node) {
  return node.hp > 1 ? Math.max(1, node.hp + profiles[difficulty].bonus) : 1;
}
function hitPoint(spans) {
  const row = spans[Math.floor(spans.length / 2)];
  return {x: row[1] + row[2], y: 2 * row[0] + 1};
}
async function combat(bank, token) {
  const b = bundle.banks[bank], level = b.level, regions = await loadMasks(bank);
  if (token !== run) return false;
  const match = {node: 0, hp: strength(level.nodes[0]), open: 0};
  let id = level.first;
  mode = "loading";
  holdScene();
  show("film", false);
  show("composite", true);
  show("subtitle", false);
  show("instruction", true);
  streetTime = 0;
  await atlasPage(b.street.pages[0]).ready;
  combo = 0;
  try {
    while (id !== "@complete" && id !== "@failed" && token === run) {
      let clip = level.clips[id];
      const threshold = clip.minimum_difficulty || "easy";
      if (Object.keys(profiles).indexOf(difficulty) < Object.keys(profiles).indexOf(threshold)) {
        id = clip.next;
        continue;
      }
      mode = "loading";
      const requested = performance.now();
      const sequence = b.layers[clip.media || id], start = clip.start || 0;
      await atlasPage(sequence.pages[Math.floor(start / 12)]).ready;
      const next = level.clips[clip.next];
      if (next) {
        const ahead = b.layers[next.media || clip.next];
        atlasPage(ahead.pages[Math.floor((next.start || 0) / 12)]).ready.catch(error);
      }
      clipAudio.src = sequence.audio;
      clipAudio.currentTime = start / 24;
      clipAudio.volume = volumes.effects;
      clipAudio.play().catch(() => {});
      if (token !== run) break;
      const c = {
        level,
        clip,
        match,
        spans: regions[id],
        struck: false,
        pending: false,
        bank: b,
        sequence,
        requested,
        label: id,
        playhead: start,
        rate: 1
      };
      if (qa) info("clip " + id + " node " + match.node + " health " + health);
      current = c;
      mode = "combat";
      viewFrame = clip.start || 0;
      buttons();
      refresh();
      show("instruction", true);
      if (pauseOnReady) {
        pauseOnReady = false;
        setPaused(true);
      }
      id = await new Promise(resolve => {
        c.resolve = v => {
          c.resolve = null;
          resolve(v);
        };
      });
      if (id === "quit") break;
    }
  } finally {
    clipAudio.pause();
    current = null;
    show("composite", false);
    show("instruction", false);
  }
  return id === "@complete";
}
async function trial(def, token) {
  let step = def.first, safeRescue = true;
  combo = 0;
  while (step !== "@complete" && token === run) {
    const s = def.steps[step], story = !!s.story_shot, begin = s.window[0];
    const region = await readRegions(s.take);
    const frames = region.regions[s.answer].length;
    const length = story ? ({easy: 72, normal: 48, hard: 29})[difficulty] :
        Math.min(frames - begin - 1, Math.round(s.window[1] * profiles[difficulty][s.projectile ? "flight" : "warn"]));
    const c = {step: s, story, begin, end: begin + length, regions: region.regions};
    const result = await oneFilm(s.take, s.subtitle || "", s.voice || "", c);
    if (qa) info("trial " + step + " " + result + " arrows " + ammo);
    if (token !== run || result === "quit") return false;
    const edge = s.outcomes[result] || s.outcomes.timeout;
    if (edge.civilian) sound("civilian");
    else if (edge.damage) sound("hurt");
    else if (edge.points && s.projectile) sound("intercept");
    else if (edge.purified) sound("purify");
    if (edge.civilian) {
      safeRescue = false;
      score.points = Math.max(0, score.points - 100);
      combo = charge = 0;
    }
    if (edge.damage && !(edge.civilian && difficulty === "easy")) {
      health -= edge.damage;
      score.damage += edge.damage;
      combo = charge = 0;
    }
    if (edge.points) {
      let award = edge.points;
      if (!c.specialFinish) score.hits++;
      if (!story && edge.purified && !c.specialFinish) {
        const reaction = 1 + .5 * Math.max(0, Math.min(1, 1 - (c.hitFrame - begin) / length));
        award =
            Math.round((award + (award === 500 ? 200 : 0)) * reaction * Math.min(3, 1 + .05 * (combo + 1)));
      }
      score.points += award;
      score.purified += edge.purified || 0;
      if (!story && !c.specialFinish) {
        score.combo = Math.max(score.combo, ++combo);
        charge = Math.min(profiles[difficulty].cap, charge + 1);
      }
    }
    if (!health) return false;
    if (edge.response) await oneFilm(edge.response);
    step = edge.next;
  }
  if (step === "@complete" && safeRescue) score.points += def.rescue_bonus || 0;
  return step === "@complete";
}
async function launch() {
  const token = ++run;
  try {
    paused = false;
    show("menu", false);
    difficulty = saved.difficulty || difficulty;
    health = saved.health || profiles[difficulty].lives;
    charge = saved.charge || 0;
    ammo = saved.arrows ?? 8;
    reloadLeft = saved.reloadRemaining || 0;
    index = stages.findIndex(s => s.id === saved.next);
    if (index < 0) index = 0;
    while (index < stages.length && run === token) {
      stage = stages[index];
      score = {...freshScore(), ...(saved.scores[stage.chapter] || {})};
      const before = {...score};
      let ok = true;
      bgm(stage.music || (stage.level === "a1" ? "festival" : ""));
      if (stage.type === "film") {
        for (const shot of stage.takes) {
          const result = await oneFilm(shot.id, shot.subtitle, shot.voice);
          if (result !== "ended" || token !== run) break;
        }
      } else if (stage.type === "encounter")
        ok = await combat(stage.level, token);
      else
        ok = await trial(stage.trial, token);
      if (token !== run) break;
      if (!ok) {
        if (!await menuDecision("重试此段", "灯火熄灭。")) {
          abandon();
          return;
        }
        score = before;
        charge = 0;
        ammo = 8;
        reloadLeft = 0;
        health = profiles[difficulty].lives;
        show("menu", false);
        continue;
      }
      score.grade = grade(score);
      index++;
      if (stages[index] && stages[index].chapter !== stage.chapter) {
        health = profiles[difficulty].lives;
        ammo = 8;
        reloadLeft = 0;
      }
      persist(stages[index]?.id || "@complete");
      if (!stages[index] || stages[index].chapter !== stage.chapter) {
        const accuracy = Math.round(100 * score.hits / Math.max(1, score.shots));
        $("chapter").textContent = stage.heading;
        const summary = "评级 " + score.grade + "　得分 " + score.points + "　命中率 " + accuracy +
            "%　最高连击 " + score.combo + "　受伤 " + score.damage + "　净化 " + score.purified;
        if (!await menuDecision("继续巡灯", summary)) {
          abandon();
          return;
        }
        show("menu", false);
      }
    }
    if (token === run) {
      title();
      info("complete");
    }
  } catch (e) {
    if (token === run) error(e);
  }
}
function tick(t) {
  const delta = Math.min(.1, (t - last) / 1000);
  last = t;
  if (pad && !paused && (stick.x || stick.y)) {
    if (aim.x < 0) aim = {x: 640, y: 360};
    aim.x = Math.max(0, Math.min(1279, aim.x + stick.x * delta * 790));
    aim.y = Math.max(0, Math.min(719, aim.y + stick.y * delta * 790));
  }
  if (!paused && reloadLeft > 0 && ["film", "trial", "combat"].includes(mode)) {
    reloadLeft = Math.max(0, reloadLeft - delta);
    if (!reloadLeft) {
      ammo = 8;
      sound("ready");
      refresh();
    }
  }
  const c = current;
  if (!paused) effectTime += delta * 1000;
  if (c?.resolve && c.pending && !paused && effectTime >= c.finishAt) c.resolve(c.outcome);
  if (c && c.resolve && !paused) {
    if (mode === "combat") {
      const next = Math.min(c.sequence.frames - 1, Math.floor(c.playhead));
      const bg = Math.min(c.bank.street.frames - 1, Math.floor(streetTime * c.bank.street.fps));
      const color = atlasPage(c.sequence.pages[Math.floor(next / 12)]);
      const back = atlasPage(c.bank.street.pages[Math.floor(bg / 12)]);
      if (color.img.complete && color.img.naturalWidth && back.img.complete && back.img.naturalWidth) {
        drawAtlas(compose, c.bank.street, bg);
        drawAtlas(compose, c.sequence, next);
        lastSurface = "atlas";
        if (qa && c.requested != null) {
          info("firstFrame atlas " + c.label + " " + Math.round(performance.now() - c.requested));
          c.requested = null;
        }
        viewFrame = next;
        if (!c.pending) c.playhead += delta * 24 * c.rate;
        streetTime += delta;
      }
    } else if (!c.recovering) {
      if (filmAtlas && !filmAtlas.paused && !filmAtlas.ended) {
        const a = filmAtlas, next = Math.min(a.data.frames - 1, Math.floor(a.playhead));
        if (drawAtlas(compose, a.data, next)) {
          a.frame = next;
          a.playhead += delta * a.data.fps * a.rate;
          a.ended = a.playhead >= a.data.frames;
        }
      }
      viewFrame = frameOf(c.video);
      if (c.holdUntil && effectTime >= c.holdUntil) {
        c.holdUntil = 0;
        c.video.play();
      }
      if (c.lastMediaTime !== c.video.currentTime || c.pending || c.holdUntil || c.video.ended) {
        c.lastMediaTime = c.video.currentTime;
        c.progressAt = t;
      } else if (t - c.progressAt > 2500) {
        // Switch presentation at the last displayed frame without reapplying the encounter.
        c.recovering = true;
        const offset = Math.max(0, viewFrame);
        info("recoverVideo " + c.filmId + " " + offset);
        holdScene();
        softwareFilm = true;
        startVideo(c.video, bundle.films[c.filmId], c.filmId, offset).then(() => {
          if (current !== c) return;
          c.video = film;
          c.recovering = false;
          c.progressAt = performance.now();
          if (filmAtlas) lastSurface = "atlas";
          show("composite", !!filmAtlas);
        }).catch(e => { if (current === c) error(e); });
      } else if (c.video.paused && !c.video.ended && !c.pending && t - (c.resumeAt || 0) > 1200) {
        c.resumeAt = t;
        Promise.resolve(c.video.play()).catch(() => { c.progressAt = -1000000; });
      }
    }
    if (!c.presented) c.presented = [];
    if (!c.presented.length || c.presented[c.presented.length - 1].frame !== viewFrame)
      c.presented.push({time: t, frame: viewFrame});
    while (c.presented.length > 1 && c.presented[1].time < t - 300) c.presented.shift();

    if (mode === "film" && film.ended && (!voice.src || voice.paused || voice.ended)) c.resolve("ended");
    if (mode === "trial") {
      const active = viewFrame >= c.begin && viewFrame < c.end;
      if (active) show("subtitle", false);
      if (qa && !c.story && ammo < (c.step.strength || 1) - (c.partial || 0) - (c.specialDamage || 0))
        reload();
      show("instruction", active);
      $("instruction").textContent = c.step.prompt +
          (c.step.strength > 1 ?
               "　符印 " + ((c.partial || 0) + (c.specialDamage || 0)) + "/" + c.step.strength :
               "");
      if (!c.pending && (viewFrame >= c.end || film.ended))
        c.resolve("timeout");
      else if (
          qa && !c.pending && active && viewFrame >= c.begin + 4 &&
          allowedZone(c, c.step.answer, viewFrame)) {
        if (!ammo && !c.story)
          reload();
        else
          shoot(center(polygonFor(c, c.step.answer, viewFrame)));
      }
    }
    if (mode === "combat") {
      const clip = c.clip,
            w = clip.windows?.find(v => v.begin <= viewFrame && viewFrame < v.end && v.node === c.match.node);
      const r = profiles[difficulty], f = viewFrame, m = c.match, n = c.level.nodes[m.node];
      const rate = clip.impact_frame != null &&
              f >= (clip.warning_frame ?? Math.max(0, clip.impact_frame - 14)) && f < clip.impact_frame ?
          1 / (clip.launch_frame != null && f >= clip.launch_frame ? r.flight : r.warn) :
          1;
      if (c.rate !== rate) {
        c.rate = rate;
        clipAudio.playbackRate = rate;
      }
      $("instruction").textContent = w?.kind === "civilian" ? "百姓经过　收弩" :
          w?.kind === "projectile"                          ? "拦截青火球" :
                                                              (n?.label || "");
      if (!c.pending && w?.kind === "target" && !m.open) m.open = performance.now();
      if (!c.pending && !c.struck && clip.impact_frame != null && f >= clip.impact_frame) {
        c.struck = true;
        health--;
        score.damage++;
        combo = charge = 0;
        burst({x: 640, y: 360}, "hurt");
        refresh();
        if (!health) c.resolve("@failed");
      }
      if (!c.pending && c.resolve && c.playhead >= c.sequence.frames)
        c.resolve(clip.next);
      else if (qa && !c.pending && w?.kind === "target" && c.spans[f]?.length) {
        if (!ammo)
          reload();
        else
          shoot(hitPoint(c.spans[f]));
      }
    }
  }
  ctx.clearRect(0, 0, 1280, 720);
  if (c && mode === "trial" && viewFrame >= c.begin && viewFrame < c.end &&
      (c.step.highlight || c.step.zones.length === 1 || c.exposed)) {
    const p = center(polygonFor(c, c.step.answer, viewFrame));
    ctx.strokeStyle = "#fbc874";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 30, 0, 2 * Math.PI);
    ctx.stroke();
  }
  particles = particles.filter(v => effectTime - v.t < 450);
  for (const v of particles) {
    const age = (effectTime - v.t) / 450;
    ctx.strokeStyle = "rgba(255,211,117," + (1 - age) + ")";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(v.p.x, v.p.y, 9 + age * 33, 0, Math.PI * 2);
    ctx.stroke();
  }
  if ((gun || pad) && aim.x >= 0) {
    ctx.strokeStyle = "#f5deb4";
    ctx.beginPath();
    ctx.arc(aim.x, aim.y, 8, 0, Math.PI * 2);
    ctx.stroke();
  }
  requestAnimationFrame(tick);
}
$("screen").addEventListener(window.PointerEvent ? "pointerdown" : "mousedown", e => {
  if (e.target.tagName === "BUTTON" || $("menu").contains(e.target)) return;
  const b = $("screen").getBoundingClientRect();
  aim = {x: (e.clientX - b.left) * 1280 / b.width, y: (e.clientY - b.top) * 720 / b.height};
  if (e.button === 2)
    reload();
  else
    shoot(aim, e.button === 1, e.timeStamp);
});
document.addEventListener("contextmenu", e => e.preventDefault());
document.addEventListener("keydown", e => {
  if (e.repeat) return;
  if (e.key === "Escape") window.togglePause();
  if (e.key.toLowerCase() === "r") reload();
  if (e.code === "Space") {
    e.preventDefault();
    if (mode === "film")
      finishChoice("skip");
    else
      shoot(aim, true);
  }
});
let gunLock = false;
window.gunEvent = (cmd, x, y) => {
  if (!gun) return;
  if (cmd === "aim" || cmd === "shoot") aim = {x: x * 2 / 3, y: y * 2 / 3};
  if (cmd === "aim") gunLock = true;
  if (cmd === "lost" || cmd === "exit") {
    gunLock = false;
    window.pauseGame();
    aim = {x: -1, y: -1};
  }
  if (cmd === "start") {
    if (paused) {
      if (gunLock) setPaused(false);
    } else if (mode === "menu" || mode === "failure")
      $("begin").click();
    else if (mode === "film")
      finishChoice("skip");
  }
  if (cmd === "reload") reload();
  if (cmd === "special") shoot(aim, true);
  if (cmd === "shoot") {
    if (aim.x < 0 || aim.x >= 1280 || aim.y < 0 || aim.y >= 720)
      reload();
    else
      shoot(aim);
  }
  if (diagnostic === "gun" && cmd !== "aim")
    info("gun " + cmd + " mode " + mode + " paused " + paused + " lock " + gunLock + " arrows " + ammo);
};
(async () => {
  bundle = await readAsset("bundle.json");
  stages = bundle.campaign.chapters.flatMap(
      ch => ch.stages.map(s => ({...s, chapter: ch.id, heading: ch.heading})));
  saved = JSON.parse(localStorage.getItem(key) || "{}");
  const opts = JSON.parse(localStorage.getItem(key + "-options") || "{}");
  difficulty = saved.difficulty || opts.difficulty || "normal";
  captions = opts.captions ?? true;
  if (typeof opts.lowEffects === "boolean") lowEffects = opts.lowEffects;
  sizeCanvases();
  for (const id of Object.keys(volumes))
    if (Number.isFinite(opts.volumes?.[id])) volumes[id] = Math.max(0, Math.min(1, opts.volumes[id]));
  title();
  requestAnimationFrame(tick);
  info("ready");
  if (qa) {
    if (qa !== "resume") saved = {};
    $("begin").click();
  }
  if (diagnostic === "gun") $("gun").click();
  if (qa)
    setInterval(
        () => info(
            "status " +
            [
              stage?.id, mode, current?.step?.answer, viewFrame, film.currentTime, film.readyState,
              film.paused, paused, !!current?.pending, !!current?.resolve
            ].join(" ")),
        8000);
})().catch(error);
