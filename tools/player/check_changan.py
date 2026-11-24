"""Validate the portable Changan encounter, media and frame masks."""

import argparse
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import struct
import subprocess


def validate_graph(level):
    clips = level["clips"]
    assert level["version"] == 1 and level["fps"] == 24
    nodes = level["nodes"]
    assert nodes and all(n["id"] and n["hp"] >= 1 and n["score"] >= 0 for n in nodes), "Invalid node"
    assert len({n["id"] for n in nodes}) == len(nodes), "Duplicate node id"
    assert level["first"] in clips, "Invalid opening clip"
    targets = set()
    if "street" in level:
        street = level["street"]
        assert 1 <= street["frames"] <= 65535, "Invalid street duration"
        assert re.fullmatch(r"[0-9a-f]{64}", street["sha256"]), "Invalid street hash"
        assert not level.get("market_entries"), "Conflicting street timelines"
    graph = {}
    for clip, info in clips.items():
        assert re.fullmatch(r"[a-z0-9_]+", clip) and re.fullmatch(r"[a-z0-9_]+", info.get("media", clip)), clip
        frames = info["frames"]
        last_end = info.get("start", 0)
        assert 0 <= last_end < frames <= 65535, clip
        launch = info.get("launch_frame", -1)
        impact = info.get("impact_frame", -1)
        assert info["in_anchor"] and info["out_anchor"], clip
        assert -1 <= impact < frames and -1 <= launch < frames, clip
        if launch >= 0:
            assert launch < impact, f"Attack ordering: {clip}"
        successors = {info["next"]}
        for region in info.get("windows", []):
            start, end, node = (region[field] for field in ("begin", "end", "node"))
            assert last_end <= start < end <= frames, f"Out of frame window: {clip}"
            assert 0 <= node < len(level["nodes"]), f"Invalid node: {clip}"
            role = region["kind"]
            assert role in ("target", "projectile", "civilian"), f"Invalid region: {clip}"
            if role == "target":
                targets.add(node)
            if role == "projectile":
                assert 0 <= launch <= start < end <= impact, f"Interception ordering: {clip}"
            elif role == "target" and impact >= 0:
                assert end <= (launch if launch >= 0 else impact), f"Late target window: {clip}"
            successors.add(region["hit"])
            if role == "target" and level["nodes"][node]["hp"] > 1:
                successors.add(level["nodes"][node]["flinch"])
            last_end = end
        for next_clip in successors:
            assert next_clip in clips or next_clip == "@complete", f"Missing clip from {clip}: {next_clip}"
        graph[clip] = successors
    assert targets == set(range(len(nodes))), "Node without a target window"
    seen = {"@complete"}
    while pending := {c for c, links in graph.items() if c not in seen and seen & links}:
        seen.update(pending)
    assert seen == set(clips) | {"@complete"}, "Branch without a path to completion"
    seen = set()
    pending = [level["first"]]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(graph.get(current, ()))
    assert seen == set(clips) | {"@complete"}, "Unreachable clip or terminal"
    occupied, files = set(), {}
    for e in level.get("market_entries", []):
        src, dest = e["source"], e["dest"]
        assert src in clips and dest in clips and re.fullmatch(r"entry_[0-9]+", e["take"]), e
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"]), e
        identity = (dest, e["sha256"], e["join"])
        assert files.setdefault(e["take"], identity) == identity, e
        assert 0 <= e["begin"] < e["end"] <= clips[src]["frames"], e
        assert 0 < e["join"] < clips[dest]["frames"], e
        assert all(w["begin"] > e["join"] for w in clips[dest].get("windows", [])), e
        for f in range(e["begin"], e["end"]):
            w = next((w for w in clips[src]["windows"] if w["begin"] <= f < w["end"]), None)
            assert w and (w["hit"] == dest or level["nodes"][w["node"]].get("flinch") == dest), e
            assert (src, dest, f) not in occupied, f"Overlapping market entrances: {src} {dest} {f}"
            occupied.add((src, dest, f))


def picture_hashes(path):
    lines = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
                                     "-f", "framemd5", "-"], text=True).splitlines()
    return [line.rsplit(",", 1)[-1].strip() for line in lines if line and not line.startswith("#")]


def audio_hash(path):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                                    "-c", "copy", "-f", "hash", "-"], text=True)


