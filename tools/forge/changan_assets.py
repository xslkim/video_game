"""Conform local H3 candidate videos and author frame-bound Changan masks."""

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
LEVEL = ROOT / "worlds/changan/m0"
ASSETS = ROOT / "assets/changan/m0"
FINAL_SIZE = (1280, 720)
SOURCE_SIZE = (1024, 576)
WISP_PAD = 14


def target(begin, end, node, clip, kind="target"):
    return {"begin": begin, "end": end, "node": node, "kind": kind, "hit": clip}


def cues(clip_id, count):
    if clip_id == "lantern":
        return [target(0, 13, 0, "lantern_to_wisp_early"),
                target(13, 29, 0, "lantern_to_wisp_mid"),
                target(29, 43, 0, "lantern_to_wisp_late")]
    if clip_id.startswith("lantern_to_wisp"):
        return [target({"early": 34, "mid": 39, "late": 29}[clip_id.split("_")[-1]],
                       count, 1, "wisp_to_fox")]
    if clip_id == "wisp":
        return [target(0, WISP_PAD + 23, 1, "wisp_to_fox"),
                target(WISP_PAD + 24, WISP_PAD + 32, 1, "interrupt_early", "projectile"),
                target(WISP_PAD + 32, WISP_PAD + 47, 1, "interrupt_middle", "projectile"),
                target(WISP_PAD + 47, WISP_PAD + 54, 1, "interrupt_late", "projectile")]
    if clip_id == "wisp_to_fox":
        return [target(34, count, 2, "purify_end")]
    if clip_id == "fox":
        return [target(0, 39, 2, "purify_end")]
    return []


# clip, candidate, natural successor, duration multiplier, first/last reference
EDGES = [
    ("lantern", "lantern_take01", "lantern", 1., "lantern", "lantern"),
    ("lantern_to_wisp_early", "relay_lantern_early", "wisp", .84, "lantern", "wisp"),
    ("lantern_to_wisp_mid", "relay_lantern_mid", "wisp", .84, "lantern_mid_hit", "wisp"),
    ("lantern_to_wisp_late", "relay_lantern_late", "wisp", .84, "lantern_late_hit", "wisp"),
    ("wisp", "wisp_take01", "wisp", 1., "wisp", "wisp"),
    ("interrupt_early", "wisp_interrupt_early", "wisp", 1., "fireball_early_hit", "wisp"),
    ("interrupt_middle", "wisp_interrupt_take01", "wisp", .60, "wisp_flight", "wisp"),
    ("interrupt_late", "wisp_interrupt_late", "wisp", 1., "fireball_late_hit", "wisp"),
    ("wisp_to_fox", "relay_wisp_fox", "fox", .84, "wisp", "fox"),
    ("fox", "fox_take01", "fox", 1., "fox", "fox"),
    ("fox_flinch", "fox_flinch_take01", "fox", .49, "fox", "fox"),
    ("purify_end", "fox_end_take01", "@complete", .82, "fox", "street"),
]

LANTERN = [(0, 265, 298, 24, 25), (8, 270, 302, 24, 25), (13, 278, 309, 25, 27),
           (20, 290, 309, 26, 26), (26, 298, 309, 26, 27), (30, 305, 308, 25, 27),
           (35, 302, 303, 24, 25), (40, 294, 301, 24, 24), (43, 289, 300, 24, 24)]
ORB = [(24, 738, 315, 20, 16), (29, 701, 341, 17, 15), (34, 671, 368, 16, 15),
       (40, 628, 402, 17, 15), (44, 606, 412, 19, 16), (48, 587, 409, 23, 21),
       (52, 563, 395, 32, 29), (54, 547, 385, 42, 36)]
FOX_POSE = np.array([(529, 258), (532, 246), (545, 246), (555, 258), (557, 284),
                     (573, 281), (588, 278), (593, 295), (578, 318), (574, 356),
                     (580, 420), (575, 475), (545, 481), (494, 475),
                     (485, 463), (499, 423), (490, 389), (498, 355),
                     (513, 337), (521, 307), (532, 281)], dtype=np.float64)


def lerp(table, frame):
    columns = zip(*table)
    xs = tuple(next(columns))
    return tuple(round(float(np.interp(frame, xs, ys))) for ys in columns)


