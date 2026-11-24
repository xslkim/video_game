"""Export a one-shot street plate and premultiplied, full-canvas H3 performances."""

import argparse
import json
import struct
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from changan_assets import LANTERN, FOX_POSE, draw_mask, lerp, spans
from changan_market import MEDIA, SIZE, WORLD, decode, digest, info, sample, write_json

# These silhouettes provide opacity for solid objects. Light and reflections are
# recovered over the whole canvas, independently of the silhouettes or hit masks.
LAMP_TRACK = LANTERN + [
    (50, 269, 300, 24, 26),
    (57, 265, 298, 24, 26),
    (72, 265, 298, 24, 25),
]


def ramp(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


# The pedestrians beside the left stall also moved in the original fox take.
# Estimate their incident light from the surrounding stall and keep new sparks.
PEOPLE_ROI = np.s_[324:526, 291:485]
yy, xx = np.mgrid[324:526, 291:485]
people_distance = ((xx - 388) / 91) ** 2 + ((yy - 424) / 95) ** 2
PEOPLE_WEIGHT = (1 - ramp(people_distance, 0.62, 1.0)).astype("float32")
PEOPLE_MASK = cv2.resize(
    np.uint8(255 * (people_distance < 0.90)), (32, 34), interpolation=cv2.INTER_NEAREST
)


def remove_old_pedestrians(signal, bright):
    patch = signal[PEOPLE_ROI]
    reduced = cv2.resize(patch, (32, 34), interpolation=cv2.INTER_AREA)
    field = cv2.merge(
        [cv2.inpaint(c, PEOPLE_MASK, 4, cv2.INPAINT_NS) for c in cv2.split(reduced)]
    )
    field = cv2.resize(
        field, (patch.shape[1], patch.shape[0]), interpolation=cv2.INTER_CUBIC
    )
    weight = (PEOPLE_WEIGHT * (1 - ramp(bright[PEOPLE_ROI], 50, 100)))[:, :, None]
    patch += (field - patch) * weight


def plate_reference(clip, frames, empty):
    # Use the same take where possible. Each source includes an unobstructed
    # view of most of the set at its start or end, under the same exposure.
    r = frames[0].copy()
    if clip.startswith("lantern_to_wisp") or clip == "wisp_to_fox":
        # The incoming actor is absent at the end and the outgoing one at the start.
        x = np.arange(SIZE[0], dtype=np.float32)
        if clip == "wisp_to_fox":
            mix = ramp(x, 820, 890)
        else:
            mix = 1 - ramp(x, 665, 790)
        r = np.uint8(r + (frames[-1].astype("float32") - r) * mix[None, :, None])
    elif clip.startswith("interrupt") or clip == "purify_end":
        r = frames[-1].copy()
    # Fill persistent characters from the empty H3 frame. These windows affect
    # only the estimate of the clean plate, never the extent of the output.
    patches = {
        "lantern": (212, 305, 425, 484),
        "wisp": (891, 305, 1006, 465),
        "fox": (548, 273, 793, 635),
        "fox_flinch": (548, 273, 793, 635),
    }
    if clip.startswith("interrupt"):
        patch = patches["wisp"]
    else:
        patch = patches.get(clip)
    if patch:
        x, y, xx, yy = patch
        mask = np.zeros(r.shape[:2], np.float32)
        mask[y:yy, x:xx] = 1
        mask = cv2.GaussianBlur(mask, (0, 0), 8)[:, :, None]
        r = np.uint8(r + (empty.astype("float32") - r) * mask)
    return r


def solid_body(clip, i, a, delta):
    body = np.zeros(a.shape[:2], np.uint8)
    if clip == "lantern":
        x, y, rx, ry = lerp(LAMP_TRACK, i)
        cv2.ellipse(
            body,
            (round(x * 1.25), round(y * 1.25)),
            (round(rx * 1.20), round(ry * 1.25)),
            0,
            0,
            360,
            255,
            -1,
        )
    elif clip.startswith("lantern_to_wisp") and i < 8:
        x = {"early": 265, "mid": 291, "late": 300}[clip.rsplit("_", 1)[1]]
        cv2.ellipse(
            body,
            (round(x * 1.25), 380),
            (29, 30),
            0,
            0,
            360,
            round(255 * (1 - i / 8)),
            -1,
        )
    if clip in ("fox", "fox_flinch", "purify_end", "wisp_to_fox"):
        # Changes adjoining the torso include sleeves and hem outside the playable contour.
        if clip == "wisp_to_fox":
            strength = ramp(float(i), 23, 37)
        elif clip == "purify_end":
            strength = 1 - ramp(float(i), 15, 23)
        else:
            strength = 1.0
        if strength:
            cv2.fillPoly(
                body, [np.rint(1.25 * FOX_POSE).astype(np.int32)], round(255 * strength)
            )
    if body.any():
        # Keep static gaps in the silhouette open, even near a complex sleeve.
        difference = cv2.GaussianBlur(np.max(np.abs(delta), axis=2), (7, 7), 0)
        shape = cv2.GaussianBlur(body, (0, 0), 2.0).astype("float32") / 255.0
        fringe = (
            cv2.GaussianBlur(
                cv2.dilate(body, np.ones((23, 23), np.uint8)), (0, 0), 4
            ).astype("float32")
            / 255.0
        )
        return np.maximum(
            shape * ramp(difference, 3, 12), fringe * ramp(difference, 12, 43)
        )
    return body.astype("float32")


def foreground(clip, i, frame, clean, expanded_clean):
    # The opacity bounds let each RGB channel reproduce the original signed
    # lighting change, including diffuse reflections and white-hot sparks.
    a = frame.astype("float32")
    delta = a - clean
    small = cv2.GaussianBlur(delta, (0, 0), 3).max(axis=2)
    # Downsample only the estimator for diffuse light; extract colour at native resolution.
    coarse = cv2.resize(delta, (320, 180), interpolation=cv2.INTER_AREA)
    broad = cv2.resize(cv2.GaussianBlur(coarse, (0, 0), 3.5).max(axis=2), SIZE)
    bright = (a - expanded_clean).max(axis=2)
    luminous = np.maximum(ramp(np.maximum(small, broad), 4, 15), ramp(bright, 10, 42))
    body = solid_body(clip, i, a, delta)
    confidence = np.maximum(luminous, body)
    signal = confidence[:, :, None] * delta
    if clip in ("fox", "fox_flinch", "wisp_to_fox", "purify_end"):
        remove_old_pedestrians(signal, bright)
    quiet = (np.max(np.abs(signal), axis=2) < 1.3) & (body < 0.03)
    signal[quiet] = 0
    body[quiet] = 0
    needed = np.maximum(
        signal / np.maximum(255 - clean, 1), -signal / np.maximum(clean, 1)
    ).max(axis=2)
    alpha = np.uint8(np.ceil(255 * np.clip(np.maximum(needed, body), 0, 1)))
    # Quantize in premultiplied space so linear filtering also preserves soft edges.
    rgb = clean * (alpha.astype("float32") / 255)[:, :, None] + signal
    out = np.empty((*alpha.shape, 4), np.uint8)
    out[:, :, :3] = np.clip(np.rint(rgb), 0, alpha[:, :, None]).astype("uint8")
    out[:, :, 3] = alpha
    return out


def encode_layer(path, source, pictures):
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgra",
        "-s",
        "1280x720",
        "-r",
        "24",
        "-i",
        "pipe:0",
        "-i",
        str(source),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "ffv1",
        "-level",
        "3",
        "-coder",
        "1",
        "-g",
        "12",
        "-threads",
        "4",
        "-pix_fmt",
        "bgra",
        "-c:a",
        "copy",
        str(path),
    ]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as p:
        try:
            for pic in pictures:
                p.stdin.write(memoryview(pic))
        finally:
            p.stdin.close()
        if p.wait():
            raise RuntimeError("Encoding failed: " + str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "base", type=Path, help="First release with the uncomposited H3 action takes"
    )
    ap.add_argument("work", type=Path, help="H3 takes for the street and flame charge")
    ap.add_argument("output", type=Path, help="Separate staging directory")
    ap.add_argument(
        "ledger", type=Path, help="Action provenance from the first release"
    )
    args = ap.parse_args()
    if args.output.resolve() == args.base.resolve():
        ap.error("The base and staging directory must differ")
    cv2.setNumThreads(3)
    world = args.output / WORLD
    media = args.output / MEDIA / "once"
    (world / "production").mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)
    level = json.loads((args.base / WORLD / "level.json").read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    src = args.work / "takes/street_once_01/source.mp4"
    street = media / "street.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(src),
            "-vf",
            "scale=1280:720:flags=lanczos,fps=24",
            "-c:v",
            "libx264",
            "-crf",
            "16",
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
            "-movflags",
            "+faststart",
            str(street),
        ],
        check=True,
    )
    cap = cv2.VideoCapture(str(street))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, count - 1)
    ok, empty = cap.read()
    cap.release()
    if not ok:
        raise ValueError("Cannot read the street's resting pose")
    level["street"] = {"frames": count, "sha256": digest(street)}
    ledger["street"] = {
        **info(args.work, "street_once_01"),
        "final_sha256": level["street"]["sha256"],
    }
    charge = sample(decode(args.work / "takes/wisp_live_charge/source.mp4"), 15)[:-1]
    for clip, meta in level["clips"].items():
        src = args.base / MEDIA / (clip + ".mp4")
        old = meta["sha256"]
        if digest(src) != old:
            raise ValueError("Base action mismatch: " + clip)
        frames = decode(src)
        clean = plate_reference(clip, frames, empty).astype("float32")
        if clip == "wisp":
            frames[:14] = [
                cv2.resize(f, SIZE, interpolation=cv2.INTER_CUBIC) for f in charge
            ]
        expanded = cv2.dilate(
            clean, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        )
        layer = media / (clip + ".mkv")
        with tempfile.TemporaryDirectory(dir=media) as tmp:
            staged = Path(tmp) / layer.name
            encode_layer(
                staged,
                src,
                (foreground(clip, i, f, clean, expanded) for i, f in enumerate(frames)),
            )
            staged.replace(layer)
        sha = digest(layer)
        if meta.get("windows"):
            mask = (args.base / WORLD / (clip + ".mask")).read_bytes()
            if mask[:36] != b"DCM1" + bytes.fromhex(old):
                raise ValueError("Wrong source mask: " + clip)
            if clip == "wisp":
                offset = 38
                prefix = bytearray()
                for i in range(14):
                    (count,) = struct.unpack_from("<H", mask, offset)
                    offset += 2 + 6 * count
                    rows = spans(draw_mask(clip, i, frames[i], meta["windows"][0]))
                    prefix.extend(struct.pack("<H", len(rows)))
                    for row in rows:
                        prefix.extend(struct.pack("<3H", *row))
                mask = mask[:38] + prefix + mask[offset:]
            (world / (clip + ".mask")).write_bytes(
                b"DCM1" + bytes.fromhex(sha) + mask[36:]
            )
        meta["sha256"] = sha
        ledger[clip]["action_export_sha256"] = old
        ledger[clip]["final_sha256"] = sha
        if clip == "wisp":
            ledger[clip]["charge_take"] = info(args.work, "wisp_live_charge")
            ledger[clip]["padding_frames"] = 0
        print(clip, len(frames), layer.stat().st_size, flush=True)
    write_json(world / "level.json", level)
    write_json(world / "production/media.json", ledger)


if __name__ == "__main__":
    main()