def verify_media(level, world, assets):
    width, height = level["size"]
    src = world / "production/media.json"
    provenance = json.loads(src.read_text(encoding="utf-8")) if src.exists() else None
    items = dict(level["clips"])
    if "street" in level:
        items["street"] = level["street"]
        assets = assets / "once"
    for clip, info in items.items():
        layer = "street" in level and clip != "street"
        media_id = info.get("media", clip)
        path = assets / (media_id + (".mkv" if layer else ".mp4"))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha == info["sha256"], f"Hash mismatch: {clip}"
        if provenance is not None:
            assert provenance[media_id]["final_sha256"] == sha and provenance[media_id]["h3_prompt_id"], clip
        result = subprocess.check_output(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                                         "stream=codec_type,codec_name,width,height,avg_frame_rate,"
                                         "nb_read_packets,has_b_frames,pix_fmt,sample_rate,channels",
                                         "-of", "json", str(path)], text=True)
        streams = json.loads(result)["streams"]
        v = next(s for s in streams if s["codec_type"] == "video")
        assert (v["width"], v["height"], v["avg_frame_rate"], v["has_b_frames"],
                int(v["nb_read_packets"]), v["pix_fmt"], v["codec_name"]) == (
                    width, height, "24/1", 0, info["frames"], "bgra" if layer else "yuv420p",
                    "ffv1" if layer else "h264"), clip
        a = next(s for s in streams if s["codec_type"] == "audio")
        assert (a["codec_name"], a["sample_rate"], a["channels"]) == ("aac", "48000", 2), clip
        windows = info.get("windows", [])
        if not windows:
            continue
        with (world / (clip + ".mask")).open("rb") as f:
            assert f.read(4) == b"DCM1" and f.read(32).hex() == sha, f"Mask stale: {clip}"
            frame_count, = struct.unpack("<H", f.read(2))
            assert frame_count == info["frames"], clip
            for index in range(frame_count):
                count, = struct.unpack("<H", f.read(2))
                assert bool(count) == any(w["begin"] <= index < w["end"] for w in windows), (clip, index)
                y0, end0 = -1, -1
                for _ in range(count):
                    y, start, end = struct.unpack("<3H", f.read(6))
                    assert 0 <= start < end <= width // 2 and 0 <= y < height // 2, (clip, index)
                    assert y > y0 or (y == y0 and start >= end0), (clip, index)
                    y0, end0 = y, end
            assert not f.read(1), clip
    tails, audio, checked = {}, {}, set()
    for e in level.get("market_entries", []):
        dest, name = e["dest"], e["take"]
        if name in checked:
            continue
        checked.add(name)
        base, path = assets / (dest + ".mp4"), assets / (name + ".mp4")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == e["sha256"], name
        if dest not in tails:
            tails[dest], audio[dest] = picture_hashes(base), audio_hash(base)
        frames, join = picture_hashes(path), e["join"]
        assert len(frames) == level["clips"][dest]["frames"] and frames[join:] == tails[dest][join:], name
        assert audio_hash(path) == audio[dest], name
    if checked:
        print(f"Verified {len(checked)} alternate entrances, identical decoded tails and AAC tracks")


def check_negative(level):
    cases = [("link", "Missing clip"), ("window", "Out of frame window")]
    if level.get("market_entries"):
        cases.append(("entrance", "Overlapping market entrances"))
    if "street" in level:
        cases.extend([("duration", "Invalid street duration"), ("hash", "Invalid street hash"),
                      ("timeline", "Conflicting street timelines")])
    for variant, expected in cases:
        bad = deepcopy(level)
        clip = next(c for c in bad["clips"].values() if c.get("windows"))
        if variant == "link":
            clip["next"] = "does_not_exist"
        elif variant == "window":
            clip["windows"][0]["end"] = clip["frames"] + 1
        elif variant == "entrance":
            bad["market_entries"].append(bad["market_entries"][0].copy())
        elif variant == "duration":
            bad["street"]["frames"] = 0
        elif variant == "hash":
            bad["street"]["sha256"] = "x" * 64
        else:
            bad["market_entries"] = [{}]
        try:
            validate_graph(bad)
        except AssertionError as e:
            assert expected in str(e), str(e)
            print(f"Negative case passed: {e}")
        else:
            raise AssertionError("Validator accepted the " + variant + " regression")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--level", default="m0")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_]+", args.level):
        parser.error("Invalid encounter name")
    world = args.root / "worlds/changan" / args.level
    assets = args.root / "assets/changan" / args.level
    level = json.loads((world / "level.json").read_text(encoding="utf-8"))
    validate_graph(level)
    verify_media(level, world, assets)
    if args.negative:
        check_negative(level)
    print(f"OK: {len(level['clips'])} reachable 720p H3 clips, frame windows, audio, hashes and mask spans")


if __name__ == "__main__":
    main()
