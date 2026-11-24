"""Bake H3 street performances and the approved action into ordinary 720p branch clips.

The base is the original M0 export. All visual blending is offline. The game still
decodes one complete picture per frame and uses its original interaction timeline.
"""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from changan_assets import LANTERN, draw_mask, lerp, spans

WORLD = Path("worlds/changan/m0")
MEDIA = Path("assets/changan/m0")
SIZE = (1280, 720)
SHOTS = {
    "lantern": ["market_anchored", "market_lantern_return"],
    "lantern_to_wisp_early": ["market_relay_2"],
    "lantern_to_wisp_mid": ["market_relay_21"],
    "lantern_to_wisp_late": ["market_relay_40"],
    "wisp": ["market_wisp"],
    "interrupt_early": ["market_intercept_early"],
    "interrupt_middle": ["market_intercept_middle"],
    "interrupt_late": ["market_intercept_late"],
    "wisp_to_fox": ["market_relay_fox"],
    "fox": ["market_fox"],
    "fox_flinch": ["market_flinch"],
    "purify_end": ["market_celebration"],
}
# Author in the same 1024x576 coordinates as the original H3 action.
Y, X = np.ogrid[:720, :1280]
X, Y = X.astype("float32") / 1.25, Y.astype("float32") / 1.25


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path):
    cap = cv2.VideoCapture(str(path))
    out = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        out.append(frame)
    cap.release()
    if not out:
        raise ValueError(f"Cannot decode {path}")
    return out


def sample(frames, count):
    return [frames[i] for i in np.rint(np.linspace(0, len(frames) - 1, count)).astype(int)]


def street_frames(clip, work, count):
    shots = [decode(work / "takes" / name / "source.mp4") for name in SHOTS[clip]]
    if clip == "lantern":
        return shots[0][:44] + sample(shots[1], count - 44 + 1)[1:]
    return sample(shots[0], count)


def soft_box(x0, y0, x1, y1, feather):
    return np.minimum(
        np.clip(np.minimum(X - x0, x1 - X) / feather, 0, 1),
        np.clip(np.minimum(Y - y0, y1 - Y) / feather, 0, 1),
    )


def smooth(value, low, high):
    x = np.clip((value - low) / (high - low), 0, 1)
    return x * x * (3 - 2 * x)


# Source-bound effects and reflected light can extend beyond an interactive mask.
AMBER = soft_box(125, 165, 520, 491, 30)
TEAL = soft_box(464, 179, 871, 512, 28)
FOX = soft_box(418, 159, 653, 511, 36)
FOX_END = soft_box(348, 130, 773, 549, 45)


def compose(clip, index, action, market, reference):
    bg = cv2.resize(market, SIZE, interpolation=cv2.INTER_CUBIC).astype("float32")
    a = action.astype("float32")
    delta = a - reference
    color_b, color_g, color_r = cv2.split(a)
    alpha = np.zeros(a.shape[:2], "float32")
    light = np.zeros_like(alpha)
    if clip.startswith("lantern"):
        # Warm spill is additive, the lantern body and its paper tail are opaque.
        warm_delta = delta[:, :, 2] - 0.44 * delta[:, :, 0]
        alpha = AMBER * smooth(warm_delta, 24, 91) * smooth(color_r - color_b, 20, 65)
        # A lamp in the clean reference can be brighter than the same pixel in the
        # flare. Close small holes so the old street cannot show through a white core.
        core = cv2.morphologyEx(
            alpha, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
        )
        alpha = np.maximum(alpha, cv2.GaussianBlur(core, (5, 5), 0) * smooth(color_r, 126, 214))
        light = AMBER * smooth(warm_delta, 8, 45)
        if clip == "lantern":
            track = LANTERN + [(50, 269, 300, 24, 26), (57, 265, 298, 24, 26), (72, 265, 298, 24, 25)]
            x, y, rx, ry = lerp(track, index)
            radius = ((X - x) / (rx + 1)) ** 2 + ((Y - y) / ry) ** 2
            alpha = np.maximum(alpha, 1 - smooth(radius, 0.90, 1.13))
    if clip.startswith(("wisp", "interrupt", "lantern_to")):
        cyan = np.minimum(color_b - color_r, color_g - color_r)
        key = TEAL * smooth(cyan, 3, 48)
        alpha = np.maximum(alpha, key)
        light = np.maximum(light, TEAL * smooth(delta[:, :, 1] - 0.65 * delta[:, :, 2], 10, 55))
    if clip in ("fox", "fox_flinch", "purify_end") or clip == "wisp_to_fox" and index >= 15:
        zone = FOX_END if clip == "purify_end" else FOX
        if clip == "wisp_to_fox":
            zone = zone * smooth(float(index), 15, 28)
        alpha = np.maximum(alpha, zone)
        # Carry the original pink light across the road and shop fronts.
        spill = np.minimum(delta[:, :, 2], delta[:, :, 0])
        light = np.maximum(light, smooth(spill, 18, 75))
    positive = np.maximum(delta - 6, 0)
    bg = np.minimum(255, bg + positive * light[:, :, None])
    return np.clip(bg + (a - bg) * alpha[:, :, None], 0, 255).astype("uint8")


