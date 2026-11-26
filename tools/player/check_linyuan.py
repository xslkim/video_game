"""Verify Linyuan's actual media, annotations, graph and replay outcomes."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import struct
import subprocess
import wave

from check_changan import validate_graph

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)

def check_dialogue(cues, voices, last_frame):
    require([c["voice"] for c in cues] == list(voices), f"Dialogue order must be {voices}")
    previous = 0
    for cue in cues:
        require(previous <= cue["begin"] < cue["end"] <= last_frame and cue["subtitle"].strip(),
                f"Invalid first/last subtitle frame: {cue['voice']}")
        previous = cue["end"]


def check_story(spec, step, annotation):
    require(annotation["sha256"] == spec["sha256"], f"Stale regions: {step['take']}")
    begin, count = step["window"]
    require(step["story_shot"] and step["window_seconds"] == 2 and step["window_rate"] == .5 and
            count == 24 and 0 <= begin < begin + count <= spec["frames"],
            "Story shot must provide a real two-second half-speed window")
    check_dialogue(step["cues"], ("yunyi/talon", "qingping/talon"), begin)
    require(step["zones"] == ["sac", "yunyi"] and step["guards"] == ["yunyi"] and step["answer"] == "sac",
            "Story target and protected body must be separate")
    for zone in step["zones"]:
        poses = annotation["regions"][zone]
        require(poses and poses[0]["frame"] <= begin and poses[-1]["frame"] >= begin + count - 1,
                f"Incomplete region: {zone}")
        previous = -1
        vertices = len(poses[0]["polygon"])
        for pose in poses:
            require(previous < pose["frame"] < spec["frames"] and vertices >= 3 and
                    len(pose["polygon"]) == vertices and
                    all(len(p) == 2 and all(math.isfinite(v) for v in p) and
                        0 <= p[0] < 1280 and 0 <= p[1] < 720 for p in pose["polygon"]),
                    f"Invalid tracked pose: {zone}")
            previous = pose["frame"]
    outcomes = step["outcomes"]
    require(set(outcomes) == {"sac", "yunyi", "miss", "timeout"} and
            outcomes["sac"]["points"] == 1000 and outcomes["yunyi"]["points"] == -100 and
            outcomes["yunyi"]["damage"] == 1 and outcomes["yunyi"]["civilian"] and
            all(o["response"] == ("c1_11_hit" if key == "sac" else "c1_11_miss") and
                o["next"] == "@complete" for key, o in outcomes.items()), "Invalid story outcomes")


def media(path, spec):
    require(path.is_file(), f"Missing media: {path}")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"], f"Stale media: {path}")
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-count_packets", "-show_streams", "-of", "json", str(path)],
        text=True)
    streams = json.loads(output)["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    require(video is not None and audio is not None, f"Missing required video or audio stream: {path}")
    require((video["codec_name"], video["width"], video["height"], video["avg_frame_rate"],
             video["pix_fmt"], video["has_b_frames"], int(video["nb_read_packets"])) ==
            ("h264", 1280, 720, "24/1", "yuv420p", 0, spec["frames"]), f"Unsupported video: {path}")
    require((audio["codec_name"], audio["sample_rate"], audio["channels"]) ==
            ("aac", "48000", 2), f"Unsupported audio: {path}")


def read_mask(path, spec, body=None):
    rows = []
    with path.open("rb") as stream:
        def chunk(n):
            data = stream.read(n)
            require(len(data) == n, f"Truncated mask: {path}")
            return data

        require(stream.read(4) == b"DCM1", f"Invalid mask: {path}")
        require(stream.read(32).hex() == spec["sha256"], f"Stale mask: {path}")
        require(struct.unpack("<H", chunk(2))[0] == spec["frames"], f"Mask length: {path}")
        for frame in range(spec["frames"]):
            count, = struct.unpack("<H", chunk(2))
            window = next((w for w in spec.get("windows", []) if w["begin"] <= frame < w["end"]), None)
            require((bool(count) == bool(window)) if body is None
                    else (not count or (window and window["kind"] == "target")),
                    f"Mask/window disagree: {path} frame {frame}")
            previous = (-1, -1)
            spans = list(struct.iter_unpack("<HHH", chunk(6 * count)))
            body_index = 0
            for y, start, end in spans:
                require(0 <= y < 360 and 0 <= start < end <= 640 and
                        (y > previous[0] or (y == previous[0] and start >= previous[1])),
                        f"Invalid span: {path} frame {frame}")
                previous = (y, end)
                if body is not None:
                    coverage = body[frame]
                    x = start
                    while body_index < len(coverage) and (coverage[body_index][0] < y or
                            (coverage[body_index][0] == y and coverage[body_index][2] <= x)):
                        body_index += 1
                    while x < end and body_index < len(coverage):
                        row, left, right = coverage[body_index]
                        if row != y or left > x:
                            break
                        x = right
                        if x < end:
                            body_index += 1
                    require(x >= end, f"Weak region outside body: {path} frame {frame}")
            rows.append(spans)
        require(not stream.read(1), f"Trailing mask bytes: {path}")
        require(any(rows), f"Empty annotated mask: {path}")
    return rows


def check_threat_glows(level, path):
    tracks = read(path)
    for scene in level["clips"].values():
        impact = scene.get("impact_frame", -1)
        if impact < 0:
            continue
        name = scene["media"]
        track = tracks.get(name, {})
        require(track.get("sha256") == scene["sha256"], f"Stale or missing attack glow track: {name}")
        poses = track["points"]
        frames = set()
        for pose in poses:
            require(len(pose) in (3, 5) and pose[0] not in frames and 0 <= pose[0] < scene["frames"] and
                    all(0 <= x < level["size"][0] and 0 <= y < level["size"][1]
                        for x, y in zip(pose[1::2], pose[2::2])), f"Invalid attack glow position: {name}")
            frames.add(pose[0])
        start = max(scene["start"], scene["warning_frame"], impact-math.floor(12*scene.get("speed", 1)))
        require(set(range(start, impact)) <= frames, f"Incomplete last half-second of attack glow: {name}")


def check_bamboo(level, folder):
    validate_graph(level)
    if (folder / "threat_glows.json").is_file():
        check_threat_glows(level, folder / "threat_glows.json")
    require(level.get("ruleset") == "linyuan" and level["size"] == [1280, 720]
            and len(level["nodes"]) == 10, "Wrong bamboo route")
    grid = level.get("materials", [])
    surfaces = {"air", "bamboo", "earth", "metal", "stone", "water"}
    require(level.get("materials_sha256") == level["plate"]["sha256"] and len(grid) == 36 and
            all(len(row) == 64 and all(cell in surfaces for cell in row) for row in grid),
            "Material grid must bind 64 x 36 cells to the selected bamboo plate")
    nodes, clips = level["nodes"], level["clips"]
    elite = nodes[8]
    require(elite["hp"] == 2 and elite["score"] == 700 and elite["flinch"] == "elite_flinch",
            "Wrong elite strength/award")
    require(nodes[9]["kills"] == 2 and nodes[9]["score"] == 400 and nodes[9]["fixed_score"],
            "Rope must award 400 and count two victims")
    core = clips["elite_core"]
    core_start = core["frames"] - 1
    require(core["hold_seconds"] == 2. and core["start"] == core_start
            and core["next"] == "elite_launch" and core.get("impact_frame", -1) == -1
            and core["windows"] == [dict(begin=core_start, end=core_start + 1, node=8,
                                         kind="target", hit="elite_kill", weak=True)],
            "Elite needs a held two-second core before refiring")
    require(clips["elite_flinch"]["next"] == clips["elite_impact"]["next"] == "elite_launch"
            and clips["elite_launch"]["speed"] > 1, "Elite must close its core and refire")
    require(nodes[7]["hp"] == nodes[7]["weak_damage"] == 2 and nodes[7]["flinch"] == "wave_08",
            "Heavy armor needs two body hits or a single direct weak hit")
    for index, node in enumerate(nodes):
        wave = clips[node["id"]]
        require(node.get("material") in {"ceramic", "feather", "vine", "crystal", "metal", "phantom"} and
                node.get("tier") in {1, 2, 3},
                f"Missing or invalid node material/tier: {node['id']}")
        require(wave.get("attack") in {"claw", "collision", "blast"},
                f"Missing or invalid wave attack profile: {node['id']}")
        windows = wave["windows"]
        kind = "projectile" if index == 8 else "target"
        count = 2 if index in (8, 9) else 3
        require(len(windows) == count and len({w["hit"] for w in windows}) == count and
                all(w["node"] == index and w["kind"] == kind for w in windows) and
                all(a["end"] == b["begin"] for a, b in zip(windows, windows[1:])),
                f"Missing or discontinuous cut range: {node['id']}")
        if index != 8:
            require(wave["next"] == node["id"], f"Failed attack must retry {node['id']}")
            following = nodes[index+1]["id"] if index < 9 else "@complete"
            require(all(clips[w["hit"]]["next"] == following for w in windows),
                    f"Wrong kill successor: {node['id']}")
        if index in (0, 4):
            require(windows[0]["begin"] > wave["start"] and wave.get("allow_early_miss"),
                    "Early fox shots must miss before the visible target window")
        if index < 8:
            require(node["weak_bonus"] == 50 and wave.get("weak_mask"), f"Missing amber region: {node['id']}")
        if index in (5, 6, 7):
            previous = clips[{5:"wave_04", 6:"wave_02", 7:"wave_03"}[index]]
            require(wave["media"] == previous["media"] and wave["start"] > previous["start"] and
                    windows[0]["begin"] > previous["windows"][0]["begin"], f"Repeated wave is not accelerated: {node['id']}")
    for key in ("wave_09", "elite_launch"):
        shots = clips[key]
        targets = [w["hit"] for w in shots["windows"]]
        require(targets == ["elite_intercept_early", "elite_intercept_late"] and
                all(w["node"] == 8 and w["kind"] == "projectile" for w in shots["windows"]) and
                shots["windows"][0]["end"] == shots["windows"][1]["begin"] and
                shots.get("end") == shots["impact_frame"] + 1 and
                shots["next"] == "elite_impact" and all(clips[t]["next"] == "elite_core" for t in targets),
                f"Incorrect needle anchors or return: {key}")
    by_media = {}
    for name, spec in clips.items():
        media_id = spec["media"]
        start, end = spec.get("start", 0), spec.get("end", spec["frames"])
        require(0 <= start < end <= spec["frames"] and
                all(start <= w["begin"] < w["end"] <= end for w in spec["windows"]) and
                all(start <= spec[k] < end for k in ("launch_frame", "impact_frame", "warning_frame") if k in spec) and
                all(start <= cue["frame"] < end for cue in spec.get("voice_cues", [])),
                f"Window or event outside playback range: {name}")
        if "material_transforms" in spec:
            poses = spec["material_transforms"]
            active = [f for w in spec["windows"] for f in range(w["begin"], w["end"])]
            require([p["frame"] for p in poses] == active and
                    all(len(p["to_plate"]) == 9 and all(math.isfinite(v) for v in p["to_plate"])
                        for p in poses), f"Incomplete source-to-plate registration: {name}")
        old = by_media.setdefault(media_id, spec)
        require(old["sha256"] == spec["sha256"] and old["frames"] == spec["frames"],
                f"Conflicting metadata for reused {media_id} in {name}")
        if spec["windows"]:
            body = read_mask(folder / (name + ".mask"), spec)
            if spec.get("weak_mask"):
                read_mask(folder / (name + ".weak.mask"), spec, body=body)
    plate = level["plate"]
    require(plate["media"] == "c1_bamboo_plate" and len(by_media) == 30, "Incomplete bamboo media")
    return {**by_media, plate["media"]: plate}


def check_audio_references(folder, stages, scenes):
    references = set()

    def collect(node):
        if isinstance(node, list):
            for item in node:
                collect(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in ("voice", "response_voice") and value:
                    require(isinstance(value, str) and re.fullmatch(r"[a-z0-9_]+/[a-z0-9_]+", value),
                            f"Invalid voice identifier: {value}")
                    references.add(folder / "voice" / (value + ".wav"))
                elif key == "music" and value:
                    require(isinstance(value, str) and re.fullmatch(r"[a-z0-9_]+", value),
                            f"Invalid music identifier: {value}")
                    references.add(folder / "music" / (value + ".wav"))
                else:
                    collect(value)

    collect(stages)
    collect(scenes)
    for path in sorted(references):
        require(path.is_file(), f"Missing referenced audio: {path}")
        try:
            with wave.open(str(path), "rb") as wav:
                require(wav.getnframes() > 0 and wav.getframerate() > 0 and
                        wav.getsampwidth() in (1, 2, 3, 4) and wav.getnchannels() in (1, 2) and
                        wav.getcomptype() == "NONE", f"Unsupported referenced WAV: {path}")
                if path.parent == folder / "music":
                    require((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 2, 2),
                            f"Campaign music requires 48 kHz stereo PCM16: {path}")
                wav.setpos(wav.getnframes() - 1)
                require(len(wav.readframes(1)) == wav.getnchannels() * wav.getsampwidth(),
                        f"Truncated referenced WAV: {path}")
        except (OSError, EOFError, wave.Error) as error:
            raise ValueError(f"Unreadable referenced WAV: {path}") from error


def validate(root):
    world = root / "worlds/linyuan"
    mvp_file = world / "mvp.json"
    campaign = read(mvp_file if mvp_file.is_file() else world / (read(world / "start.json")["campaign"] + ".json"))
    stages = [s for chapter in campaign["chapters"] for s in chapter["stages"]]
    require([s["type"] for s in stages] == ["film", "trial", "film", "card", "encounter"],
            "MVP must enter film, trial, card and encounter through the campaign")
    drama = read(world / "drama.json")
    mvp_takes = {"c1_04_noodle", "c1_10_talon", "c1_11_hit", "c1_11_miss", "c1_12_thanks", "c1_12_rebuke"}
    require(mvp_takes <= set(drama), "Incomplete drama inventory")
    for name in mvp_takes:
        media(root / "assets/linyuan/drama" / (name + ".mp4"), drama[name])
    for stage in stages:
        if stage["type"] == "film":
            if stage["id"] == "yunyi_reply":
                require([(t.get("after_civilian"), t["id"], t["voice"]) for t in stage["takes"]] ==
                        [(False, "c1_12_thanks", "yunyi/thanks"), (True, "c1_12_rebuke", "yunyi/rebuke")],
                        "Yunyi needs matching clean and civilian dialogue outcomes")
            require(all(t["id"] in drama for t in stage["takes"]), f"Missing film: {stage['id']}")
            for take in stage["takes"]:
                if take["id"] == "c1_04_noodle":
                    check_dialogue(take["cues"], ("qingping/noodle", "luchen/noodle"), drama[take["id"]]["frames"])
        if stage["type"] == "trial":
            trial = stage["trial"]
            for step in trial["steps"].values():
                spec = drama[step["take"]]
                annotation = read(world / "regions" / (step["take"] + ".json"))
                check_story(spec, step, annotation)
    level = read(world / "bamboo/level.json")
    check_audio_references(root / "assets/linyuan/audio", stages, level["clips"])
    bamboo = check_bamboo(level, world / "bamboo")
    for media_id, spec in bamboo.items():
        media(root / "assets/linyuan/bamboo" / (media_id + ".mp4"), spec)
    return dict(stages=len(stages), bamboo_nodes=10, bamboo_media=len(bamboo), story_media=len(drama))


def validate_run(directory):
    run = read(directory / "bamboo/playthrough.json")
    require(run["ok"] and run["scenario"] == "normal", "Expected a completed normal route")
    require(run["hits"] == 13 and run["shots"] == 13, "Normal route must fire thirteen swords")
    require(run["lives"] == 3 and run["reloads"] == 1, "Normal route must finish without damage")
    require(run["intercepts"] == 2 and run["weak_returns"] >= 4, "Double needle defense or weak returns missing")
    require(run["kills"] == 11 and run["hurts"] == 0, "Wrong kill/damage count")
    kills = [e for e in run["events"] if e["event"] == "shot_purify"]
    require([e["node"] for e in kills] == list(range(1, 11)) and kills[-1]["arrows"] == run["arrows"],
            "Ten actual node advances and a consistent sword inventory required")
    timeline = read(directory / "timeline.json")
    require([e["stage"] for e in timeline] == ["noodle", "save_yunyi", "yunyi_reply", "bamboo_card", "bamboo"],
            "Missing full campaign entry or exit")
    trial = read(directory / "save_yunyi.json")
    require(len(trial) == 1 and trial[0]["input"] == "sac" and trial[0]["points"] == 1000 and
            trial[0]["arrows"] == 8 and trial[0]["damage"] == 0, "Missing clean story shot")
    return {k: run[k] for k in ("shots", "hits", "lives", "intercepts", "reloads")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_run(args.run) if args.run else validate(args.root),
                     ensure_ascii=False, indent=2))
