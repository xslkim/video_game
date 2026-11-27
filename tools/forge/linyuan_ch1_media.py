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
    "c1_13_conch": dict(
        first="KF_C1_13", last=None, length=99,
        prompt_raw=(
            "[P_FILM] Locked medium-close shot matching KF_C1_13. Lu Chen raises his natural right hand holding a small "
            "spiral conch shell with faint glowing blue seam light to his ear, listening intently with narrowed eyes. "
            "His left mechanical arm hangs steady at his side, and his flat wooden eight-sword case stays still on his back. "
            "Warm afternoon breeze sways the cloth awning; tranquil clear blue sky and green karst peaks behind."
        ),
    ),
    "c1_14_core": dict(first="KF_C1_14", last=None, length=119),
    "c1_15_lookup": dict(
        first="KF_C1_15", last=None, length=73,
        prompt_raw=(
            "[P_FILM] Subtle slow camera tilt upward over Lu Chen's stationary back and shoulders toward the tall "
            "distant mountain peak and the glowing broken stone ring. His hands remain completely lowered out of frame, "
            "and the old wooden sword case with 8 small wuxia hilts and cyan tassels stays still on his back. "
            "NEVER pull out a giant sword. Golden afternoon sky."
        ),
    ),
    "c1_20_smoke": dict(
        first="KF_C1_20", last=None, length=99,
        prompt_raw=(
            "[P_FILM] Locked camera on the sunset river shoal matching KF_C1_20. The defeated dark Taotie kneels "
            "smoking in the center-right foreground with pebbles around it. Behind it on the left side of the river, "
            "the colossal tortoise Xuanwu wades slowly right while warm temple lanterns glow on its shell. Keep "
            "wide clear sky separation: the distant mountain's broken red ring on the right horizon stays 100% motionless."
        ),
    ),
    "c1_21_run": dict(
        first="KF_C1_21", last=None, length=73,
        prompt_raw=(
            "[P_FILM] Smooth tracking shot behind Lu Chen (carrying his flat wooden 8-sword case on his back, mechanical "
            "left arm, natural right arm) as he splashes through shallow water right up to the outside armor plates of "
            "Xuanwu's colossal lifting hind leg and reaches to grab a ceramic ridge step to climb aboard."
        ),
    ),
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
        if w == "c1_w_bifang_sky":
            items[w] = dict(
                group="dukou", heading=w, first="PL_DUKOU", last="PL_DUKOU",
                guide=["G_DUKOU_BIFANG_SKY", 32], length=99,
                prompt_raw=(
                    "[P_WAVE] Only ONE white ceramic flying crane machine (matching EN_BIFANG: TWO large segmented bird "
                    "wings, bird head with glowing red eye, glowing amber-gold chest sac, ONE folded bird talon — NEVER "
                    "a 4-legged beast!) flies out from behind the ruined stone archway into the open upper blue sky above "
                    "the square, hovers cleanly in the upper half of the frame (`y < 50%`) with chest sac blazing amber-gold, "
                    "fires two small spark bolts downward, then wheels back behind the archway into the clean empty PL_DUKOU plate.\n[M]"
                ),
            )
        else:
            items[w] = dict(group="dukou", heading=w, first="PL_DUKOU", last="PL_DUKOU", length=99)
    items["c1_w_peddler"] = dict(
        group="dukou", heading="c1_w_peddler", first="PL_DUKOU", last="PL_DUKOU",
        guide=["G_DUKOU_PEDDLER", 44], length=99,
        prompt_raw=(
            "[P_FIXED] Quiet sunlit cobblestone market square matching PL_DUKOU throughout; peaceful clear afternoon air "
            "with gentle sea breeze only. A frightened Chinese market peddler in indigo tunic enters on foot from the far "
            "left edge around frame 10 carrying a bamboo shoulder pole with two baskets of fresh green vegetables, runs "
            "steadily left-to-right across the flat stone paving glancing back over his shoulder, and exits completely "
            "off the far right edge by frame 86, leaving only the empty cobblestone square on the end frame."
        ),
    )
    kill_prompts = {
        "c1_w_bifang_awning": (
            "[P_FIXED] Locked camera matching the start frame's exact white ceramic crane machine and sunlit market. "
            "In the first 6 frames a crisp compact amber spark flashes on its chest sac and its eyes go dark. "
            "Keeping its exact two-winged bird anatomy intact, the stunned crane banks sharply upward-left and drops "
            "completely out of sight behind the upper-left striped cloth awning roof by frame 32, leaving the empty "
            "sunlit PL_DUKOU square clean and motionless from frame 34 through frame 46.\n[M]"
        ),
        "c1_w_bifang_sky": (
            "[P_FIXED] Locked camera matching the start frame's exact white ceramic crane machine in the sky. "
            "In the first 6 frames a crisp compact amber spark flashes on its chest sac and its eyes go dark. "
            "Keeping its exact two-winged bird anatomy intact, the stunned crane folds its wings and plummets swiftly "
            "away behind the distant stone archway and bridge into the river by frame 32, leaving the empty sunlit "
            "PL_DUKOU square clean and motionless from frame 34 through frame 46.\n[M]"
        ),
        "c1_w_suanni_tables": (
            "[P_FIXED] Locked camera matching the start frame's exact white ceramic lion machine on the square. "
            "In the first 6 frames a crisp compact amber spark flashes on its shoulder canister and its red eyes go dark. "
            "Keeping its exact white-and-graphite lion anatomy intact, the stunned machine recoils and bounds swiftly "
            "backward out of sight behind the mid-ground stall tables and stone archway by frame 33, leaving the empty "
            "sunlit PL_DUKOU square clean and motionless from frame 35 through frame 46.\n[M]"
        ),
        "c1_w_suanni_shrine": (
            "[P_FIXED] Locked camera matching the start frame's exact white ceramic lion machine by the shrine. "
            "In the first 6 frames a crisp compact amber spark flashes on its shoulder canister and its red eyes go dark. "
            "Keeping its exact white-and-graphite lion anatomy intact, the stunned machine recoils sideways and bounds "
            "swiftly out of sight behind the huge horned skull shrine at right by frame 33, leaving the empty "
            "sunlit PL_DUKOU square clean and motionless from frame 35 through frame 46.\n[M]"
        ),
        "c1_w_suanni_bridge": (
            "[P_FIXED] Locked camera matching the start frame's exact white ceramic lion machine on the bridge. "
            "In the first 6 frames a crisp compact amber spark flashes on its shoulder canister and its red eyes go dark. "
            "Keeping its exact white-and-graphite lion anatomy intact, the stunned machine stumbles backward and topples "
            "cleanly off the far side of the stone arch bridge into the river with a brief splash by frame 32, leaving "
            "the empty sunlit PL_DUKOU square clean and motionless from frame 35 through frame 46.\n[M]"
        ),
    }
    for w in DUKOU_WAVES:
        for slot in DUKOU_SLOTS:
            items[f"{w}_kill_{slot}"] = dict(
                group="dukou",
                heading=f"{w}_kill_{slot}",
                first=f"@{w}/{slot}",
                last="PL_DUKOU",
                length=47,
                prompt_raw=kill_prompts[w],
            )

    # S6 Boss Taotie (14 clean locked-wide videos: p1_l, p1_r replacing old zooming p1_a/b/c)
    items["c1_boss_enter"] = dict(
        group="boss", heading="c1_boss_enter", first="PL_SHOAL", last="K_TAOTIE_1", length=119
    )
    for side_key, side_text in (("l", "screen-left"), ("r", "screen-right")):
        items[f"c1_boss_p1_{side_key}"] = dict(
            group="boss",
            heading=f"c1_boss_p1_{side_key}",
            first="K_TAOTIE_1",
            last="K_TAOTIE_1",
            guide=[f"G_TAOTIE_P1_{side_key.upper()}", 24],
            length=73,
            prompt_raw=(
                "[P_BOSS] Locked wide shoal camera matching the first and last frames identically; zero camera zoom, "
                "zero crop, fixed lens. Taotie stands planted on all four legs in the center of the shoal with 1 "
                "horned bronze-mask head, red eyes, and 2 back shoulder canisters. Only the " + side_text +
                " shoulder canister blazes bright incandescent molten amber-gold continuously from frame 10 through "
                "frame 48 while the opposite shoulder canister remains dark unlit metal. Around frame 50 it stamps "
                "once cleanly without leaving center framing, the lit canister dims dark by frame 64, and it settles "
                "seamlessly into the exact K_TAOTIE_1 end anchor. No floating metal rings, no extra heads, no cables in the sky.\n[M]"
            ),
        )
        items[f"c1_boss_p1_flinch_{side_key}"] = dict(
            group="boss",
            heading="c1_boss_p1_flinch_l / _r",
            first=f"@c1_boss_p1_{side_key}/aim",
            last="K_TAOTIE_1",
            length=47,
            subs={"<side>": side_text},
        )
    items["c1_boss_break"] = dict(
        group="boss",
        heading="c1_boss_break",
        first="@c1_boss_p1_r/aim",
        last="K_TAOTIE_2",
        length=73,
        prompt_raw=(
            "[P_BOSS] Locked wide shoal camera matching the first and last frames. The right glowing canister explodes "
            "and tears away along with the left canister in compact orange amber bursts falling downward onto the "
            "shoal pebbles. NO floating metal rings or black tendrils in the air or sky. Smoke clears cleanly as the "
            "creature lowers its head with fire between its jaws, settling smoothly into the exact K_TAOTIE_2 end anchor.\n[M]"
        ),
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
    if "prompt_raw" in spec:
        body = spec["prompt_raw"].strip()
    else:
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
    if "guide" in spec:
        job["guide"] = spec["guide"]
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


def conform_clip(src_mp4, start, end, speed, in_png=None, out_png=None):
    """Resize raw locked-tripod H3 video cleanly with speed-scaling and smooth endpoint anchor feathering."""
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
        target_n = max(4, int(round(len(sub) / speed)))
        idxs = [min(len(sub) - 1, int(round(i * (len(sub) - 1) / max(1, target_n - 1)))) for i in range(target_n)]
        sub = [sub[i] for i in idxs]

    out_frames = [
        f if f.shape[:2] == (720, 1280) else cv2.resize(f, (1280, 720), interpolation=cv2.INTER_LANCZOS4)
        for f in sub
    ]
    if in_png is not None:
        in_im = cv2.resize(cv2.imread(str(in_png)), (1280, 720), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        in_weights = (1.0, 0.55, 0.22)
        for k, w in enumerate(in_weights):
            if k < len(out_frames):
                blended = out_frames[k].astype(np.float32) * (1.0 - w) + in_im * w
                out_frames[k] = np.uint8(np.clip(blended, 0, 255))
    if out_png is not None:
        out_im = cv2.resize(cv2.imread(str(out_png)), (1280, 720), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        out_weights = (0.48, 1.0)
        n = len(out_frames)
        for offset, w in enumerate(out_weights):
            idx = n - len(out_weights) + offset
            if 0 <= idx < n:
                blended = out_frames[idx].astype(np.float32) * (1.0 - w) + out_im * w
                out_frames[idx] = np.uint8(np.clip(blended, 0, 255))
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


def _resolve_anchor_png(ref):
    if not ref:
        return None
    if ref.startswith("@"):
        source, slot = ref[1:].split("/")
        info = json.loads((ANCHORS_DIR / f"{source}_{slot}.json").read_bytes())
        return ROOT / info["anchor"]
    return KEYS / (ref + ".png")


def publish(name, variant=1, start=0, end=0, speed=1.0, note="ch1", stabilize_plate=None,
            in_anchor=None, out_anchor=None):
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

    in_ref = in_anchor if in_anchor is not None else stabilize_plate
    out_ref = out_anchor if out_anchor is not None else stabilize_plate
    if in_ref is not None or out_ref is not None or speed != 1.0:
        frames_list = conform_clip(
            source, start, end, speed,
            in_png=_resolve_anchor_png(in_ref),
            out_png=_resolve_anchor_png(out_ref),
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
            "boss_p1": ["c1_boss_enter", "c1_boss_p1_l", "c1_boss_p1_r"],
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