def ellipse(mask, spec):
    x, y, rx, ry = spec
    cv2.ellipse(mask, (x, y), (rx, ry), 0, 0, 360, 1, -1)


def cyan(frame, mask, area, reference):
    x0, y0, x1, y1 = area
    b, g, r = frame[y0:y1, x0:x1].astype(np.int16).transpose(2, 0, 1)
    binary = ((g - r >= 32) & (b - r >= 20) & (g > 112)).astype(np.uint8)
    n, labels, stats, centers = cv2.connectedComponentsWithStats(binary)
    if n > 1:
        indices = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 10]
        if indices:
            index = min(indices, key=lambda i: (centers[i][0] + x0 - reference[0]) ** 2 +
                        (centers[i][1] + y0 - reference[1]) ** 2)
            mask[y0:y1, x0:x1] = np.uint8(labels == index)
            return cv2.dilate(mask, np.ones((7, 7), dtype=np.uint8))
    ellipse(mask, (*reference, 13, 16))
    return mask


def draw_mask(clip_id, frame_index, frame, cue):
    frame = cv2.resize(frame, SOURCE_SIZE, interpolation=cv2.INTER_AREA)
    out = np.zeros((SOURCE_SIZE[1], SOURCE_SIZE[0]), dtype=np.uint8)
    if clip_id == "lantern":
        ellipse(out, lerp(LANTERN, frame_index))
    elif cue["kind"] == "projectile":
        xy = lerp(ORB, frame_index - WISP_PAD)
        # Let the hand-marked track bound the cyan segmentation so that the source and tail
        # cannot become an alternate projectile target.
        x, y, rx, ry = xy
        limit = np.zeros_like(out)
        ellipse(limit, (x, y, rx + 3, ry + 3))
        core = cyan(frame, out, (x - rx, y - ry, x + rx, y + ry), (x, y))
        out = core & limit
    elif cue["node"] == 1:
        guide = {
            "early": [(34, 778, 329), (41, 764, 312), (46, 759, 302)],
            "mid": [(39, 779, 309), (44, 766, 305), (46, 759, 303)],
            "late": [(29, 763, 333), (40, 759, 313), (46, 759, 302)],
        }
        ref = (759, 301)
        if clip_id.startswith("lantern_to_wisp"):
            ref = lerp(guide[clip_id.split("_")[-1]], frame_index)
        x, y = ref
        out = cyan(frame, out, (x - 19, y - 33, x + 21, y + 26), ref)
    else:
        pose = FOX_POSE.copy()
        if clip_id == "fox":
            spread = float(np.interp(frame_index, [0, 10, 22, 38], [0, .15, 1., .60]))
            pose[[13, 14, 15, 16, 17], 0] -= 12 * spread
            pose[[5, 6, 7, 8, 9], 0] += 9 * spread
            pose[[0, 1, 2, 3, 4], 0] -= 4 * spread
        cv2.fillPoly(out, [np.round(pose).astype(np.int32)], 1)
    return cv2.resize(out, (FINAL_SIZE[0] // 2, FINAL_SIZE[1] // 2), interpolation=cv2.INTER_NEAREST)


def spans(mask):
    rows = []
    for y, line in enumerate(mask):
        if not line.any():
            continue
        edges = np.flatnonzero(np.diff(np.pad(line, (1, 1))))
        rows.extend((y, x0, x1) for x0, x1 in zip(edges[0::2], edges[1::2]))
    return rows


def export(src, dest, duration, padding):
    rate = 1 / duration
    vf = f"scale={FINAL_SIZE[0]}:{FINAL_SIZE[1]}:flags=lanczos,setpts={duration}*PTS,fps=24"
    af = f"atempo={rate:.7f},highpass=f=55,volume=0.55"
    if padding:
        vf += f",tpad=start={padding}:start_mode=clone"
        af += f",adelay={round(padding*1000/24)}:all=1"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src),
                    "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-bf", "0", "-g", "24", "-c:a", "aac", "-b:a", "160k",
                    "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(dest)], check=True)


def author(clip_id, source, duration, review):
    dest = ASSETS / (clip_id + ".mp4")
    export(source, dest, duration, WISP_PAD if clip_id == "wisp" else 0)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    frames = []
    capture = cv2.VideoCapture(str(dest))
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise ValueError(f"No frames: {dest}")
    windows = cues(clip_id, len(frames))
    if windows:
        boundaries = {i for w in windows for i in (w["begin"], (w["begin"] + w["end"]) // 2, w["end"] - 1)}
        tiles = []
        with (LEVEL / (clip_id + ".mask")).open("wb") as file:
            file.write(b"DCM1" + bytes.fromhex(digest) + struct.pack("<H", len(frames)))
            for i, frame in enumerate(frames):
                cue = next((w for w in windows if w["begin"] <= i < w["end"]), None)
                rows = []
                if cue:
                    mask = draw_mask(clip_id, i, frame, cue)
                    rows = spans(mask)
                    if not rows:
                        raise ValueError(f"Empty mask in {clip_id} frame {i}")
                    if i in boundaries:
                        tint = cv2.resize(mask, FINAL_SIZE, interpolation=cv2.INTER_NEAREST) > 0
                        frame[tint] = (frame[tint] * .45 + np.asarray((170, 255, 30)) * .55).astype("uint8")
                        rgb = cv2.cvtColor(cv2.resize(frame, (384, 216)), cv2.COLOR_BGR2RGB)
                        tiles.append((i, Image.fromarray(rgb)))
                file.write(struct.pack("<H", len(rows)))
                file.write(b"".join(struct.pack("<3H", *row) for row in rows))
        cols, h = 3, 236
        sheet = Image.new("RGB", (384 * cols, h * ((len(tiles) + cols - 1) // cols)), (10, 18, 25))
        text = ImageDraw.Draw(sheet)
        for k, (i, im) in enumerate(tiles):
            x, y = (k % cols) * 384, (k // cols) * h
            sheet.paste(im, (x, y))
            text.text((x + 8, y + 217), f"{clip_id} | {i}")
        sheet.save(review / (clip_id + ".jpg"), quality=91)
    clip = {"frames": len(frames), "sha256": digest}
    if windows:
        clip["windows"] = windows
    if clip_id in ("lantern", "wisp", "fox"):
        clip["impact_frame"] = {"lantern": 43, "wisp": WISP_PAD + 54, "fox": 39}[clip_id]
    if clip_id == "wisp":
        clip["launch_frame"] = WISP_PAD + 23
    return clip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Existing H3 working folder with takes/ and anchors/")
    parser.add_argument("review", type=Path, help="Output folder for frame and mask contact sheets")
    args = parser.parse_args()
    for folder in (ASSETS, LEVEL, args.review):
        folder.mkdir(parents=True, exist_ok=True)
    clips = {}
    sources = {}
    for clip_id, job, successor, duration, first, last in EDGES:
        take = args.work / "takes" / job
        clip = author(clip_id, take / "source.mp4", duration, args.review)
        clip.update(next=successor, in_anchor=first, out_anchor=last)
        clips[clip_id] = clip
        record = json.loads((take / "job.json").read_text(encoding="utf-8"))
        history = json.loads((take / "history.json").read_text(encoding="utf-8"))
        stamps = {name: data["timestamp"] for name, data in history["status"]["messages"]
                  if name in ("execution_start", "execution_success")}
        sources[clip_id] = {
            "candidate": job,
            "h3_prompt_id": record["prompt"],
            "comfy_revision": record["comfy_revision"],
            "gpu_wall_seconds": (stamps["execution_success"] - stamps["execution_start"]) / 1000.,
            "source_sha256": hashlib.sha256((take / "source.mp4").read_bytes()).hexdigest(),
            "duration_multiplier": duration,
            "padding_frames": WISP_PAD if clip_id == "wisp" else 0,
            "in_anchor": first,
            "out_anchor": last,
            "final_sha256": clip["sha256"],
        }
        print(f"{clip_id}: {clip['frames']} frames from {job}")
    level = {
        "version": 1, "title": "长安灯妖录", "fps": 24, "size": FINAL_SIZE, "first": "lantern",
        "nodes": [{"id": "lantern", "label": "净化灯笼妖", "hp": 1, "score": 100},
                  {"id": "wisp", "label": "净化青火", "hp": 1, "score": 100},
                  {"id": "fox", "label": "净化狐火", "hp": 3, "score": 500, "flinch": "fox_flinch"}],
        "clips": clips,
    }
    (LEVEL / "level.json").write_text(json.dumps(level, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (LEVEL / "production/media.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
