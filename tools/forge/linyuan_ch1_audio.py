"""Produce all remaining Chapter 1 voice lines, ACE-Step music tracks, special foley, and dukou ambience."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import wave


ROOT = Path("/mnt/d/video_game") if Path("/mnt/d/video_game").exists() else Path(__file__).resolve().parents[2]
ART = ROOT / "assets/linyuan"
PRODUCTION = ROOT / "worlds/linyuan/production"

CAPS = {
    "qingping/redeye": 3.70,
    "qingping/first": 2.10,
    "qingping/up": 1.10,
    "qingping/canister": 1.90,
    "qingping/shrine": 1.80,
    "qingping/civilian": 1.90,
    "qingping/bridge": 1.10,
    "qingping/reload": 1.80,
    "qingping/core": 4.40,
    "qingping/canisters": 2.20,
    "qingping/fireball": 2.20,
    "qingping/mouth": 2.20,
    "qingping/xuanwu": 4.40,
    "qingping/hurt_1": 1.00,
    "qingping/hurt_2": 1.30,
    "qingping/hurt_3": 1.00,
    "qingping/protect": 1.20,
    "luchen/up": 2.20,
    "laojiu/conch": 4.65,
}

MUSIC_TRACKS = {
    "title": (
        56,
        39101,
        "Bright optimistic Chinese wuxia fantasy main title, sweeping guzheng and bamboo dizi "
        "over warm cinematic strings, distant bronze bell harmonics, sunlit karst peaks mood, 84 bpm, no vocals",
    ),
    "jiuqu_story": (
        52,
        39102,
        "Afternoon Chinese river ferry market underscore, warm plucked pipa and light bamboo xiao "
        "with subtle wooden percussion and mysterious low synth pulse at the end, 88 bpm, instrumental, no vocals",
    ),
    "dukou_battle": (
        54,
        39103,
        "Brisk Chinese martial arts courtyard battle loop, fast driving pipa and guzheng ostinato, "
        "crisp paiban woodblock and bright Chinese frame drums, energetic heroic pentatonic melody, 114 bpm, no vocals",
    ),
    "boss_taotie": (
        58,
        39104,
        "Colossal mechanical beast boss battle on a river shoal at sunset, heavy thunderous Chinese war drums, "
        "urgent bowed erhu and low brass swells with subtle driving electronic sub pulse, 122 bpm, no vocals",
    ),
    "jiuqu_outro": (
        46,
        39105,
        "Heroic sunset crossing over a wide river, soaring bamboo xiao motif answered by guzheng arpeggios "
        "and warm orchestral strings, triumphant and hopeful cadence, 76 bpm, instrumental, no vocals",
    ),
}


def free_comfy_vram():
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8194/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print("ComfyUI VRAM freed:", resp.status, flush=True)
    except Exception as exc:
        print("ComfyUI free skipped:", exc, flush=True)


def render_voices():
    free_comfy_vram()
    os.environ.setdefault("HF_HOME", str(Path.home() / "SoundGame/models/hf"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(ROOT / "tools/forge"))
    from changan_voice import synthesizer

    sheet = json.loads((PRODUCTION / "c1_voice_audition.json").read_bytes())
    synth = synthesizer("qwen")
    import numpy as np
    import soundfile as sf
    import torch

    raw_dir = ART / "audit/voice/qwen"
    out_dir = ART / "audio/voice"
    report = {}
    for actor, spec in sheet.items():
        for i, (key, text, direction) in enumerate(spec["lines"]):
            line_id = f"{actor}/{key}"
            raw_path = raw_dir / actor / f"{key}.wav"
            dest = out_dir / actor / f"{key}.wav"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not raw_path.exists():
                torch.manual_seed(79100 + i)
                wave_arr, rate = synth(text, spec, direction)
                wave_arr = np.asarray(wave_arr).squeeze()
                tmp = raw_path.with_suffix(".part.wav")
                sf.write(tmp, wave_arr, rate, subtype="PCM_16")
                tmp.replace(raw_path)
            with wave.open(str(raw_path)) as handle:
                raw_sec = handle.getnframes() / handle.getframerate()
            pace = max(1.0, raw_sec / CAPS.get(line_id, raw_sec))
            af = [f"atempo={pace:.6f}"] if pace <= 2.0 else [f"atempo=2.0,atempo={pace/2.0:.6f}"]
            if actor == "laojiu":
                # Bandpass 300-3400Hz + subtle saturation + conch shell cavity echo
                af.append("highpass=f=300,lowpass=f=3400,acompressor=threshold=0.25:ratio=3,aecho=0.8:0.75:14:0.22")
            elif line_id in {"qingping/redeye", "qingping/core", "qingping/xuanwu"}:
                af.append("aecho=0.92:0.88:24:0.10")
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-v", "error", "-y",
                    "-i", str(raw_path),
                    "-af", ",".join(af),
                    "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le",
                    str(dest),
                ],
                check=True,
            )
            with wave.open(str(dest)) as handle:
                dur = handle.getnframes() / handle.getframerate()
            report[line_id] = {
                "file": dest.relative_to(ROOT).as_posix(),
                "seconds": round(dur, 4),
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            }
            print("Voice:", line_id, f"{dur:.3f}s", flush=True)
    (PRODUCTION / "c1_voice_timing.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def render_music():
    free_comfy_vram()
    model_repo = Path.home() / "tools/ACE-Step-1.5"
    sys.path.insert(0, str(model_repo))
    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    torch.backends.cuda.preferred_blas_library("cublaslt")
    handler = AceStepHandler()
    handler.initialize_service(project_root=str(model_repo), config_path="acestep-v15-turbo", device="cuda")

    raw_out = ART / "audit/music"
    raw_out.mkdir(parents=True, exist_ok=True)
    music_dir = ART / "audio/music"
    music_dir.mkdir(parents=True, exist_ok=True)
    for name, (duration, seed, prompt) in MUSIC_TRACKS.items():
        dest = music_dir / f"{name}.wav"
        if dest.is_file():
            continue
        raw_wav = raw_out / f"{name}_raw.wav"
        if not raw_wav.is_file():
            params = GenerationParams(
                caption=prompt, lyrics="", duration=duration, instrumental=True,
                inference_steps=8, seed=seed,
            )
            config = GenerationConfig(batch_size=1, audio_format="wav", use_random_seed=False, seeds=[seed])
            result = generate_music(handler, None, params, config, save_dir=str(raw_out))
            if not result.success:
                raise RuntimeError(result.error)
            Path(result.audios[0]["path"]).replace(raw_wav)
        fade_out = max(1, duration - 1)
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-y",
                "-i", str(raw_wav),
                "-af", f"afade=t=in:st=0:d=0.15,afade=t=out:st={fade_out}:d=1.0",
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
                str(dest),
            ],
            check=True,
        )
        print("Music:", dest.name, flush=True)
    credits = music_dir / "credits.wav"
    if not credits.is_file() and (music_dir / "jiuqu_outro.wav").is_file():
        credits.write_bytes((music_dir / "jiuqu_outro.wav").read_bytes())


def render_special_foley_and_ambience():
    import numpy as np

    foley_dir = ART / "audio/foley"
    foley_dir.mkdir(parents=True, exist_ok=True)
    rate = 48000
    dur = 1.05
    t = np.arange(round(rate * dur)) / rate
    for idx, suffix in enumerate(("", "_2", "_3")):
        rng = np.random.default_rng(9100 + idx)
        stereo = np.zeros((len(t), 2))
        for k in range(8):
            start = 0.015 + 0.028 * k
            s = np.maximum(0.0, t - start)
            freq = (1320 + k * 145) * rng.uniform(0.98, 1.02)
            tone = (0.20 * np.sin(2 * np.pi * freq * s) + 0.11 * np.sin(2 * np.pi * freq * 1.98 * s))
            env = (1 - np.exp(-s / 0.002)) * np.exp(-s / 0.11)
            pan = (k - 3.5) / 4.0 * 0.6
            l_gain = np.sqrt(0.5 * (1 - pan))
            r_gain = np.sqrt(0.5 * (1 + pan))
            stereo[:, 0] += tone * env * l_gain
            stereo[:, 1] += tone * env * r_gain
        # Low-frequency convergence shockwave around 0.24s
        sb = np.maximum(0.0, t - 0.24)
        phase = 2 * np.pi * (92 * sb + 4.5 * (1 - np.exp(-sb / 0.05)))
        boom = 0.45 * (1 - np.exp(-sb / 0.004)) * np.exp(-sb / 0.18) * (
            np.sin(phase) + 0.42 * np.sin(2 * phase)
        )
        stereo[:, 0] += boom
        stereo[:, 1] += boom
        stereo[-240:] *= np.linspace(1.0, 0.0, 240)[:, None]
        stereo *= min(1.0, 0.78 / max(0.001, np.abs(stereo).max()))
        dest = foley_dir / f"special{suffix}.wav"
        with wave.open(str(dest), "wb") as handle:
            handle.setparams((2, 2, rate, len(stereo), "NONE", "not compressed"))
            handle.writeframes(np.rint(stereo * 32767).astype("<i2").tobytes())
        print("Foley:", dest.name, flush=True)

    amb_src = ART / "audit/field_audio/bamboo-wind.mp3"
    amb_dest = ART / "audio/ambience/dukou_air.wav"
    amb_dest.parent.mkdir(parents=True, exist_ok=True)
    if amb_src.is_file():
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-y",
                "-ss", "5", "-t", "20", "-i", str(amb_src),
                "-af", "highpass=f=90,volume=0.18",
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
                str(amb_dest),
            ],
            check=True,
        )
    elif (ART / "audio/ambience/bamboo_stream.wav").is_file():
        amb_dest.write_bytes((ART / "audio/ambience/bamboo_stream.wav").read_bytes())
    print("Ambience:", amb_dest.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("voices", "music", "foley", "all"))
    args = parser.parse_args()
    if args.step in ("foley", "all"):
        render_special_foley_and_ambience()
    if args.step in ("voices", "all"):
        render_voices()
    if args.step in ("music", "all"):
        render_music()


if __name__ == "__main__":
    main()
