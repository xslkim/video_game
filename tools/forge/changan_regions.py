"""Track hand-marked surface polygons against the final delivered film frames."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from changan_surface_tracks import refined


def follow(frames, marks):
    # Manual anchors bound drift; track local translation from textured features.
    poses = {}
    anchors = sorted(int(k) for k in marks)
    for f in range(len(frames)):
        anchor = min(anchors, key=lambda k: abs(k - f))
        if f == anchor:
            poses[f] = np.asarray(marks[str(anchor)], dtype=np.float32)
    for direction in (1, -1):
        for anchor in anchors:
            poly = poses[anchor].copy()
            index = anchor
            while 0 <= index + direction < len(frames):
                nxt = index + direction
                if min(anchors, key=lambda k: abs(k - nxt)) != anchor:
                    break
                mask = np.zeros(frames[index].shape, np.uint8)
                cv2.fillPoly(mask, [np.int32(np.round(poly))], 255)
                mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
                features = cv2.goodFeaturesToTrack(
                    frames[index], maxCorners=40, qualityLevel=0.015, minDistance=3, mask=mask
                )
                if features is not None and len(features) >= 3:
                    moved, ok, _ = cv2.calcOpticalFlowPyrLK(frames[index], frames[nxt], features, None)
                    valid = ok[:, 0].astype(bool)
                    if valid.sum() >= 3:
                        delta = np.median((moved - features)[valid, 0, :], axis=0)
                        if np.linalg.norm(delta) <= 26:
                            poly += delta
                poses[nxt] = poly.copy()
                index = nxt
    return [{"frame": i, "polygon": np.int32(np.round(poses[i])).tolist()} for i in range(len(frames))]


def recipes(world, output):
    base = json.loads((world / "production/regions.json").read_bytes())
    yield from base.items()
    wave_file = world / "production/drama_wave_jobs.json"
    if not wave_file.exists():
        return
    index = json.loads((world / "drama.json").read_bytes())
    sources = {}
    for file in sorted((world / "production").glob("drama*jobs.json")):
        sources.update(json.loads(file.read_bytes()))
    for take, spec in json.loads(wave_file.read_bytes()).items():
        video_path = world.parents[1] / "assets/changan/drama" / (take + ".mp4")
        if not video_path.is_file():
            continue
        if take in index:
            frames = index[take]["frames"]
        else:
            video = cv2.VideoCapture(str(video_path))
            frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            video.release()
            if frames <= 1:
                raise ValueError(f"Invalid new performance: {take}")
        parent, frame = spec["from_take"]
        marks = json.loads((output / (parent + ".json")).read_bytes())["regions"]
        aperture = sources[parent].get("aperture", [1024, 576, 0, 0])
        w, h, x, y = aperture
        frame = round(frame / sources[parent].get("speed", 1))
        result = {}
        for key, poses in marks.items():
            poly = poses[min(frame, len(poses) - 1)]["polygon"]
            mapped = [
                [round((px * w / 1280 + x) * 1280 / 1024), round((py * h / 720 + y) * 720 / 576)]
                for px, py in poly
            ]
            result[key] = {"0": mapped}
            if spec.get("last") == spec["first"]:
                result[key][str(frames - 1)] = mapped
        yield take, result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[2])
    args = ap.parse_args()
    world = args.root / "worlds/changan"
    out = world / "regions"
    out.mkdir(exist_ok=True)
    rules = json.loads((world / "production/surface_tracks.json").read_bytes())
    for take, spec in recipes(world, out):
        file = args.root / "assets/changan/drama" / (take + ".mp4")
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        correction = rules.get(take, {})
        contract = [spec, correction, 1] if correction else spec
        recipe = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        dest = out / (take + ".json")
        if dest.is_file():
            prior = json.loads(dest.read_bytes())
            if prior.get("sha256") == sha and prior.get("recipe") == recipe:
                continue
        video = cv2.VideoCapture(str(file))
        frames = []
        corrected = {role: [] for role in correction}
        while True:
            ok, frame = video.read()
            if not ok:
                break
            number = len(frames)
            for role, rule in correction.items():
                corrected[role].append({"frame": number, "polygon": refined(frame, number, rule)})
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        video.release()
        if not frames:
            raise ValueError(f"Cannot decode {file}")
        regions = {
            name: corrected[name] if name in corrected else follow(frames, marks)
            for name, marks in spec.items()
        }
        output = {"sha256": sha, "recipe": recipe, "regions": regions}
        import os

        temporary = dest.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(output, separators=(",", ":")) + "\n")
        temporary.replace(dest)


if __name__ == "__main__":
    main()