def encode(path, action_file, frames, join=None):
    command = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        "1280x720",
        "-r",
        "24",
        "-i",
        "pipe:0",
    ]
    if action_file:
        command += [
            "-i",
            str(action_file),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
        ]
    command += [
        "-c:v",
        "libx264",
        "-crf",
        "17",
        "-preset",
        "fast",
        "-bf",
        "0",
        "-g",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-x264-params",
        "open-gop=0",
    ]
    if join is not None:
        command += ["-force_key_frames", f"expr:eq(n,{join})"]
    command.append(str(path))
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        try:
            for frame in frames:
                proc.stdin.write(memoryview(frame))
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError("Encoding failed: " + path.name)


def splice_entry(output, base, action_file, join, prefix):
    # Both elementary streams start on an IDR. Copying the original coded tail
    # makes every later interactive picture byte-identical after decoding.
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        folder = Path(tmp)
        head, tail = folder / "head.h264", folder / "tail.h264"
        encode(head, None, prefix)
        ff = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y"]
        subprocess.run(
            ff
            + [
                "-ss",
                f"{join / 24:.9f}",
                "-i",
                str(base),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-bsf:v",
                "h264_mp4toannexb",
                str(tail),
            ],
            check=True,
        )
        with head.open("ab") as dst, tail.open("rb") as src:
            shutil.copyfileobj(src, dst)
        staged = folder / output.name
        subprocess.run(
            ff
            + [
                "-r",
                "24",
                "-f",
                "h264",
                "-i",
                str(head),
                "-i",
                str(action_file),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(staged),
            ],
            check=True,
        )
        staged.replace(output)


