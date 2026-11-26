"""Generate, stabilize, trim, and extract anchors for Chapter 1 H3 video assets."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from changan_h3 import generate as h3_generate

ROOT = Path(__file__).resolve().parents[2]
KEYS = ROOT / "assets/linyuan/kf_raw/horizon_v1"
ART = ROOT / "assets/linyuan"
WORK = ROOT / "output/linyuan_prod"
PRODUCTION = ROOT / "worlds/linyuan/production"
ANCHORS_DIR = PRODUCTION / "ch1_anchors"
SELECTIONS_DIR = PRODUCTION / "ch1_selections"
BINDING = PRODUCTION / "ch1_bindings.json"
SHEET = ROOT / "docs/LINYUAN_CH1_PROMPTS.md"

# Complete catalog of the 49 new Chapter 1 H3 video IDs.
CH1_DRAMA = {
    "c1_01_vista": dict(first="KF_C1_01", last=None, length=119),
    "c1_02_descend": dict(first="KF_C1_02", last=None, length=119),
    "c1_03_market": dict(first="PL_MARKET", last=None, length=119),
    "c1_05_redeye": dict(first="KF_C1_05", last=None, length=119),
    "c1_06_leap": dict(first="KF_C1_06", last=None, length=73),
    "c1_13_conch": dict(first="KF_C1_13", last=None, length=119),
    "c1_14_core": dict(first="KF_C1_14", last=None, length=119),
    "c1_15_lookup": dict(first="KF_C1_15", last=None, length=119),
    "c1_20_smoke": dict(first="KF_C1_20", last=None, length=119),
    "c1_21_run": dict(first="KF_C1_21", last=None, length=119),
    "c1_22_board": dict(first="KF_C1_22", last=None, length=119),
}

DUKOU_WAVES = [
    "c1_w_bifang_awning",
    "c1_w_bifang_sky",
    "c1_w_suanni_tables",
    "c1_w_suanni_shrine",
    "c1_w_suanni_bridge",
]

DUKOU_SLOTS = ("early", "mid", "late")


def build_catalog():
    items = {}
    for name, spec in CH1_DRAMA.items():
        items[name] = dict(group="drama", heading=name, **spec)
    items["c1_dukou_plate"] = dict(
        group="dukou", heading="c1_dukou_plate", first="PL_DUKOU", last="PL_DUKOU", length=175
    )
    for w in DUKOU_WAVES:
        items[w] = dict(group="dukou", heading=w, first="PL_DUKOU", last="PL_DUKOU", length=99)
    items["c1_w_peddler"] = dict(
        group="dukou", heading="c1_w_peddler", first="PL_DUKOU", last="PL_DUKOU", length=99
    )
    for w in DUKOU_WAVES:
        if "bifang" in w:
            heading = "**c1_w_bifang_awning_kill_*"
        elif w == "c1_w_suanni_bridge":
            heading = "**c1_w_suanni_bridge_kill_*"
        else:
            heading = "**c1_w_suanni_tables_kill_*"
        for slot in DUKOU_SLOTS:
            items[f"{w}_kill_{slot}"] = dict(
                group="dukou",
                heading=heading,
                first=f"@{w}/{slot}",
                last="PL_DUKOU",
                length=47,
            )

    # S6 Boss Taotie (16 videos)
    items["c1_boss_enter"] = dict(
        group="boss", heading="c1_boss_enter", first="PL_SHOAL", last="K_TAOTIE_1", length=119
    )
    for letter, ord_word in (("a", "first"), ("b", "second"), ("c", "third")):
        items[f"c1_boss_p1_{letter}"] = dict(
            group="boss",
            heading="c1_boss_p1_a / c1_boss_p1_b / c1_boss_p1_c",
            first="K_TAOTIE_1",
            last="K_TAOTIE_1",
            length=119,
            subs={"<n>": ord_word},
        )
    for side_key, side_text in (("l", "screen-left"), ("r", "screen-right")):
        pose = "left_aim" if side_key == "l" else "right_aim"
        items[f"c1_boss_p1_flinch_{side_key}"] = dict(
            group="boss",
            heading="c1_boss_p1_flinch_l / _r",
            first=f"@c1_boss_p1_a/{pose}",
            last="K_TAOTIE_1",
            length=47,
            subs={"<side>": side_text},
        )
    items["c1_boss_break"] = dict(
        group="boss",
        heading="c1_boss_break",
        first="@c1_boss_p1_c/right_aim",
        last="K_TAOTIE_2",
        length=73,
    )
    items["c1_boss_p2_launch"] = dict(
        group="boss",
        heading="c1_boss_p2_launch",
        first="K_TAOTIE_2",
        last="K_TAOTIE_2",
        length=99,
    )
    for slot in ("early", "mid", "late"):
        items[f"c1_boss_p2_intercept_{slot}"] = dict(
            group="boss",
            heading="c1_boss_p2_intercept_early / _mid / _late",
            first=f"@c1_boss_p2_launch/{slot}",
            last="K_TAOTIE_2",
            length=47,
        )
    items["c1_boss_p2_impact"] = dict(
        group="boss",
        heading="c1_boss_p2_impact",
        first="@c1_boss_p2_launch/impact",
        last="K_TAOTIE_2",
        length=47,
    )
    items["c1_boss_expose"] = dict(
        group="boss",
        heading="c1_boss_expose",
        first="K_TAOTIE_2",
        last="K_TAOTIE_3",
        length=73,
    )
    items["c1_boss_p3"] = dict(
        group="boss",
        heading="c1_boss_p3",
        first="K_TAOTIE_3",
        last="K_TAOTIE_3",
        length=99,
    )
    items["c1_boss_p3_flinch"] = dict(
        group="boss",
        heading="c1_boss_p3_flinch",
        first="K_TAOTIE_3",
        last="K_TAOTIE_3",
        length=47,
    )
    items["c1_boss_kill"] = dict(
        group="boss",
        heading="c1_boss_kill",
        first="K_TAOTIE_3",
        last="K_TAOTIE_END",
        length=73,
    )
    return items


def resolve_prompt(spec):
    doc = SHEET.read_text(encoding="utf8")
    h = spec["heading"]
    heading = h if h.startswith("**") else ("**" + h + "**")
    start = doc.index(heading)
    body = doc[start:].split("```", 2)[1].strip()
    for _ in range(4):
        tokens = set(re.findall(r"\[[A-Z_]+\]", body))
        if not tokens:
            break
        for token in tokens:
            ref = doc.index("**" + token)
            body = body.replace(token, doc[ref:].split("```", 2)[1].strip())
    for k, v in spec.get("subs", {}).items():
        body = body.replace(k, v)
    return body


def rel(path):
    return path.relative_to(ROOT).as_posix()


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf8", dir=path.parent, delete=False,
        prefix=path.stem + ".", suffix=".writing",
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    out = Path(tmp.name)
    try:
        out.replace(path)
    finally:
        out.unlink(missing_ok=True)


def resolve_anchor_files(spec):
    refs = [spec["first"], spec["last"]]
    ret = {}
    for ref in filter(None, refs):
        if ref.startswith("@"):
            source, slot = ref[1:].split("/")
            proof = ANCHORS_DIR / f"{source}_{slot}.json"
            info = json.loads(proof.read_bytes())
            if hash_file(ROOT / info["source"]) != info["sha256"]:
                raise ValueError(f"Stale extraction: {proof}")
            ret[ref] = (ROOT / info["anchor"]).stem
        else:
            ret[ref] = ref
    return ret


def generate_take(name, variant=1):
    cat = build_catalog()
    spec = cat[name]
    resolved = resolve_anchor_files(spec)
    idx = sorted(cat).index(name)
    job = {
        "first": resolved[spec["first"]],
        "length": spec["length"],
        "prompt": resolve_prompt(spec),
        "prefix": "",
        "seed": 721000 + idx * 19 + variant,
    }
    if spec["last"]:
        job["last"] = resolved[spec["last"]]
    h3_generate(f"linyuan_{name}__v{variant}", job, KEYS, WORK)


def extract_anchor(source_name, slot, source_video, frame):
    if frame < 0:
        raise ValueError("Frame must be nonnegative")
    source_video = source_video.resolve()
    digest = hash_file(source_video)
    dest = KEYS / f"src_{source_name}_{slot}_{frame}_{digest[:12]}.png"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(source_video),
            "-vf", f"select=eq(n\\,{frame}),scale=1280:720:flags=lanczos",
            "-frames:v", "1", str(dest),
        ],
        check=True,
    )
    if not dest.exists():
        raise ValueError(f"No decoded frame {frame} in {source_video}")
    write_json(
        ANCHORS_DIR / f"{source_name}_{slot}.json",
        {"source": rel(source_video), "frame": frame, "sha256": digest, "anchor": rel(dest)},
    )
    print(f"Anchor extracted: {source_name}/{slot} @ f{frame} -> {dest.name}", flush=True)


def stabilize_to_plate(src_mp4, plate_png, start, end, speed, kill=False):
    """Warp H3 frames to exact plate registration and blend out static background drift."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(src_mp4))
    raw_frames = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        raw_frames.append(img)
    cap.release()
    if not raw_frames:
        raise ValueError(f"Empty video {src_mp4}")

    end_idx = end if end else len(raw_frames)
    sub = raw_frames[start:end_idx]
    if speed != 1.0:
        target_n = max(2, int(round(len(sub) / speed)))
        idxs = [min(len(sub) - 1, int(round(i * (len(sub) - 1) / max(1, target_n - 1)))) for i in range(target_n)]
        sub = [sub[i] for i in idxs]

    h, w = sub[0].shape[:2]
    plate_full = cv2.imread(str(plate_png))
    plate = cv2.resize(plate_full, (w, h), interpolation=cv2.INTER_AREA)
    orb = cv2.ORB_create(nfeatures=2400)
    kp_ref, des_ref = orb.detectAndCompute(cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY), None)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    warped = []
    for raw in sub:
        kp, des = orb.detectAndCompute(cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY), None)
        if des is None or des_ref is None:
            warped.append(raw)
            continue
        matches = matcher.knnMatch(des, des_ref, k=2)
        good = [m for pair in matches if len(pair) == 2 for m, n in [pair] if m.distance < 0.74 * n.distance]
        if len(good) >= 12:
            src_pts = np.float32([kp[m.queryIdx].pt for m in good])
            dst_pts = np.float32([kp_ref[m.trainIdx].pt for m in good])
            mat, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if mat is not None:
                warped.append(cv2.warpAffine(raw, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))
                continue
        warped.append(raw)

    empty = warped[-1] if kill else warped[0]
    out_frames = []
    for f, img in enumerate(warped):
        if f == len(warped) - 1 or (f == 0 and not kill):
            out_frames.append(cv2.resize(plate_full, (1280, 720), interpolation=cv2.INTER_LANCZOS4))
            continue
        diff = cv2.absdiff(img, empty).max(axis=2)
        mask = np.uint8(diff > 24) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
        alpha = cv2.GaussianBlur(mask, (9, 9), 1.8).astype(np.float32) / 255.0
        # Guarantee clean blend to empty plate over last 3 frames of wave or kill.
        tail = len(warped) - 1 - f
        if tail < 3:
            alpha *= tail / 3.0
        comp = plate.astype(np.float32) * (1.0 - alpha[..., None]) + img.astype(np.float32) * alpha[..., None]
        u8 = np.uint8(np.clip(comp, 0, 255))
        out_frames.append(cv2.resize(u8, (1280, 720), interpolation=cv2.INTER_LANCZOS4))
    return out_frames


