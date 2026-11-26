"""Assemble Linyuan runtime data from approved, hash-bound frame annotations."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/player"))
from check_linyuan import check_bamboo, check_dialogue, check_story
ROUTE = ["fox_shrine", "bifang_canopy", "suanni_rock", "suanni_steps",
         "fox_grove", "suanni_steps", "bifang_canopy", "suanni_rock",
         "pangolin_roof", "raft"]
NODE_MATERIALS = {
    "fox_shrine": "ceramic", "fox_grove": "ceramic", "bifang_canopy": "feather",
    "suanni_rock": "ceramic", "suanni_steps": "ceramic",
    "pangolin_roof": "ceramic", "raft": "vine",
}
SCENE_ATTACKS = {
    "fox_shrine": "claw", "fox_grove": "claw", "bifang_canopy": "collision",
    "suanni_rock": "claw", "suanni_steps": "collision",
    "pangolin_roof": "blast", "raft": "collision",
}
TAKES = ("c1_04_noodle", "c1_10_talon", "c1_11_hit", "c1_11_miss", "c1_12_thanks", "c1_12_rebuke")
COMBAT_LINES = {"scan": "等它现形，再出剑！", "needles": "飞针！打下来！",
                "elite_core": "它背上的鳞扇中间，打核心！", "raft": "打断那根藤索！"}


def _is_compact_list(value):
    if not isinstance(value, list):
        return False
    if all(isinstance(x, (int, float, bool, str)) or x is None for x in value):
        return True
    if all(isinstance(x, list) and all(isinstance(y, (int, float)) for y in x) for x in value):
        return True
    return False


def dump_compact_json(value, level=0):
    if isinstance(value, dict):
        if not value:
            return "{}"
        pad = "  " * (level + 1)
        items = [f"{pad}{json.dumps(k, ensure_ascii=False)}: {dump_compact_json(v, level + 1)}"
                 for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + ("  " * level) + "}"
    if isinstance(value, list):
        if _is_compact_list(value):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if not value:
            return "[]"
        pad = "  " * (level + 1)
        items = [f"{pad}{dump_compact_json(v, level + 1)}" for v in value]
        return "[\n" + ",\n".join(items) + "\n" + ("  " * level) + "]"
    return json.dumps(value, ensure_ascii=False)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_compact_json(value) + "\n", encoding="utf8")


def silhouette(poses, frame):
    """Interpolate authored polygons with equal vertex counts."""
    keys = poses
    if not keys or frame < keys[0]["frame"] or frame > keys[-1]["frame"]:
        raise ValueError(f"Annotation does not cover frame {frame}")
    for left, right in zip(keys, keys[1:]):
        if left["frame"] <= frame <= right["frame"]:
            a, b = np.array(left["polygon"], float), np.array(right["polygon"], float)
            if a.shape != b.shape or len(a) < 3:
                raise ValueError("Tracked polygon vertex count changed")
            weight = (frame - left["frame"]) / (right["frame"] - left["frame"])
            return np.rint(a + weight * (b - a)).astype(np.int32)
    return np.array(keys[-1]["polygon"], np.int32)

def keys_for(poses, spec, path):
    if not poses:
        raise ValueError(f"Missing tracked silhouette: {path}")
    previous = -1
    for pose in poses:
        if not previous < pose["frame"] < spec["frames"]:
            raise ValueError(f"Invalid tracked pose: {path}")
        rings = pose["rings"] if "rings" in pose else [pose["polygon"]]
        for ring in rings:
            points = np.asarray(ring, dtype=float)
            if (points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or
                    not np.isfinite(points).all() or np.any(points < 0) or np.any(points >= [1280, 720])):
                raise ValueError(f"Invalid source-pixel polygon: {path} frame {pose['frame']}")
        previous = pose["frame"]
    return poses


def mask(path, spec, windows, poses, weak=False):
    keys = keys_for(poses, spec, path)
    dense = {k["frame"]: k["rings"] for k in keys if "rings" in k}
    payload = bytearray(b"DCM1" + bytes.fromhex(spec["sha256"]))
    payload.extend(struct.pack("<H", spec["frames"]))
    for frame in range(spec["frames"]):
        spans = []
        active = any(w["begin"] <= frame < w["end"] for w in windows)
        if active and (not weak or keys[0]["frame"] <= frame <= keys[-1]["frame"]):
            image = np.zeros((360, 640), np.uint8)
            if dense:
                if frame not in dense:
                    raise ValueError(f"Missing exact-frame rings: {path.name} frame {frame}")
                rings = [np.asarray(r, np.int32) // 2 for r in dense[frame]]
            else:
                rings = [silhouette(keys, frame) // 2]
            if rings:
                cv2.fillPoly(image, rings, 1)
            # Each padded row transitions 0→1 at the inclusive start, 1→0 at the exclusive end.
            ys, xs = np.nonzero(np.diff(np.pad(image, ((0, 0), (1, 1))), axis=1))
            spans = list(zip(ys[::2], xs[::2], xs[1::2]))
        payload.extend(struct.pack("<H", len(spans)))
        for span in spans:
            payload.extend(struct.pack("<HHH", *span))
    path.write_bytes(payload)


def assemble(root, binding):
    root = root.resolve()
    # Keep published data intact if a late annotation or a selected file is invalid.
    with tempfile.TemporaryDirectory(prefix=".linyuan-assemble-", dir=root) as temp:
        staging = Path(temp)
        level = build(root, binding, staging)
        world = root / "worlds/linyuan"
        old_level = world / "bamboo/level.json"
        old_clips = json.loads(old_level.read_text(encoding="utf8"))["clips"] if old_level.is_file() else {}
        for path in sorted((p for p in staging.rglob("*") if p.is_file()),
                           key=lambda p: (p.name in {"level.json", "mvp.json", "start.json"}, p.name)):
            dest = root / path.relative_to(staging)
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.replace(dest)
        for key, old in old_clips.items():
            if not re.fullmatch("[a-z0-9_]+", key):
                continue
            new = level["clips"].get(key, {})
            for field, ending in (("windows", ".mask"), ("weak_mask", ".weak.mask")):
                if old.get(field) and not new.get(field):
                    (world / "bamboo" / (key + ending)).unlink(missing_ok=True)
        return level


def build(root, binding, staging):
    world = staging / "worlds/linyuan"
    folder = world / "bamboo"
    folder.mkdir(parents=True, exist_ok=True)
    videos = binding["videos"]
    selected = {}

    def select(media):
        if media not in selected:
            if not re.fullmatch("[a-z0-9_]+", media):
                raise ValueError(f"Invalid runtime media ID: {media}")
            source = videos[media]
            file = root / source["file"]
            if not file.is_file() or not 1 <= source["frames"] <= 65535:
                raise ValueError(f"Invalid selected media: {media} at {file}")
            relative = Path("assets/linyuan") / ("drama" if media in TAKES else "bamboo") / (media + ".mp4")
            dest = root / relative
            if file.resolve() != dest.resolve():
                staged = staging / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, staged)
                file = staged
            with file.open("rb") as handle:
                sha = hashlib.file_digest(handle, "sha256").hexdigest()
            if sha != source["sha256"]:
                raise ValueError(f"Edited media requires new annotation: {media}")
            selected[media] = dict(frames=source["frames"], sha256=sha)
        return selected[media]

    def clip(media, following, windows=None, **extra):
        source = videos[media]
        return dict(media=media, **select(media), start=0,
                    in_anchor=source.get("in_anchor", "bamboo"),
                    out_anchor=source.get("out_anchor", "bamboo"),
                    next=following, windows=windows or [], **extra)

    nodes, clips = [], {}
    for index, name in enumerate(ROUTE):
        current = f"wave_{index + 1:02}"
        following = f"wave_{index + 2:02}" if index < 9 else "@complete"
        media = "c1_w_" + name
        source = videos[media]
        node = dict(id=current, label={"fox_shrine": "等隐狐现形，再出剑",
                    "fox_grove": "隐狐", "bifang_canopy": "毕方",
                    "suanni_rock": "狻猊", "suanni_steps": "狻猊",
                    "pangolin_roof": "鲮鲤", "raft": "打断藤索" }[name],
                    hp=2 if name == "pangolin_roof" else 1, score=700 if name == "pangolin_roof" else 100,
                    material=NODE_MATERIALS[name],
                    tier=3 if name == "pangolin_roof" else (2 if index in (7, 9) else 1))
        nodes.append(node)
        if name == "pangolin_roof":
            node["flinch"] = "elite_flinch"
            windows = []
            for begin, end, anchor in source["intercept_windows"]:
                dest = f"elite_intercept_{anchor}"
                windows.append(dict(begin=begin, end=end, node=index,
                                    kind="projectile", hit=dest))
                clips[dest] = clip(f"c1_pangolin_intercept_{anchor}", "elite_core")
            clips[current] = clip(media, "elite_impact", windows, end=source["impact"] + 1,
                launch_frame=source["launch"], impact_frame=source["impact"],
                warning_frame=source["warning"], attack=SCENE_ATTACKS[name])
            cycle = videos["c1_pangolin_threat"]
            cycle_windows = [dict(begin=a, end=b, node=index, kind="projectile",
                                  hit=f"elite_intercept_{anchor}")
                             for a, b, anchor in cycle["intercept_windows"]]
            clips["elite_launch"] = clip("c1_pangolin_threat", "elite_impact", cycle_windows, end=cycle["impact"] + 1,
                launch_frame=cycle["launch"], impact_frame=cycle["impact"],
                warning_frame=cycle["warning"], attack="blast")
            clips["elite_launch"]["start"] = min(10, cycle["warning"])
            clips["elite_launch"]["speed"] = 1.2
            clips["elite_impact"] = clip("c1_pangolin_impact", "elite_launch", attack="blast")
            last = source["frames"] - 1
            clips["elite_core"] = clip(media, "elite_launch",
                [dict(begin=last, end=last + 1, node=index, kind="target", hit="elite_kill", weak=True)],
                hold_seconds=2., attack="blast")
            clips["elite_core"]["start"] = last
            clips["elite_flinch"] = clip("c1_pangolin_flinch", "elite_launch")
            clips["elite_kill"] = clip("c1_pangolin_kill", following)
        else:
            if name != "raft":
                node["weak_bonus"] = 50
            if index == 7:
                node.update(hp=2, weak_damage=2, flinch=current, label="重甲狻猊 · 瞄准琥珀肩罐")
            if index == 9:
                node.update(score=400, kills=2, fixed_score=True)
            windows = []
            entries = source["hit_windows"]
            for begin, end, anchor in entries:
                dest = current + "_hit_" + str(anchor)
                result = f"c1_raft_drop_{anchor}" if index == 9 else media + "_kill_" + str(anchor)
                windows.append(dict(begin=begin, end=end, node=index, kind="target", hit=dest))
                clips[dest] = clip(result, following)
            clips[current] = clip(media, current, windows, warning_frame=source["warning"],
                                  impact_frame=source["impact"], attack=SCENE_ATTACKS[name])
            start = source.get("start", 0)
            if index in (5, 6, 7):
                # Keep each real early/middle/late result take reachable even on shorter source cuts.
                start = min(start + (12, 14, 14)[index - 5], entries[0][1] - 1)
                windows[0]["begin"] = max(windows[0]["begin"], start)
            clips[current]["start"] = start
            if name.startswith("fox_"):
                clips[current]["allow_early_miss"] = True
            if "end" in source:
                clips[current]["end"] = source["end"]
            if "material_transforms" in source:
                clips[current]["material_transforms"] = source["material_transforms"]
            if source.get("weak_regions"):
                clips[current]["weak_mask"] = True
            elif name != "raft":
                raise ValueError(f"Amber weak region missing from {media}")
    for key, line in (("wave_01", "scan"), ("wave_09", "needles"),
                      ("elite_core", "elite_core"), ("wave_10", "raft")):
        spec = clips[key]
        source = videos[spec["media"]]
        # A production binding may place the call earlier than opening. Both moments
        # refer to the visible source frames, including the repeated final core frame.
        frame = source.get("cue_frames", {}).get(line, spec["start"])
        if not spec["start"] <= frame <= spec["windows"][0]["begin"]:
            raise ValueError(f"Voice misses first window: {key}/{line}")
        spec["voice_cues"] = [dict(frame=frame, voice="qingping/" + line,
                                   subtitle=COMBAT_LINES[line], priority=2 if line == "needles" else 1)]
    for key, spec in clips.items():
        if spec["windows"]:
            source_spec = videos[spec["media"]]
            poses = source_spec.get("core_regions") if key == "elite_core" else source_spec.get("regions")
            mask(folder / (key + ".mask"), spec, spec["windows"], poses)
            if spec.get("weak_mask"):
                mask(folder / (key + ".weak.mask"), spec, spec["windows"],
                     source_spec.get("weak_regions"), weak=True)

    level = dict(version=1, ruleset="linyuan", title="临渊御剑", fps=24, size=[1280, 720],
                 first="wave_01", selectable_difficulty=False, location="九曲渡 · 后山竹海",
                 briefing="左键出剑 · 右键或 R 收剑", cleared="竹海已平",
                 nodes=nodes, clips=clips, plate=dict(media="c1_bamboo_plate", **select("c1_bamboo_plate")))
    level["materials"] = binding["materials"]
    level["materials_sha256"] = binding["materials_sha256"]
    check_bamboo(level, folder)
    write(folder / "level.json", level)
    write(world / "drama.json", {key: select(key) for key in TAKES})
    if len(selected) != len(TAKES) + 31:
        raise ValueError(f"Incomplete MVP video inventory: assembled {len(selected)}")
    talon = binding["story"]["talon"]
    annotation = dict(sha256=videos["c1_10_talon"]["sha256"], regions=talon["regions"])
    trial = dict(first="talon", steps=dict(talon=dict(take="c1_10_talon", story_shot=True,
        window=[talon["window_start"], 24], window_seconds=2., window_rate=.5,
        cues=talon["cues"], prompt="瞄准琥珀燃料囊 · 保护云姨",
        zones=["sac", "yunyi"], guards=["yunyi"], answer="sac", outcomes={
            "sac": dict(points=1000, response="c1_11_hit", next="@complete"),
            "miss": dict(response="c1_11_miss", next="@complete"),
            "timeout": dict(response="c1_11_miss", next="@complete"),
            "yunyi": dict(points=-100, damage=1, civilian=True,
                          response="c1_11_miss", next="@complete")})))
    check_story(selected["c1_10_talon"], trial["steps"]["talon"], annotation)
    check_dialogue(binding["noodle_cues"], ("qingping/noodle", "luchen/noodle"), selected["c1_04_noodle"]["frames"])
    write(world / "regions/c1_10_talon.json", annotation)
    stages = [
        dict(id="noodle", type="film", takes=[dict(id="c1_04_noodle",
             cues=binding["noodle_cues"])]),
        dict(id="save_yunyi", type="trial", trial=trial),
        dict(id="yunyi_reply", type="film", takes=[
             dict(id="c1_12_thanks", after_civilian=False, voice="yunyi/thanks", subtitle="云姨  手还在，面也没凉。快去！"),
             dict(id="c1_12_rebuke", after_civilian=True, voice="yunyi/rebuke", subtitle="云姨  瞄准点儿！还不快去！")]),
        dict(id="bamboo_card", type="card", text="九曲渡 · 后山竹海", milliseconds=1000),
        dict(id="bamboo", type="encounter", level="bamboo", music="battle")]
    write(world / "mvp.json", dict(title="临渊御剑", chapters=[
        dict(id="mvp", heading="九曲渡 · 后山竹海", stages=stages)]))
    write(world / "start.json", dict(campaign="mvp"))
    return level


def assemble_pilot(root, binding):
    """Publish the four selected first-pass clips under an explicit --campaign pilot entry."""
    root = root.resolve()
    world = root / "worlds/linyuan"
    videos = binding["videos"]
    lion, fox, kill = "c1_w_suanni_rock", "c1_w_fox_shrine", "c1_w_suanni_rock_kill_35"
    clips = {}
    nodes = []
    with tempfile.TemporaryDirectory(prefix=".linyuan-pilot-", dir=root) as temp:
        staging = Path(temp)
        bamboo = staging / "worlds/linyuan/pilot"
        bamboo.mkdir(parents=True)
        for name in (lion, fox, kill, TAKES[0]):
            source = videos[name]
            path = root / source["file"]
            with path.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != source["sha256"]:
                    raise ValueError(f"Stale pilot binding: {name}")
            runtime = Path("assets/linyuan") / ("drama" if name == TAKES[0] else "pilot") / (name + ".mp4")
            if path.resolve() != (root / runtime).resolve():
                target = staging / runtime
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        for index, media in enumerate((lion, lion, fox)):
            name = f"pilot_{index+1}"
            source = videos[media]
            kill_id = name + "_hit" if index < 2 else "@complete"
            nodes.append(dict(id=name, label="狻猊肩罐" if index < 2 else "等隐狐现形",
                              hp=1, score=100, weak_bonus=50 if index < 2 else 0,
                              material="ceramic", tier=1))
            windows = [dict(begin=source["hit_windows"][0][0], end=source["hit_windows"][-1][1],
                            kind="target", node=index, hit=kill_id)]
            wave = dict(media=media, sha256=source["sha256"], frames=source["frames"], start=source.get("start", 0),
                        in_anchor="bamboo", out_anchor="bamboo", next=name, windows=windows,
                        warning_frame=source["warning"], impact_frame=source["impact"], attack="claw")
            if "end" in source:
                wave["end"] = source["end"]
            clips[name] = wave
            mask(bamboo / (name + ".mask"), wave, windows, source["regions"])
            if index < 2:
                wave["weak_mask"] = True
                mask(bamboo / (name + ".weak.mask"), wave, windows, source["weak_regions"], weak=True)
                clips[kill_id] = dict(media=kill, frames=videos[kill]["frames"], sha256=videos[kill]["sha256"],
                                      next=f"pilot_{index+2}", in_anchor="lion_mid", out_anchor="bamboo")
            else:
                wave["voice_cues"] = [dict(frame=wave["start"], voice="qingping/scan", subtitle=COMBAT_LINES["scan"], priority=1)]
        level = dict(version=1, ruleset="linyuan", fps=24, size=[1280, 720], title="临渊御剑 · 首批试剑",
                     location="后山竹海", briefing="左键出剑 · 右键收剑", cleared="试剑完成",
                     first="pilot_1", nodes=nodes, clips=clips)
        if "materials" in binding:
            level["materials"] = binding["materials"]
        write(bamboo / "level.json", level)
        first = videos[TAKES[0]]
        check_dialogue(binding["noodle_cues"], ("qingping/noodle", "luchen/noodle"), first["frames"])
        drama_path = world / "drama.json"
        drama = json.loads(drama_path.read_bytes()) if drama_path.is_file() else {}
        drama[TAKES[0]] = {k: first[k] for k in ("sha256", "frames")}
        write(staging / "worlds/linyuan/drama.json", drama)
        stages = [dict(id="noodle", type="film", takes=[dict(id=TAKES[0], cues=binding["noodle_cues"])]),
                  dict(id="pilot", type="encounter", level="pilot", music="battle")]
        write(staging / "worlds/linyuan/pilot.json", dict(title="临渊御剑 · 首批试剑", chapters=[
            dict(id="pilot", heading="九曲渡 · 后山竹海", stages=stages)]))
        for path in sorted((p for p in staging.rglob("*") if p.is_file()), key=lambda p:p.name == "pilot.json"):
            dest = root / path.relative_to(staging)
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.replace(dest)
    return level


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--bindings", type=Path)
    parser.add_argument("--pilot", action="store_true", help="Build just the four selected first-pass film IDs")
    args = parser.parse_args()
    path = args.bindings or args.root / "worlds/linyuan/production/bindings.json"
    (assemble_pilot if args.pilot else assemble)(args.root, json.loads(path.read_text(encoding="utf8")))
