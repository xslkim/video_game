"""Validate Chapter 1 manifests, video streams, audio banks, masks, polygons, and pacing budgets."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import wave

from check_linyuan import validate as validate_mvp

ROOT = Path(__file__).resolve().parents[2]

CH1_VOICES = (
    "qingping/redeye", "qingping/first", "qingping/up", "qingping/canister",
    "qingping/shrine", "qingping/civilian", "qingping/bridge", "qingping/reload",
    "qingping/core", "qingping/canisters", "qingping/fireball", "qingping/mouth",
    "qingping/xuanwu", "qingping/hurt_1", "qingping/hurt_2", "qingping/hurt_3",
    "qingping/protect", "luchen/up", "laojiu/conch",
    # Plus all 8 MVP voices:
    "qingping/noodle", "luchen/noodle", "yunyi/talon", "qingping/talon",
    "yunyi/thanks", "yunyi/rebuke", "qingping/scan", "qingping/needles",
    "qingping/elite_core", "qingping/raft",
)

CH1_MUSIC = ("title", "jiuqu_story", "dukou_battle", "battle", "boss_taotie", "jiuqu_outro", "credits")
CH1_AMBIENCES = ("bamboo_stream", "dukou_air")


def check_stream(path):
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate,has_b_frames,sample_rate,channels",
            "-of", "json", str(path),
        ],
        text=True,
    )
    streams = json.loads(out).get("streams", [])
    vid = [s for s in streams if s["codec_type"] == "video"]
    aud = [s for s in streams if s["codec_type"] == "audio"]
    if len(vid) != 1 or len(aud) != 1:
        raise ValueError(f"Expected 1 video + 1 audio stream in {path}")
    v, a = vid[0], aud[0]
    if (v["codec_name"] != "h264" or v["pix_fmt"] != "yuv420p" or
            v["width"] != 1280 or v["height"] != 720 or v["r_frame_rate"] != "24/1" or
            int(v.get("has_b_frames", 0)) != 0):
        raise ValueError(f"Bad video stream format in {path}: {v}")
    if int(a["sample_rate"]) != 48000 or int(a["channels"]) != 2:
        raise ValueError(f"Bad audio stream format in {path}: {a}")


def check_wav(path, channels=(2,)):
    if not path.is_file():
        raise ValueError(f"Missing audio file: {path}")
    with wave.open(str(path)) as w:
        if w.getnframes() == 0 or w.getsampwidth() != 2 or w.getframerate() != 48000 or w.getnchannels() not in channels:
            raise ValueError(f"Invalid WAV format: {path}")


def check_mask(path, frames, sha256_hex, windows):
    data = path.read_bytes()
    if len(data) < 38 or data[:4] != b"DCM1":
        raise ValueError(f"Bad DCM1 mask header: {path}")
    if data[4:36].hex() != sha256_hex:
        raise ValueError(f"Mask hash mismatch: {path}")
    nf = struct.unpack_from("<H", data, 36)[0]
    if nf != frames:
        raise ValueError(f"Mask frame count {nf} != {frames} in {path}")
    pos = 38
    counts = []
    for _ in range(nf):
        cnt = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + cnt * 6
        counts.append(cnt)
    if pos != len(data):
        raise ValueError(f"Trailing bytes in mask {path}")
    for win in windows:
        if all(counts[f] == 0 for f in range(win["begin"], win["end"])):
            raise ValueError(f"Empty mask across window {win} in {path}")


def check_dukou(world, asset_dir):
    level = json.loads((world / "dukou/level.json").read_bytes())
    if level.get("ruleset") != "linyuan" or not level.get("allow_special"):
        raise ValueError("dukou level missing linyuan/allow_special")
    nodes = level["nodes"]
    if len(nodes) != 11:
        raise ValueError(f"Expected 11 dukou nodes, got {len(nodes)}")
    baseline_swords = sum(1 if n.get("weak_damage", 1) > 1 else n["hp"] for n in nodes)
    if baseline_swords != 11:
        raise ValueError(f"Expected 11 normal baseline swords in dukou, got {baseline_swords}")
    plate = level["plate"]
    plate_file = asset_dir / "dukou" / (plate["media"] + ".mp4")
    if hashlib.sha256(plate_file.read_bytes()).hexdigest() != plate["sha256"]:
        raise ValueError("dukou plate sha256 mismatch")
    check_stream(plate_file)

    clips = level["clips"]
    saw_forbearance = False
    saw_hold = False
    for cid, spec in clips.items():
        mp4 = asset_dir / "dukou" / (spec["media"] + ".mp4")
        if hashlib.sha256(mp4.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(f"dukou clip sha256 mismatch: {cid}")
        check_stream(mp4)
        if spec.get("hold_frame", -1) >= 0:
            saw_hold = True
        if spec.get("forbearance_bonus", 0) > 0:
            saw_hold = saw_hold
            saw_forbearance = True
        if spec.get("windows"):
            check_mask(world / "dukou" / (cid + ".mask"), spec["frames"], spec["sha256"], spec["windows"])
            if spec.get("weak_mask"):
                check_mask(world / "dukou" / (cid + ".weak.mask"), spec["frames"], spec["sha256"], spec["windows"])
        # Ordinary kill relay waits must stay <= 1.8s
        if "_hit" in cid:
            dur = (spec.get("end", spec["frames"]) - spec.get("start", 0)) / 24.0
            if dur > 1.8:
                raise ValueError(f"Relay clip too long ({dur:.2f}s > 1.8s): {cid}")
    if not saw_hold or not saw_forbearance:
        raise ValueError("dukou missing hold_frame or forbearance_bonus")
    glow_file = world / "dukou/threat_glows.json"
    if not glow_file.is_file():
        raise ValueError("Missing dukou threat_glows.json")
    if level.get("materials_sha256") != plate["sha256"]:
        raise ValueError("dukou materials_sha256 mismatch")


def check_regions_file(world, path_rel, take_sha, expected_zones):
    p = world / "regions" / path_rel
    data = json.loads(p.read_bytes())
    if data["sha256"] != take_sha:
        raise ValueError(f"Region SHA mismatch: {p}")
    for z in expected_zones:
        if z not in data["regions"]:
            raise ValueError(f"Missing zone {z} in {p}")


def validate_ch1(root):
    root = Path(root)
    world = root / "worlds/linyuan"
    asset_dir = root / "assets/linyuan"
    # Validate shared MVP/bamboo assets and campaign integrity first if mvp.json exists
    if (world / "mvp.json").is_file():
        validate_mvp(root)
    check_dukou(world, asset_dir)

    drama = json.loads((world / "drama.json").read_bytes())
    for tid, info in drama.items():
        mp4 = asset_dir / "drama" / (tid + ".mp4")
        if hashlib.sha256(mp4.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Drama take sha256 mismatch: {tid}")
        check_stream(mp4)

    for v in set(CH1_VOICES):
        check_wav(asset_dir / "audio/voice" / (v + ".wav"), channels=(1, 2))
    for m in CH1_MUSIC:
        check_wav(asset_dir / "audio/music" / (m + ".wav"))
    for a in CH1_AMBIENCES:
        check_wav(asset_dir / "audio/ambience" / (a + ".wav"))
    for sfx in ("special.wav", "special_2.wav", "special_3.wav"):
        check_wav(asset_dir / "audio/foley" / sfx)

    if not (asset_dir / "title.bmp").is_file():
        raise ValueError("Missing title.bmp")

    campaign = json.loads((world / "chapter_one.json").read_bytes())
    stages = campaign["chapters"][0]["stages"]
    stage_ids = [s["id"] for s in stages]
    for req in ("opening", "dukou", "save_yunyi", "yunyi_reply", "conch", "bamboo", "taotie", "xuanwu_outro"):
        if req not in stage_ids:
            raise ValueError(f"Missing Chapter 1 stage: {req}")

    # Verify non-interactive story duration <= 75s
    story_sec = 0.0
    for s in stages:
        if s["type"] == "film":
            if s["id"] == "yunyi_reply":
                t = s["takes"][0]
                d = drama[t["id"]]
                sf = t.get("start_frame", 0)
                ef = t.get("end_frame", d["frames"])
                story_sec += (ef - sf) / (24.0 * d.get("speed", 1.0))
            else:
                for t in s["takes"]:
                    d = drama[t["id"]]
                    sf = t.get("start_frame", 0)
                    ef = t.get("end_frame", d["frames"])
                    story_sec += (ef - sf) / (24.0 * d.get("speed", 1.0))
        elif s["type"] == "card":
            story_sec += s["milliseconds"] / 1000.0
    if story_sec > 75.0:
        raise ValueError(f"Pure story duration {story_sec:.2f}s exceeds 75s limit")

    # Verify boss trial polygon integrity and normal sword count (6 + 3 + 3 = 12)
    boss = next(s["trial"] for s in stages if s["id"] == "taotie")
    boss_swords = 0
    for sid, step in boss["steps"].items():
        take = step["take"]
        if sid.startswith("p1_") or sid.startswith("p2_"):
            boss_swords += 1
        elif sid == "p3":
            boss_swords += step.get("boss_hp", 1)
        check_regions_file(world, f"{take}.json", drama[take]["sha256"], step["zones"])
    if boss_swords != 12:
        raise ValueError(f"Expected 12 normal baseline swords in taotie boss, got {boss_swords}")

    return {"story_seconds": round(story_sec, 2), "dukou_swords": 11, "bamboo_swords": 13, "boss_swords": boss_swords}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(validate_ch1(args.root), indent=2))