def encode_h264_frames(frames, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".part.mp4")
    h, w = frames[0].shape[:2]
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", "24", "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-threads", "4", "-preset", "veryfast", "-crf", "17",
        "-bf", "0", "-g", "12", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart",
        str(temp),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for img in frames:
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed ({rc}) for {dest}")
    temp.replace(dest)


def publish(name, variant=1, start=0, end=0, speed=1.0, note="ch1", stabilize_plate=None):
    cat = build_catalog()
    spec = cat[name]
    media_id = name
    if "_kill_" in name and spec["group"] == "dukou":
        wave, slot = name.rsplit("_kill_", 1)
        anchor = json.loads((ANCHORS_DIR / f"{wave}_{slot}.json").read_bytes())
        media_id = f"{wave}_kill_{anchor['frame']}"
    candidate = f"linyuan_{name}__v{variant}"
    source = WORK / "takes" / candidate / "source.mp4"
    subdir = "dukou" if spec["group"] == "dukou" else "drama"
    dest = ART / subdir / (media_id + ".mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)

    if stabilize_plate is not None:
        frames_list = stabilize_to_plate(
            source, KEYS / (stabilize_plate + ".png"), start, end, speed,
            kill="_kill_" in name,
        )
        encode_h264_frames(frames_list, dest)
    else:
        trim = f"trim=start_frame={start}" + (f":end_frame={end}" if end else "")
        vf = f"{trim},setpts=(PTS-STARTPTS)/{speed},fps=24,scale=1280:720:flags=lanczos,setsar=1"
        temp = dest.with_suffix(".part.mp4")
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-y",
                "-i", str(source),
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-map", "0:v:0", "-vf", vf, "-map", "1:a:0",
                "-c:v", "libx264", "-threads", "4", "-preset", "veryfast", "-crf", "17",
                "-bf", "0", "-g", "12", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart",
                str(temp),
            ],
            check=True,
        )
        temp.replace(dest)

    frames = int(
        subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=nb_frames", "-of", "csv=p=0", str(dest),
            ],
            text=True,
        ).strip()
    )
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
    write_json(SELECTIONS_DIR / (name + ".json"), selection)
    print(json.dumps(selection, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_take = sub.add_parser("take")
    p_take.add_argument("names", nargs="+")
    p_take.add_argument("--variant", type=int, default=1)

    p_batch = sub.add_parser("batch")
    p_batch.add_argument("group", choices=["drama_early", "drama_late", "dukou_plates", "boss_p1", "boss_p2", "boss_p3"])
    p_batch.add_argument("--variant", type=int, default=1)

    p_ext = sub.add_parser("extract")
    p_ext.add_argument("source_name")
    p_ext.add_argument("slot")
    p_ext.add_argument("source_video", type=Path)
    p_ext.add_argument("frame", type=int)

    p_pub = sub.add_parser("publish")
    p_pub.add_argument("name")
    p_pub.add_argument("--variant", type=int, default=1)
    p_pub.add_argument("--start", type=int, default=0)
    p_pub.add_argument("--end", type=int, default=0)
    p_pub.add_argument("--speed", type=float, default=1.0)
    p_pub.add_argument("--plate", default=None)
    p_pub.add_argument("--note", default="ch1")

    args = parser.parse_args()
    if args.cmd == "take":
        for n in args.names:
            generate_take(n, args.variant)
    elif args.cmd == "batch":
        groups = {
            "drama_early": ["c1_01_vista", "c1_02_descend", "c1_03_market", "c1_05_redeye", "c1_06_leap", "c1_13_conch", "c1_14_core", "c1_15_lookup"],
            "drama_late": ["c1_20_smoke", "c1_21_run", "c1_22_board"],
            "dukou_plates": ["c1_dukou_plate"] + DUKOU_WAVES + ["c1_w_peddler"],
            "boss_p1": ["c1_boss_enter", "c1_boss_p1_a", "c1_boss_p1_b", "c1_boss_p1_c"],
            "boss_p2": ["c1_boss_p2_launch"],
            "boss_p3": ["c1_boss_expose", "c1_boss_p3", "c1_boss_p3_flinch", "c1_boss_kill"],
        }
        for n in groups[args.group]:
            generate_take(n, args.variant)
    elif args.cmd == "extract":
        extract_anchor(args.source_name, args.slot, args.source_video, args.frame)
    elif args.cmd == "publish":
        publish(args.name, args.variant, args.start, args.end, args.speed, args.note, args.plate)


if __name__ == "__main__":
    main()
