"""Prepare the Linyuan production manifest and run reproducible local H3 candidates."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from changan_h3 import generate


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "assets/linyuan"
KEYS = ART / "kf_raw/horizon_v1"
WORK = ART / "audit/h3"
PRODUCTION = ROOT / "worlds/linyuan/production"
LEDGER = PRODUCTION / "mvp_jobs.json"
SHEET = ROOT / "docs/LINYUAN_CH1_PROMPTS.md"
FIRST_IMAGES = "CH_LUCHEN CH_QINGPING CH_YUNYI EN_SUANNI EN_FOX PL_BAMBOO PL_NOODLE PL_STALL KF_C1_04".split()
LATER_IMAGES = "EN_BIFANG EN_PANGOLIN PL_BAMBOO_X KF_C1_10 KF_C1_11_END KF_C1_12 K_PANGOLIN PL_VISTA PL_MARKET KF_C1_13 EN_TAOTIE".split()
WAVES = [
    "c1_w_" + suffix
    for suffix in (
        "fox_shrine",
        "fox_grove",
        "bifang_canopy",
        "suanni_rock",
        "suanni_steps",
    )
]
PILOT = {
    "c1_04_noodle",
    "c1_w_suanni_rock",
    "c1_w_suanni_rock_kill_mid",
    "c1_w_fox_shrine",
}
SFX = "shot hit_ceramic hit_wing canister kill miss_water miss_stone miss_earth miss_bamboo intercept hurt_claw hurt_impact hurt_blast civilian reload empty reveal warning".split()
IMAGE_REFS = {
    "CH_LUCHEN": ["AH_LUCHEN_02"],
    "CH_QINGPING": ["AH_QINGPING_02"],
    "CH_YUNYI": ["AH_CAMP_02"],
    "EN_SUANNI": ["AH_SUANNI_02"],
    "EN_BIFANG": ["AH_BIFANG_02"],
    "EN_FOX": ["EN_SUANNI"],
    "EN_PANGOLIN": ["EN_SUANNI"],
    "PL_BAMBOO": ["AH_BAMBOO_02"],
    "PL_NOODLE": ["AH_CAMP_02"],
    "PL_STALL": ["PL_NOODLE"],
    "PL_BAMBOO_X": ["PL_BAMBOO"],
    "KF_C1_04": ["PL_NOODLE", "CH_LUCHEN", "CH_QINGPING", "CH_YUNYI"],
    "KF_C1_10": ["PL_STALL", "CH_YUNYI", "EN_BIFANG"],
    "KF_C1_11_END": ["KF_C1_10", "CH_YUNYI"],
    "KF_C1_12": ["CH_YUNYI", "PL_STALL"],
    "K_PANGOLIN": ["PL_BAMBOO", "EN_PANGOLIN"],
    "PL_VISTA": ["AH_VISTA_02"],
    "PL_MARKET": ["AH_CAMP_02"],
    "KF_C1_13": ["PL_NOODLE", "CH_LUCHEN"],
    "EN_TAOTIE": ["AH_TAOTIE_02"],
}


def catalog():
    # A slot ending in _early/_mid/_late binds to an extracted frame before publication.
    result = {}

    def add(name, first, last, length, heading=None, guide=None):
        spec = {
            "first": first,
            "last": last,
            "length": length,
            "heading": heading or name,
        }
        if guide:
            spec["guide"] = guide
        result[name] = spec

    add("c1_04_noodle", "KF_C1_04", None, 119)
    add("c1_10_talon", "KF_C1_10", None, 119)
    for outcome in ("hit", "miss"):
        add("c1_11_" + outcome, "@c1_10_talon/hover", "KF_C1_11_END", 73)
    add("c1_12_thanks", "KF_C1_12", None, 73)
    add("c1_bamboo_plate", "PL_BAMBOO", "PL_BAMBOO", 175)
    for wave in WAVES:
        guide = {
            "c1_w_suanni_rock": ["G_SUANNI_ROCK", 40],
            "c1_w_suanni_steps": ["G_SUANNI_STEPS", 32],
            "c1_w_fox_shrine": ["G_FOX_SHRINE", 40],
            "c1_w_fox_grove": ["G_FOX_GROVE", 20],
            "c1_w_bifang_canopy": ["G_BIFANG_CANOPY", 32],
        }[wave]
        add(wave, "PL_BAMBOO", "PL_BAMBOO", 99, guide=guide)
        if "fox" in wave:
            heading = "c1_w_fox_shrine_kill_* / c1_w_fox_grove_kill_*"
        elif "suanni" in wave:
            heading = "c1_w_suanni_rock_kill_* / c1_w_suanni_steps_kill_*"
        else:
            heading = "c1_w_bifang_canopy_kill_*"
        for slot in ("early", "mid", "late"):
            add(
                wave + "_kill_" + slot,
                "@" + wave + "/" + slot,
                "PL_BAMBOO",
                47,
                heading,
            )
    add("c1_w_raft", "PL_BAMBOO", "PL_BAMBOO", 99, guide=["G_RAFT", 32])
    for frame, slot in [(28, "early"), (42, "late")]:
        add(
            f"c1_raft_drop_{frame}",
            "@c1_w_raft/" + slot,
            "PL_BAMBOO_X",
            47,
            "c1_raft_drop_28 / 42",
        )
    add(
        "c1_w_pangolin_roof",
        "PL_BAMBOO",
        "K_PANGOLIN",
        119,
        guide=["G_NEEDLES_CLOSED", 32],
    )
    for slot in ("early", "late"):
        add(
            "c1_pangolin_intercept_" + slot,
            "@c1_w_pangolin_roof/" + slot,
            "K_PANGOLIN",
            47,
            "c1_pangolin_intercept_early / late",
        )
    add("c1_pangolin_impact", "@c1_w_pangolin_roof/impact", "K_PANGOLIN", 47)
    add(
        "c1_pangolin_threat",
        "K_PANGOLIN",
        "K_PANGOLIN",
        99,
        guide=["G_NEEDLES_CLOSED", 24],
    )
    add("c1_pangolin_flinch", "K_PANGOLIN", "K_PANGOLIN", 47)
    add("c1_pangolin_kill", "K_PANGOLIN", "PL_BAMBOO", 73)
    return result


def prompt(name):
    spec = catalog()[name]
    # A literal heading lookup preserves wildcard suffixes in authored titles.
    doc = SHEET.read_text(encoding="utf8")
    heading = "**" + spec["heading"] + "**"
    start = doc.index(heading)
    body = doc[start:].split("```", 2)[1].strip()
    for _ in range(4):
        tokens = set(re.findall(r"\[[A-Z_]+\]", body))
        if not tokens:
            return body
        for token in tokens:
            ref = doc.index("**" + token)
            body = body.replace(token, doc[ref:].split("```", 2)[1].strip())
    raise ValueError(f"Unresolved prompt parts for {name}")


def rel(path):
    return path.relative_to(ROOT).as_posix()


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf8",
        dir=path.parent,
        delete=False,
        prefix=path.stem + ".",
        suffix=".writing",
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    output = Path(tmp.name)
    try:
        for attempt in range(8):
            try:
                output.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.04 * (attempt + 1))
    finally:
        output.unlink(missing_ok=True)


def refresh():
    ledger = json.loads(LEDGER.read_text(encoding="utf8")) if LEDGER.exists() else {}
    ledger.update(
        schema=1,
        source_references="output/imagegen/linyuan_art_horizon_20261125/",
        source_frame_origin=0,
        time_window="begin <= displayed_source_frame < end",
        human_review=ledger.get(
            "human_review", {"pilot": "pending", "first_play": "pending"}
        ),
    )
    ledger["images"] = {}
    for name in FIRST_IMAGES + LATER_IMAGES:
        path = KEYS / (name + ".png")
        ledger["images"][name] = {
            "stage": 1 if name in FIRST_IMAGES else 2,
            "file": rel(path),
            "references": IMAGE_REFS[name],
            "medium": "AI-generated keyframe",
            "status": "available" if path.exists() else "planned",
            "sha256": hash_file(path) if path.exists() else None,
        }
    videos = ledger.setdefault("videos", {})
    for name, spec in catalog().items():
        # Candidate movies are large local audit files. Preserve their production history
        # when an agent checks out just the shared manifests and final media.
        previous = {c["id"]: c for c in videos.get(name, {}).get("candidates", [])}
        v = {"status": "planned", "selected": None, "region_version": None}
        videos[name] = v
        v.update(
            spec,
            stage=1 if name in PILOT else 2,
            requested_candidates=(
                3
                if name in PILOT
                or name.startswith(
                    ("c1_0", "c1_1", "c1_pangolin", "c1_w_pangolin", "c1_bamboo")
                )
                else 2
            ),
        )
        for record in sorted((WORK / "takes").glob(f"linyuan_{name}__v*/job.json")):
            source = record.parent / "source.mp4"
            hist = record.parent / "history.json"
            info = json.loads(record.read_text(encoding="utf8"))
            state = (
                json.loads(hist.read_bytes()).get("status", {}) if hist.exists() else {}
            )
            times = {
                k: m.get("timestamp")
                for k, m in state.get("messages", [])
                if isinstance(m, dict)
            }
            ms = (times.get("execution_success") or 0) - (
                times.get("execution_start") or 0
            )
            saved = previous.get(record.parent.name, {})
            generated = (
                source.is_file()
                or state.get("completed")
                or saved.get("status") == "generated"
            )
            previous[record.parent.name] = {
                "id": record.parent.name,
                "request_id": info["prompt"],
                "file": rel(source),
                "status": "generated"
                if generated
                else state.get("status_str", "submitted"),
                "gpu_job_minutes": round(ms / 60000, 3)
                if ms > 0
                else saved.get("gpu_job_minutes"),
                "seed": info["workflow"]["7"]["inputs"]["noise_seed"],
                "comfy_revision": info["comfy_revision"],
            }
        v["candidates"] = sorted(
            previous.values(), key=lambda c: int(c["id"].rsplit("__v", 1)[1])
        )
        if v["candidates"] and v["status"] == "planned":
            v["status"] = "candidates"
        selection = PRODUCTION / "selections" / (name + ".json")
        if selection.exists():
            v.update(status="selected", selected=json.loads(selection.read_bytes()))
    speakers = json.loads((PRODUCTION / "voice_audition.json").read_bytes())
    ledger["voices"] = {
        f"{actor}/{key}": {
            "line": line,
            "delivery": rel(ART / "audio/voice" / actor / (key + ".wav")),
            "auditions": {
                engine: rel(ART / "audit/voice" / engine / actor / (key + ".wav"))
                for engine in ("qwen", "vox")
            },
        }
        for actor, data in speakers.items()
        for key, line, _ in data["lines"]
    }
    ledger["audio"] = {
        "effects": SFX,
        "variants_per_effect": 3,
        "ambience": "bamboo_stream",
        "music": "battle",
    }
    for key, file in (
        ("voice_timing", "voice_timing.json"),
        ("audition_transcripts", "voice_listening.json"),
        ("event_files", "foley_bank.json"),
        ("ambient_source", "ambient_source.json"),
    ):
        path = PRODUCTION / file
        if path.is_file():
            ledger["audio"][key] = rel(path)
    if (PRODUCTION / "voice_timing.json").is_file():
        timing = json.loads((PRODUCTION / "voice_timing.json").read_bytes())["lines"]
        for line_id, entry in ledger["voices"].items():
            entry["selected_engine"] = timing[line_id]["engine"]
            entry["seconds"] = timing[line_id]["seconds"]
            entry["sha256"] = timing[line_id]["sha256"]
            entry["available_auditions"] = [
                engine
                for engine, path in entry["auditions"].items()
                if (ROOT / path).is_file()
            ]
    ledger["anchor_proofs"] = rel(PRODUCTION / "anchors")
    ledger.setdefault("review_log", [])
    ledger["accounting"] = {
        "candidates_requested": sum(v["requested_candidates"] for v in videos.values()),
        "submissions": sum(len(v["candidates"]) for v in videos.values()),
        "generated": sum(
            c["status"] == "generated" for v in videos.values() for c in v["candidates"]
        ),
        "selected_ids": sum(v["selected"] is not None for v in videos.values()),
        "worker_minutes": round(
            sum(
                c["gpu_job_minutes"] or 0
                for v in videos.values()
                for c in v["candidates"]
            ),
            3,
        ),
        "timing_scope": "ComfyUI execution_start to execution_success; excludes queue, imagegen and QA.",
    }
    review = PRODUCTION / "production_review.json"
    if review.exists():
        ledger["review_log"] = json.loads(review.read_bytes())
    bindings = PRODUCTION / "bindings.json"
    if bindings.exists():
        data = json.loads(bindings.read_bytes()).get("videos", {})
        for v in videos.values():
            selected = v["selected"]
            if selected and selected["id"] in data:
                current = data[selected["id"]]
                if current.get("sha256") == selected["sha256"]:
                    payload = json.dumps(
                        current, ensure_ascii=False, sort_keys=True
                    ).encode()
                    v["region_version"] = hashlib.sha256(payload).hexdigest()
    reply = PRODUCTION / "selections/c1_12_rebuke.json"
    if reply.exists():
        ledger["dialogue_variants"] = {"c1_12_rebuke": json.loads(reply.read_bytes())}
    ledger.setdefault("human_minutes", None)
    assert (
        len(videos) == 36 and len(ledger["voices"]) == 10 and len(ledger["images"]) == 20
    )
    write_json(LEDGER, ledger)


def anchor_files(name):
    spec = catalog()[name]
    refs = [spec["first"], spec["last"]]
    if spec.get("guide"):
        refs.append(spec["guide"][0])
    ret = {}
    for ref in filter(None, refs):
        if ref.startswith("@"):
            source, slot = ref[1:].split("/")
            proof = PRODUCTION / "anchors" / f"{source}_{slot}.json"
            info = json.loads(proof.read_bytes())
            if hash_file(ROOT / info["source"]) != info["sha256"]:
                raise ValueError(f"Stale extraction: {proof}")
            ret[ref] = (ROOT / info["anchor"]).stem
        else:
            ret[ref] = ref
    return ret


def take(name, variant):
    spec = catalog()[name]
    resolved = anchor_files(name)
    job = {
        "first": resolved[spec["first"]],
        "length": spec["length"],
        "prompt": prompt(name),
        "prefix": "",
        "seed": 611000 + list(catalog()).index(name) * 17 + variant,
    }
    if spec["last"]:
        job["last"] = resolved[spec["last"]]
    if "guide" in spec:
        job["guide"] = spec["guide"]
    if name == "c1_w_fox_grove" and variant >= 3:
        job.update(
            guide=["G_FOX_GROVE", 12],
            prompt="Locked tripod, continuous sunlit shot. In the first six frames a single "
            "very thin cyan scan ring passes left-to-right through the foliage. It reveals a "
            "solid pale ivory ceramic fox crouched under the left bamboo. Its armor, two "
            "small RED eyes and one amber forehead cell become clear immediately. The scan "
            "line vanishes; the creature stays fully opaque with unchanged ivory armor and red "
            "eyes for the entire dash. It stalks forward then lunges towards camera and darts "
            "past the edge. End on the empty forest. No other light pulses, orange flash, "
            "cyan body glow, explosions, afterimages, debris, mist, camera movement or HUD.",
        )
    if name.startswith("c1_w_suanni_rock_kill_") and (
        "_mid" not in name or variant >= 4
    ):
        job.update(
            guide=["G_ROCK_KILL_BEHIND", 24],
            prompt="Continuous locked camera, same light and forest. The shoulder tank is struck "
            "IMMEDIATELY and shoots BACKWARD AND UP to screen right with a bright amber spark. "
            "The lion loses power and tips backward behind the large right boulder. Both the white "
            "machine AND entire detached canister sink out of sight behind the far upper-right rim "
            "of that boulder. The footpath and stream in FRONT of the rock stay empty and unchanged "
            "throughout. Tiny brief sparks only. Reach and hold the empty background plate. "
            "No floating fade-outs, smoke clouds, camera shake, lettering, character or HUD.",
        )
    if name == "c1_pangolin_flinch" and variant >= 4:
        job.update(
            guide=["G_PANGOLIN_FLINCH", 16],
            prompt="Locked-off wide view, static camera, unchanged focal length. The tiny white "
            "machine remains perched in its exact original spot on the upper-left roof ridge. "
            "The fan jerks slightly backward, the one round central amber cell emits a short "
            "local spray of sparks. Machine holds position, steadies and reveals its intact "
            "core again by frame 22. Hold the end anchor. No camera motion or close-up, no UI.",
        )
    fall_guides = {
        "c1_w_fox_shrine": (
            "G_FOX_SHRINE_KILL",
            "inside the dark shrine doorway on the left",
        ),
        "c1_w_fox_grove": (
            "G_FOX_GROVE_KILL",
            "behind the thick bamboo trunks at the far left frame edge",
        ),
        "c1_w_bifang_canopy": (
            "G_BIFANG_KILL",
            "behind the distant upper bamboo canopy away from the viewer",
        ),
        "c1_w_suanni_steps": (
            "G_STEPS_KILL",
            "behind the raised bank beside the distant stone steps",
        ),
    }
    wave = name.split("_kill_")[0]
    if (
        "_kill_" in name
        and wave in fall_guides
        and (variant >= 3 or wave == "c1_w_fox_grove")
    ):
        guide, cover = fall_guides[wave]
        job.update(
            guide=[guide, 24],
            prompt=f"Locked tripod; preserve the first picture and empty "
            f"last anchor. The white machine takes an immediate sharp hit in its amber cell. "
            f"A brief spray of sparks and an armor plate break away. Heavy body and all pieces "
            f"recoil backward together and disappear {cover}. All debris must land {cover}. "
            f"Smooth exit through physical occlusion; no teleport. The path, foreground and creek "
            f"remain empty. Reach the empty background by the mid shot and hold. No camera movement, "
            f"zoom, new sunlight, smoke clouds, letters, player or HUD.",
        )
    if name == "c1_pangolin_kill" and variant >= 4:
        job.update(
            guide=["G_PANGOLIN_KILL", 20],
            prompt="Locked very WIDE shot, static tripod. On the roof, "
            "the lit amber core bursts, the white pangolin shudders then tips BACKWARD and DOWN "
            "on the far side of the shrine. By the middle, only two fan tips show for a moment "
            "over the roof ridge and then drop behind it. All debris falls behind the roof. Hold "
            "the original empty bamboo clearing. No machine on the ground, no camera zoom or cut.",
        )
    generate(f"linyuan_{name}__v{variant}", job, KEYS, WORK)


def extract(name, slot, source, frame):
    if frame < 0:
        raise ValueError("Frame must be nonnegative")
    source = source.resolve()
    digest = hash_file(source)
    dest = KEYS / f"src_{name}_{slot}_{frame}_{digest[:12]}.png"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-frames:v",
            "1",
            str(dest),
        ],
        check=True,
    )
    if not dest.exists():
        raise ValueError(f"No decoded frame {frame} in {source}")
    write_json(
        PRODUCTION / "anchors" / f"{name}_{slot}.json",
        {"source": rel(source), "frame": frame, "sha256": digest, "anchor": rel(dest)},
    )


def publish(name, variant, start, end, speed, note, reveal_frames=0):
    media_id = name
    if "_kill_" in name:
        wave, slot = name.rsplit("_kill_", 1)
        anchor = json.loads(
            (PRODUCTION / "anchors" / f"{wave}_{slot}.json").read_bytes()
        )
        media_id = f"{wave}_kill_{anchor['frame']}"
    candidate = f"linyuan_{name}__v{variant}"
    source = WORK / "takes" / candidate / "source.mp4"
    dest = (
        ART
        / ("drama" if name.startswith(("c1_0", "c1_1")) else "bamboo")
        / (media_id + ".mp4")
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    if speed <= 0 or start < 0 or (end and end <= start):
        raise ValueError("Invalid trim interval or playback speed")
    trim = f"trim=start_frame={start}" + (f":end_frame={end}" if end else "")
    vf = f"{trim},setpts=(PTS-STARTPTS)/{speed},fps=24,scale=1280:720:flags=lanczos,setsar=1"
    video = ["-map", "0:v:0", "-vf", vf]
    if reveal_frames:
        if name != "c1_w_fox_grove" or not 2 <= reveal_frames <= 12 or speed != 1:
            raise ValueError(
                "The scan dissolve needs normal-speed grove footage and 2–12 frames"
            )
        # Use the original empty first frame and one continuous H3 take of the late scan.
        # Its white-armor dash remains at the original speed with no further color changes.
        duration = reveal_frames / 24
        graph = (
            "[0:v]split[a][b];[a]trim=end_frame=1,setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={duration + 1:.8f},fps=24[empty];"
            f"[b]{trim},setpts=PTS-STARTPTS,fps=24[motion];"
            f"[empty][motion]xfade=transition=fade:duration={duration:.8f}:offset=0,"
            "scale=1280:720:flags=lanczos,setsar=1[out]"
        )
        video = ["-filter_complex", graph, "-map", "[out]"]
    # World audio is authored separately; suppress stochastic H3 speech and baked-in impacts.
    temp = dest.with_suffix(".part.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            *video,
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-threads",
            "4",
            "-preset",
            "veryfast",
            "-crf",
            "17",
            "-bf",
            "0",
            "-g",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-shortest",
            "-movflags",
            "+faststart",
            str(temp),
        ],
        check=True,
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
                str(temp),
            ],
            text=True,
        ).strip()
    )
    if frames <= 0:
        raise ValueError(f"Empty output for {name}")
    temp.replace(dest)
    selection = {
        "id": media_id,
        "candidate": candidate,
        "file": rel(dest),
        "sha256": hash_file(dest),
        "source_sha256": hash_file(source),
        "frames": frames,
        "first_source": start,
        "end_exclusive": end,
        "edit_speed": speed,
        "editor_notes": note,
    }
    if reveal_frames:
        selection["scan_dissolve_frames"] = reveal_frames
    write_json(PRODUCTION / "selections" / (name + ".json"), selection)
    print(json.dumps(selection, ensure_ascii=False), flush=True)


def join_volley(prefix_end, first_frame):
    # Cut on the same closed-shell pose and keep the first volley's exact shot timing.
    first = json.loads((PRODUCTION / "selections/c1_w_pangolin_roof.json").read_bytes())
    record = PRODUCTION / "selections/c1_pangolin_threat.json"
    loop = json.loads(record.read_bytes())
    template = WORK / "takes" / loop["candidate"] / "source.mp4"
    dest = ROOT / loop["file"]
    first_file = ROOT / first["file"]
    temp = dest.with_suffix(".part.mp4")
    vf = (
        f"[0:v]trim=end_frame={prefix_end},setpts=PTS-STARTPTS,scale=1280:720,setsar=1[a];"
        f"[1:v]trim=start_frame={first_frame},setpts=PTS-STARTPTS,setsar=1[b];"
        "[a][b]concat=n=2:v=1:a=0[out]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(template),
            "-i",
            str(first_file),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-filter_complex",
            vf,
            "-map",
            "[out]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-threads",
            "4",
            "-preset",
            "veryfast",
            "-crf",
            "17",
            "-bf",
            "0",
            "-g",
            "24",
            "-r",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(temp),
        ],
        check=True,
    )
    actual = int(
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
                str(temp),
            ],
            text=True,
        ).strip()
    )
    expected = prefix_end + first["frames"] - first_frame
    if actual != expected:
        raise ValueError(f"Joined frames {actual}, expected {expected}")
    temp.replace(dest)
    loop.update(
        sha256=hash_file(dest),
        frames=actual,
        shared_flight={
            "source": first["file"],
            "source_sha256": first["sha256"],
            "source_start_frame": first_frame,
            "loop_start_frame": prefix_end,
            "frame_offset": prefix_end - first_frame,
        },
    )
    write_json(record, loop)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    t = sub.add_parser("take")
    t.add_argument("ids", nargs="+", choices=catalog())
    t.add_argument("--variants", type=int, nargs="+", default=[1])
    a = sub.add_parser("anchor")
    a.add_argument("id", choices=catalog())
    a.add_argument("slot")
    a.add_argument("source", type=Path)
    a.add_argument("frame", type=int)
    sel = sub.add_parser("publish")
    sel.add_argument("id", choices=catalog())
    sel.add_argument("variant", type=int)
    sel.add_argument("--start", type=int, default=0)
    sel.add_argument("--end", type=int)
    sel.add_argument("--speed", type=float, default=1)
    sel.add_argument("--reveal-frames", type=int, default=0)
    sel.add_argument("--note", required=True)
    splice = sub.add_parser("join-volley")
    splice.add_argument("prefix_end", type=int)
    splice.add_argument("first_frame", type=int)
    args = p.parse_args()
    if args.command == "take":
        for variant in args.variants:
            for name in args.ids:
                take(name, variant)
    if args.command == "anchor":
        extract(args.id, args.slot, args.source, args.frame)
    if args.command == "publish":
        publish(
            args.id,
            args.variant,
            args.start,
            args.end,
            args.speed,
            args.note,
            args.reveal_frames,
        )
    if args.command == "join-volley":
        join_volley(args.prefix_end, args.first_frame)
    refresh()


if __name__ == "__main__":
    main()