def info(work, name):
    take = work / "takes" / name
    job = json.loads((take / "job.json").read_text())
    return {
        "candidate": name,
        "h3_prompt_id": job["prompt"],
        "source_sha256": digest(take / "source.mp4"),
    }


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def charge_mask(mask, path, cue):
    # Only the replacement charge changes the original action pose.
    header = mask[:38]
    offset = len(header)
    capture = cv2.VideoCapture(str(path))
    prefix = bytearray()
    for i in range(14):
        (count,) = struct.unpack_from("<H", mask, offset)
        offset += 2 + 6 * count
        ok, frame = capture.read()
        if not ok:
            raise ValueError("Missing charge frame")
        rows = spans(draw_mask("wisp", i, frame, cue))
        prefix.extend(struct.pack("<H", len(rows)))
        for row in rows:
            prefix.extend(struct.pack("<3H", *row))
    capture.release()
    return header + prefix + mask[offset:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="Original playable release or base asset export")
    parser.add_argument("work", type=Path, help="H3 work directory with takes and anchors")
    parser.add_argument("output", type=Path, help="Separate staging directory")
    parser.add_argument("ledger", type=Path, help="Original action production/media.json")
    parser.add_argument("--entries", type=Path, help="Background entrance plan")
    args = parser.parse_args()
    if args.base.resolve() == args.output.resolve():
        parser.error("Use a separate staging directory")
    cv2.setNumThreads(2)
    world = args.output / WORLD
    (world / "production").mkdir(parents=True, exist_ok=True)
    (args.output / MEDIA).mkdir(parents=True, exist_ok=True)
    level = json.loads((args.base / WORLD / "level.json").read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    cap = cv2.VideoCapture(str(args.work / "takes/market_free/source.mp4"))
    ok, reference = cap.read()
    cap.release()
    if not ok:
        raise ValueError("Missing clean reference")
    reference = cv2.resize(reference, SIZE, interpolation=cv2.INTER_CUBIC).astype("float32")
    entries = json.loads(args.entries.read_text(encoding="utf-8")) if args.entries else []
    for clip, meta in level["clips"].items():
        action_file = args.base / MEDIA / (clip + ".mp4")
        if digest(action_file) != meta["sha256"]:
            raise ValueError("Base video changed: " + clip)
        action = decode(action_file)
        if clip == "wisp":
            awake = decode(args.work / "takes/wisp_live_charge/source.mp4")
            action[:14] = [
                cv2.resize(f, SIZE, interpolation=cv2.INTER_CUBIC) for f in sample(awake, 15)[:-1]
            ]
        market = street_frames(clip, args.work, len(action))
        path = args.output / MEDIA / (clip + ".mp4")
        with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
            staged = Path(tmp) / path.name
            joins = {e["join"] for e in entries if e["dest"] == clip}
            if len(joins) > 1:
                raise ValueError("Alternate entrances must share their return frame")
            encode(
                staged,
                action_file,
                (
                    compose(clip, i, a, b, reference)
                    for i, (a, b) in enumerate(zip(action, market, strict=True))
                ),
                next(iter(joins), None),
            )
            staged.replace(path)
        old_sha, sha = meta["sha256"], digest(path)
        meta["sha256"] = sha
        if meta.get("windows"):
            mask = (args.base / WORLD / (clip + ".mask")).read_bytes()
            if mask[:36] != b"DCM1" + bytes.fromhex(old_sha):
                raise ValueError("Stale action mask: " + clip)
            if clip == "wisp":
                mask = charge_mask(mask, path, meta["windows"][0])
            (world / (clip + ".mask")).write_bytes(b"DCM1" + bytes.fromhex(sha) + mask[36:])
        provenance = ledger[clip]
        provenance["action_export_sha256"] = old_sha
        provenance["final_sha256"] = sha
        provenance["market_takes"] = [info(args.work, key) for key in SHOTS[clip]]
        if clip == "wisp":
            provenance["charge_take"] = info(args.work, "wisp_live_charge")
            provenance["padding_frames"] = 0
        print(clip, len(action), sha[:12], flush=True)
        for key in dict.fromkeys(e["take"] for e in entries if e["dest"] == clip):
            match = next(e for e in entries if e["take"] == key)
            join = match["join"]
            if any(w["begin"] <= join for w in meta.get("windows", [])):
                raise ValueError("Market entrance overlaps active mask: " + key)
            intro = sample(decode(args.work / "takes" / key / "source.mp4"), join + 1)
            variant = args.output / MEDIA / (key + ".mp4")
            splice_entry(
                variant,
                path,
                action_file,
                join,
                (compose(clip, i, action[i], intro[i], reference) for i in range(join)),
            )
            source = info(args.work, key)
            for e in entries:
                if e["take"] == key:
                    e.update(
                        sha256=digest(variant),
                        h3_prompt_id=source["h3_prompt_id"],
                        source_sha256=source["source_sha256"],
                    )
            print(" ", key, flush=True)
    if entries:
        level["market_entries"] = entries
    write_json(world / "level.json", level)
    write_json(world / "production/media.json", ledger)


if __name__ == "__main__":
    main()
