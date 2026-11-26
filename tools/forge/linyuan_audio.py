"""Build event Foley and timed dialogue for Linyuan from the local production models."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave

from linyuan_media import ART, PRODUCTION, ROOT, hash_file, rel, write_json


CUES = {
    "shot": (
        "a single elegant Chinese flying sword whistles past the listener with a short metal zing",
        0.37,
    ),
    "hit_ceramic": (
        "steel tip strikes a thick hollow ceramic shell, dry sharp crack with a low knock",
        0.36,
    ),
    "hit_wing": (
        "steel blade hits a thin metal feather, sharp high clang and short flutter",
        0.40,
    ),
    "canister": (
        "a pressurized glass and metal fuel canister pops out of a bracket and clangs",
        0.55,
    ),
    "kill": (
        "heavy broken robotic armor falls onto packed earth and shuts down with a descending pitch",
        0.83,
    ),
    "miss_water": (
        "a tiny steel blade skips over a shallow clear stream with a quick splash",
        0.36,
    ),
    "miss_stone": (
        "a tiny steel blade glances off a flat stone with a dry sharp ping",
        0.32,
    ),
    "miss_earth": (
        "a tiny steel blade lands softly into wet earth with a short dull thud",
        0.33,
    ),
    "miss_bamboo": (
        "a slim flying blade hits a hollow bamboo stalk with a wooden tok",
        0.35,
    ),
    "intercept": (
        "two fast projectiles meet in midair with a tight bright crystalline snap and sparks",
        0.45,
    ),
    "hurt_claw": (
        "a heavy ceramic paw swipes across wood with a short low tearing scrape",
        0.49,
    ),
    "hurt_impact": (
        "a heavy metal body slams into padded wood with a blunt low thud",
        0.50,
    ),
    "hurt_blast": (
        "a compact low pressure blast with a short sharp crack, no debris tail",
        0.50,
    ),
    "civilian": (
        "two descending muted alarm bell notes, distinct short mistake warning",
        0.53,
    ),
    "reload": (
        "a cluster of light metal flying swords slides swiftly back into a wooden case",
        0.54,
    ),
    "empty": ("a dry hollow wooden trigger click with no metal resonance", 0.21),
    "reveal": (
        "a thin rising glass harmonic sweeps through air with a short bright release",
        0.38,
    ),
    "warning": ("three short urgent rising mechanical ticks before a lunge", 0.51),
    "ready": (
        "a polished iron latch closing on a wooden sword case with a precise snick",
        0.24,
    ),
}
TEMP = {
    "canister": "purify",
    "kill": "purify",
    "reveal": "special",
    "warning": "civilian",
    "empty": "ready",
}


def foley(model, dependency_path=None):
    # The shared producer maintains seeds, local-only weights, 3 retries and per-file provenance.
    import sys

    if dependency_path:
        # The workstation keeps torchsde/trampoline in the companion Stable Audio environment.
        # Append it so the interpreter's own PyTorch, diffusers and binary wheels take precedence.
        sys.path.append(str(dependency_path))
    import changan_foley

    changan_foley.CUES = CUES
    sys.argv = [
        "changan_foley",
        str(model),
        str(ART / "audit/foley_sources"),
        "--variants",
        "3",
    ]
    changan_foley.main()
    conform_foley()


COMBAT_MASTER = "blade-recall-3"
COMBAT_CUES = {"shot", "reload", "warning", "canister", "civilian", "hurt_claw", "hurt_impact", "hurt_blast"}


def master_combat_foley(path, cue, seed):
    """Layer the authored gestures over the original stereo model takes before loading them in SDL."""
    import numpy as np
    from scipy.signal import butter, sosfilt

    with wave.open(str(path)) as stream:
        pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2) / 32768.
    if cue == "reload":
        pcm = np.pad(pcm, ((0, max(0, 28800-len(pcm))), (0, 0)))
    t = np.arange(len(pcm)) / 48000.
    rng = np.random.default_rng(seed)
    detune = rng.uniform(.966, 1.034)

    def ring(start, freq, decay):
        s = np.maximum(0, t-start)
        env = (1-np.exp(-s/.0018)) * np.exp(-s/decay)
        return np.sin(2*np.pi*freq*detune*s) * env

    def wind(low, high):
        noise = rng.normal(size=(len(t), 2))
        filtered = sosfilt(butter(3, [low, high], fs=48000, btype="bandpass", output="sos"), noise, axis=0)
        return filtered / max(.001, np.sqrt(np.mean(filtered**2)))

    if cue == "shot":
        steel = .21*ring(0, 1460, .085) + .16*ring(.002, 2351, .092) + .085*ring(.005, 4043, .061)
        passage = np.sin(np.pi*np.minimum(1., np.maximum(0., (t-.022)/.29)))**1.6
        mixed = .12*pcm + steel[:,None] + .079*wind(600,6400)*passage[:,None]
    elif cue == "reload":
        steel = np.zeros(len(t))
        for i in range(8):
            start = .16+.055*i
            at = start+.004
            click = .19*ring(at,1380+82*i,.013) + .14*ring(at+.002,2620+65*i,.019)
            click += (.14+.013*i)*ring(at+.003,485-25*i,.016)
            steel += click * np.clip((start+.055-t)/.005,0,1)
        opening = .26*pcm*np.clip((.158-t)/.022,0,1)[:,None]
        mixed = opening + steel[:,None]
    elif cue == "warning":
        alarm = sum(.19*ring(at, freq, .037) + .10*ring(at, 2*freq, .021)
                    for at,freq in ((.006,790),(.21,1030),(.412,1420)))
        mixed = .26*pcm + alarm[:,None]
    elif cue == "canister":
        crack = (.20*ring(.002,1840,.067) + .13*ring(.008,2733,.084) +
                 .14*ring(.014,380,.035) + .08*ring(.085,3580,.083))
        grit = .056*wind(2000,8400)*np.exp(-np.maximum(t-.01,0)/.044)[:,None]
        mixed = .52*pcm + crack[:,None] + grit
    elif cue == "civilian":
        fault = .22*ring(0,262,.095) + .19*ring(.12,174,.15) + .1*ring(.12,221,.11)
        mixed = .26*pcm + fault[:,None]
    else:
        def thump(delay, level):
            s = np.maximum(t - delay, 0)
            phase = 2 * np.pi * (83*s + 2.6*(1 - np.exp(-s/.042)))
            return level * (1 - np.exp(-s/.003)) * np.exp(-s/.070) * (
                np.sin(phase) + .48*np.sin(2*phase) + .32*np.sin(3*phase))
        accent = thump(0, .34) + thump(.13, .21)
        mixed = .82*pcm + accent[:,None]
    # Keep the SAO texture and its stereo image; reserve headroom for simultaneous dialogue and impacts.
    mixed[-192:] *= np.linspace(1, 0, 192)[:,None]
    mixed *= min(1., .67 / max(.001, np.abs(mixed).max()))
    with wave.open(str(path), "wb") as stream:
        stream.setparams((2, 2, 48000, len(mixed), "NONE", "not compressed"))
        stream.writeframes(np.rint(mixed * 32767).astype("<i2").tobytes())


def conform_foley():
    """Deliver atomic 48 kHz stereo PCM files for the SDL campaign mixer."""
    base = ART / "audio/foley"
    raw = ART / "audit/foley_sources"
    raw.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    for cue in CUES:
        for suffix in ("", "_2", "_3"):
            name = cue + suffix
            dest = base / (name + ".wav")
            source = raw / dest.name
            origin = raw / (name + ".json")
            meta = dest.with_suffix(".json")
            mastered = cue not in COMBAT_CUES or (
                meta.is_file() and json.loads(meta.read_bytes()).get("master") == COMBAT_MASTER
            )
            if dest.exists():
                with wave.open(str(dest)) as handle:
                    canonical_pcm = (
                        handle.getframerate(),
                        handle.getnchannels(),
                        handle.getsampwidth(),
                    ) == (48000, 2, 2)
                    if canonical_pcm and mastered:
                        continue
                # Migrate previous raw exports without losing their original model output.
                if not canonical_pcm and not source.exists() and dest.with_suffix(".json").exists():
                    shutil.copyfile(dest, source)
                    shutil.copyfile(dest.with_suffix(".json"), origin)
            if not (source.is_file() and origin.is_file()):
                if dest.exists() and not mastered:
                    raise FileNotFoundError(f"Original model take required to master {name}: {source}")
                continue
            with tempfile.NamedTemporaryFile(
                dir=base, suffix=".mixing", delete=False
            ) as temp:
                part = Path(temp.name)
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(source),
                        "-ar",
                        "48000",
                        "-ac",
                        "2",
                        "-c:a",
                        "pcm_s16le",
                        "-f",
                        "wav",
                        str(part),
                    ],
                    check=True,
                )
                if cue in COMBAT_CUES:
                    master_combat_foley(part, cue, json.loads(origin.read_bytes())["seed"])
                part.replace(dest)
            finally:
                part.unlink(missing_ok=True)
            metadata = json.loads(origin.read_bytes())
            if cue in COMBAT_CUES:
                metadata["master"] = COMBAT_MASTER
            write_json(meta, metadata)


def combat_music():
    """Cut on drum transients, jump the quiet bridge, then blend back into the 24s cue-in."""
    import numpy as np
    from scipy.io import wavfile

    src = ROOT / "assets/changan/audio/music/river_battle.wav"
    dest = ART / "audio/music/battle.wav"
    rate, data = wavfile.read(src)
    if rate != 48000 or data.ndim != 2 or data.shape[1] != 2 or data.dtype != np.int16:
        raise ValueError("Unexpected source format for the bamboo battle loop")
    data = data.astype(float)

    def cut(a, b):
        return data[round(a*rate):round(b*rate)].copy()

    def lead_into(section, entry, duration):
        n = round(duration*rate)
        blend = np.linspace(0, 1, n)[:,None]
        section[-n:] = section[-n:]*(1-blend) + cut(entry-duration, entry)*blend

    opening = cut(24., 38.46)
    ending = cut(47.67, 62.68)
    lead_into(opening, 47.67, .085)
    lead_into(ending, 24., .19)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dest, rate, np.rint(np.vstack((opening,ending))).astype("<i2"))
    write_json(PRODUCTION / "battle_music_edit.json", dict(source=rel(src), source_sha256=hash_file(src),
               source_ranges_seconds=[[24.,38.46],[47.67,62.68]], crossfades_seconds=[.085,.19],
               file=rel(dest), sha256=hash_file(dest)))


def temp_audio():
    source = ROOT / "assets/changan/audio"
    combat_music()
    ref = ART / "audit/temp_foley"
    ref.mkdir(parents=True, exist_ok=True)
    for key in CUES:
        original = TEMP.get(key, key.split("_", 1)[0])
        shutil.copyfile(source / "foley" / (original + ".wav"), ref / (key + ".wav"))


def ambience():
    """Build one continuous field-recorded bed from the bamboo wind and creek stems."""
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt

    folder = ART / "audit/field_audio"
    target = ART / "audio/ambience/bamboo_stream.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    rate = 48000

    def render_stem(name, begin, length, blend):
        file = folder / (name + ".mp3")
        read = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-i", str(file),
                "-ss", str(begin-blend), "-t", str(length+blend), "-ar", str(rate), "-ac", "2", "-f", "f32le", "-"])
        data = np.frombuffer(read, "<f4").reshape(-1, 2)
        data = sosfilt(butter(2, 85, "highpass", fs=rate, output="sos"), data, axis=0)
        n = round(blend*rate)
        bed = data[n:n+round(length*rate)].copy()
        if len(bed) != round(length*rate):
            raise ValueError(f"Short field take: {file}")
        cross = np.linspace(0, 1, n)[:, None]
        bed[-n:] = (1-cross)*bed[-n:] + cross*data[:n]
        return bed / np.sqrt(np.mean(bed**2))

    wind = render_stem("bamboo-wind", 15., 20., .4)
    creek = render_stem("muir-stream", .65, 4., .36)
    mixed = .050*wind + .055*np.tile(creek, (5, 1))
    mixed *= min(1., .60/np.max(np.abs(mixed)))
    wavfile.write(target, rate, np.rint(mixed*32767).astype("<i2"))
    sources = [{"file": rel(file), "sha256": hash_file(file)} for file in
               (folder/"bamboo-wind.mp3", folder/"muir-stream.mp3")]
    write_json(PRODUCTION / "ambient_source.json", dict(file=rel(target), sha256=hash_file(target),
               sources=sources, field_ranges_seconds=[[15.,35.],[.65,4.65]], loop_seconds=20,
               credits=rel(target.parent/"CREDITS.md")))


def aliases():
    conform_foley()
    base = ART / "audio/foley"
    variants = {}
    for cue in CUES:
        variants[cue] = []
        for suffix in ("", "_2", "_3"):
            path = base / (cue + suffix + ".wav")
            origin = json.loads(path.with_suffix(".json").read_bytes())
            with wave.open(str(path)) as stream:
                if stream.getsampwidth() != 2 or stream.getnframes() == 0:
                    raise ValueError(f"Invalid event sound {path}")
                variants[cue].append(
                    {
                        "file": rel(path),
                        "sha256": hash_file(path),
                        "source_model": origin["model"],
                        **({"master": origin["master"]} if "master" in origin else {}),
                        "seed": origin["seed"],
                        "seconds": round(
                            stream.getnframes() / stream.getframerate(), 4
                        ),
                        "rate": stream.getframerate(),
                    }
                )
    canonical = {
        "hit": "hit_ceramic",
        "purify": "kill",
        "miss": "miss_bamboo",
        "hurt": "hurt_claw",
    }
    for alias, source in canonical.items():
        for suffix in ("", "_2", "_3"):
            shutil.copyfile(
                base / (source + suffix + ".wav"), base / (alias + suffix + ".wav")
            )
    write_json(
        PRODUCTION / "foley_bank.json",
        {
            "directory": rel(base),
            "variants": 3,
            "aliases": canonical,
            "events": list(CUES),
            "files": variants,
            "ambience": "audio/ambience/bamboo_stream.wav",
            "music": "audio/music/battle.wav",
            "music_source": {
                "file": "assets/changan/audio/music/river_battle.wav",
                "sha256": hash_file(ROOT / "assets/changan/audio/music/river_battle.wav"),
                "edit_sha256": hash_file(ART / "audio/music/battle.wav"),
                "edit": rel(PRODUCTION / "battle_music_edit.json"),
                "model": "ACE-Step",
            },
        },
    )


def lipsync(model, line="thanks"):
    name = "c1_12_" + line
    record = PRODUCTION / "selections" / (name + ".json")
    source_record = PRODUCTION / "selections/c1_12_thanks.json"
    meta = json.loads((record if record.exists() else source_record).read_bytes())
    meta["id"] = name
    meta["file"] = f"assets/linyuan/drama/{name}.mp4"
    dest = ROOT / meta["file"]
    voice = ART / "audio/voice/yunyi" / (line + ".wav")
    timing = json.loads((PRODUCTION / "voice_timing.json").read_bytes())["scenes"][
        line
    ][0]
    if (
        meta.get("lip_sync", {}).get("voice_sha256") == hash_file(voice)
        and dest.is_file() and hash_file(dest) == meta["sha256"]
    ):
        return
    src = ART / "audit/h3/takes" / meta["candidate"] / "source.mp4"
    folder = ART / "audit/lipsync" / meta["candidate"] / line
    folder.mkdir(parents=True, exist_ok=True)
    src25, speech, synced = (
        folder / f for f in ("source25.mp4", "voice_padded.wav", "speaking.mp4")
    )

    def ff(*args):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True
        )

    duration = meta["frames"] / 24
    ff(
        "-i",
        src,
        "-t",
        duration,
        "-vf",
        "scale=1280:720,fps=25,setsar=1",
        "-an",
        "-crf",
        15,
        src25,
    )
    ff(
        "-i",
        voice,
        "-af",
        f"adelay={timing['begin_ms']}:all=1,apad",
        "-t",
        duration,
        "-ar",
        16000,
        "-ac",
        1,
        speech,
    )
    env = dict(
        os.environ, HF_HUB_OFFLINE="1", HF_HOME=str(Path.home() / ".cache/huggingface")
    )
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.inference",
            "--unet_config_path",
            "configs/unet/stage2_512.yaml",
            "--inference_ckpt_path",
            "checkpoints/latentsync_unet.pt",
            "--inference_steps",
            "20",
            "--guidance_scale",
            "1.5",
            "--video_path",
            str(src25),
            "--audio_path",
            str(speech),
            "--video_out_path",
            str(synced),
            "--temp_dir",
            str(folder / "temp"),
            "--seed",
            "261125",
        ],
        cwd=model,
        env=env,
        check=True,
    )
    part = dest.with_suffix(".synced.mp4")
    ff(
        "-i",
        synced,
        "-f",
        "lavfi",
        "-i",
        "anullsrc=cl=stereo:r=48000",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-vf",
        "scale=1280:720,fps=24,setsar=1,tpad=stop_duration=0.2:stop_mode=clone",
        "-t",
        duration,
        "-r",
        24,
        "-c:v",
        "libx264",
        "-crf",
        17,
        "-g",
        24,
        "-bf",
        0,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        48000,
        "-ac",
        2,
        "-movflags",
        "+faststart",
        part,
    )
    frames = int(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=nb_frames",
                "-of",
                "csv=p=0",
                str(part),
            ],
            text=True,
        ).strip()
    )
    if frames != meta["frames"]:
        raise ValueError(f"Lip sync duration changed: {frames} frames")
    part.replace(dest)
    meta.update(
        sha256=hash_file(dest),
        lip_sync={
            "model": "LatentSync stage2_512",
            "seed": 261125,
            "begin_ms": timing["begin_ms"],
            "voice_sha256": hash_file(voice),
            "video_sha256": hash_file(src),
        },
    )
    write_json(record, meta)


def retry_vox():
    import os
    import sys

    os.environ.setdefault("HF_HOME", str(Path.home() / "SoundGame/models/hf"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import numpy as np
    import soundfile as sf
    import torch
    from changan_voice import synthesizer

    synth = synthesizer("vox")
    for actor, spec in json.loads(
        (PRODUCTION / "voice_audition.json").read_bytes()
    ).items():
        for index, (key, text, direction) in enumerate(spec["lines"]):
            dest = ART / "audit/voice/vox" / actor / (key + ".wav")
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            for attempt in range(5):
                torch.manual_seed(74201 + index * 17 + attempt)
                samples, rate = synth(text, spec, direction)
                samples = np.asarray(samples).squeeze()
                if (
                    len(samples) >= rate * 0.5
                    and np.isfinite(samples).all()
                    and np.max(np.abs(samples)) > 0.01
                ):
                    tmp = dest.with_suffix(".part.wav")
                    sf.write(tmp, samples, rate, subtype="PCM_16")
                    tmp.replace(dest)
                    break
            else:
                print("no usable Vox audition for", actor, key, file=sys.stderr)
                raise ValueError("VoxCPM2 produced an insufficient spoken take")


def timelock():
    # Qwen voices are selected per role. The two shared scene windows include natural pauses.
    sheet = json.loads((PRODUCTION / "voice_audition.json").read_bytes())
    uses = {}
    caps = {
        "qingping/noodle": 3.50,
        "luchen/noodle": 1.22,
        "yunyi/talon": 1.70,
        "qingping/talon": 1.00,
        "yunyi/thanks": 2.75,
        "yunyi/rebuke": 2.75,
    }
    for actor, spec in sheet.items():
        for key, text, _ in spec["lines"]:
            line_id = actor + "/" + key
            source = ART / "audit/voice/qwen" / actor / (key + ".wav")
            dest = ART / "audio/voice" / actor / (key + ".wav")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(source)) as voice:
                raw = voice.getnframes() / voice.getframerate()
            pace = max(1.0, raw / caps.get(line_id, raw))
            args = [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-af",
                f"atempo={pace:.6f}",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                str(dest),
            ]
            subprocess.run(args, check=True)
            with wave.open(str(dest)) as voice:
                seconds = voice.getnframes() / voice.getframerate()
            uses[line_id] = {
                "text": text,
                "engine": "qwen",
                "source": rel(source),
                "file": rel(dest),
                "sha256": hash_file(dest),
                "seconds": round(seconds, 4),
                "tempo": round(pace, 4),
            }
    scenes = {}
    for scene, ids in {
        "noodle": ["qingping/noodle", "luchen/noodle"],
        "talon": ["yunyi/talon", "qingping/talon"],
        "thanks": ["yunyi/thanks"],
        "rebuke": ["yunyi/rebuke"],
    }.items():
        cursor = 0.0 if scene in ("thanks", "rebuke") else 0.06
        scenes[scene] = []
        for id_ in ids:
            end = cursor + uses[id_]["seconds"]
            scenes[scene].append(
                {
                    "line": id_,
                    "begin_ms": round(cursor * 1000),
                    "end_ms": round(end * 1000),
                }
            )
            cursor = end + 0.09
        if end > {"noodle": 5, "talon": 3, "thanks": 3, "rebuke": 3}[scene]:
            raise ValueError(f"Dialogue exceeds scene window: {scene} {end}")
    write_json(PRODUCTION / "voice_timing.json", {"lines": uses, "scenes": scenes})


def audit_voice(recognizer_path):
    """Store the words recognized in the selected performances and available auditions."""
    from funasr import AutoModel

    model = AutoModel(
        model=str(recognizer_path), device="cpu", disable_update=True, ncpu=3
    )
    cast = json.loads((PRODUCTION / "voice_audition.json").read_bytes())
    report = PRODUCTION / "voice_listening.json"
    rows = json.loads(report.read_bytes()) if report.exists() else {}
    for actor, role in cast.items():
        for key, expected, _ in role["lines"]:
            for kind, base in (
                ("selected", ART / "audio/voice"),
                ("vox", ART / "audit/voice/vox"),
                ("qwen", ART / "audit/voice/qwen"),
            ):
                take = base / actor / (key + ".wav")
                if not take.exists():
                    continue
                digest = hash_file(take)
                label = "/".join((kind, actor, key))
                if rows.get(label, {}).get("sha256") == digest:
                    continue
                result = model.generate(input=str(take), language="zh", use_itn=True)
                recognized = re.sub(r"<\|.*?\|>", "", result[0]["text"]).strip()
                rows[label] = {
                    "file": rel(take),
                    "sha256": digest,
                    "script": expected,
                    "transcript": recognized,
                    "recognizer": "SenseVoiceSmall",
                }
                write_json(report, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest="command", required=True)
    cmd.add_parser("temporary")
    cmd.add_parser("combat-music")
    cmd.add_parser("timelock")
    cmd.add_parser("ambience")
    cmd.add_parser("aliases")
    cmd.add_parser("conform-foley")
    lips = cmd.add_parser("lipsync")
    lips.add_argument("model", type=Path)
    lips.add_argument("--line", choices=("thanks", "rebuke"), default="thanks")
    cmd.add_parser("retry-vox")
    listen = cmd.add_parser("audit-voice")
    listen.add_argument("recognizer", type=Path)
    final = cmd.add_parser("foley")
    final.add_argument("model", type=Path)
    final.add_argument("--dependency-path", type=Path)
    args = parser.parse_args()
    if args.command == "temporary":
        temp_audio()
    elif args.command == "combat-music":
        combat_music()
    elif args.command == "timelock":
        timelock()
    elif args.command == "retry-vox":
        retry_vox()
    elif args.command == "audit-voice":
        audit_voice(args.recognizer)
    elif args.command == "ambience":
        ambience()
    elif args.command == "aliases":
        aliases()
    elif args.command == "conform-foley":
        conform_foley()
    elif args.command == "lipsync":
        lipsync(args.model, args.line)
    else:
        foley(args.model, args.dependency_path)


if __name__ == "__main__":
    main()
