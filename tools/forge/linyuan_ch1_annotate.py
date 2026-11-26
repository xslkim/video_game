"""Extract stabilized masks, amber weak spots, background materials, threat glows, and boss polygons for Chapter 1."""

import hashlib
import json
import struct
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/forge"))
import linyuan_ch1_media as m

KEYS = ROOT / "assets/linyuan/kf_raw/horizon_v1"
ART = ROOT / "assets/linyuan"
WORLD = ROOT / "worlds/linyuan"


def rle_encode(mask_u8):
    """Encode 640x360 binary mask rows matching changan Mask format (u16 spans per row)."""
    small = cv2.resize(mask_u8, (640, 360), interpolation=cv2.INTER_NEAREST)
    out = bytearray()
    for y in range(360):
        row = small[y] > 0
        padded = np.concatenate(([False], row, [False]))
        diffs = np.flatnonzero(padded[1:] != padded[:-1])
        spans = diffs.reshape(-1, 2)
        out.extend(struct.pack("<H", len(spans)))
        for x0, x1 in spans:
            out.extend(struct.pack("<HH", int(x0), int(x1)))
    return bytes(out)


def write_camask(path, masks_per_frame):
    encoded = [rle_encode(frame) for frame in masks_per_frame]
    header = bytearray(b"CAMASK\x01\x00")
    header.extend(struct.pack("<III", 640, 360, len(encoded)))
    for blob in encoded:
        header.extend(struct.pack("<I", len(blob)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + b"".join(encoded))


def build_dukou_materials():
    """Classify 36x64 tiles of PL_DUKOU into valid engine material names."""
    img = cv2.imread(str(KEYS / "PL_DUKOU.png"))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Allowed names per changan_game.cpp:213 -> {"air", "water", "stone", "earth", "bamboo", "metal"}
    rows = []
    for r in range(36):
        line = []
        y0, y1 = r * 20, (r + 1) * 20
        for c in range(64):
            x0, x1 = c * 20, (c + 1) * 20
            patch_bgr = img[y0:y1, x0:x1]
            patch_hsv = hsv[y0:y1, x0:x1]
            b, g, red = patch_bgr.mean(axis=(0, 1))
            _, s, v = patch_hsv.mean(axis=(0, 1))
            if y0 < 170 and x0 >= 540 and b > 170 and red > 140:
                mat = "air"
            elif 280 <= x0 < 920 and 240 <= y0 < 395 and g > red + 8 and b > 105:
                mat = "water"
            elif y0 < 230 and g > red + 8 and g > 85:
                mat = "bamboo"
            elif (x0 < 540 and y0 >= 380) or (x0 < 520 and y0 < 400 and (red > b + 15 or v < 90)):
                mat = "bamboo"
            elif x0 >= 900 and 100 <= y0 < 380 and v > 155 and s < 55:
                mat = "metal"
            elif y0 >= 580 and s > 40 and red > b + 20:
                mat = "earth"
            else:
                mat = "stone"
            line.append(mat)
        rows.append(line)
    return rows


def read_video(path):
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    return frames


def analyze_dukou_wave(wave_mp4, plate_img, is_civilian=False):
    """Segment enemy body + amber weak points from a stabilized dukou wave video."""
    frames = read_video(wave_mp4)
    n = len(frames)
    plate = cv2.resize(plate_img, (frames[0].shape[1], frames[0].shape[0]))
    body_masks = []
    weak_masks = []
    body_counts = []
    weak_counts = []
    glow_points = []

    for f, img in enumerate(frames):
        diff = cv2.absdiff(img, plate).max(axis=2)
        body = np.uint8(diff > 22) * 255
        body = cv2.morphologyEx(body, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
        # Remove tiny specks < 90 px
        contours, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        clean_body = np.zeros_like(body)
        for cnt in contours:
            if cv2.contourArea(cnt) >= 90:
                cv2.drawContours(clean_body, [cnt], -1, 255, cv2.FILLED)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Glowing amber-gold canister/sac/core detection inside the body envelope
        amber = np.uint8(
            (hsv[:, :, 0] >= 12) & (hsv[:, :, 0] <= 34) &
            (hsv[:, :, 1] >= 105) & (hsv[:, :, 2] >= 145)
        ) * 255
        env = cv2.dilate(clean_body, np.ones((15, 15), np.uint8))
        weak = cv2.bitwise_and(amber, env)
        weak = cv2.morphologyEx(weak, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        weak = cv2.dilate(weak, np.ones((5, 5), np.uint8))
        # Ensure weak mask covers a clean playable hitbox if amber pixels are small
        if not is_civilian and cv2.countNonZero(weak) < 80 and cv2.countNonZero(clean_body) >= 600:
            ys, xs = np.where(clean_body > 0)
            cx, cy = int(xs.mean()), int(ys.min() + (ys.max() - ys.min()) * 0.42)
            cv2.circle(weak, (cx, cy), 22, 255, -1)

        # Red eye/core glow points (sampled at top ~1/3 of body for threat glow)
        red = np.uint8(
            ((hsv[:, :, 0] <= 10) | (hsv[:, :, 0] >= 168)) &
            (hsv[:, :, 1] >= 140) & (hsv[:, :, 2] >= 165)
        ) * 255
        red_in_body = cv2.bitwise_and(red, clean_body)
        red_pts = []
        rcnt, _ = cv2.findContours(red_in_body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sorted(rcnt, key=cv2.contourArea, reverse=True)[:2]:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                red_pts.extend([int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])])
        if not is_civilian and red_pts and 18 <= f <= n - 18:
            glow_points.append([f, *red_pts])

        body_masks.append(clean_body)
        weak_masks.append(weak)
        body_counts.append(int(cv2.countNonZero(clean_body)))
        weak_counts.append(int(cv2.countNonZero(weak)))

    # Pick active interactive window where body is clearly visible
    thresh = max(600, int(max(body_counts) * 0.18))
    active = [i for i, c in enumerate(body_counts) if c >= thresh]
    w_begin = max(8, active[0] if active else 20)
    w_end = min(n - 12, (active[-1] + 1) if active else 62)
    if w_end - w_begin < 18:
        w_begin, w_end = 18, min(n - 10, 62)

    if is_civilian:
        return {
            "body_masks": body_masks,
            "weak_masks": weak_masks,
            "window": [w_begin, w_end],
            "glow_points": [],
        }

    # Three evenly spaced cut slots matching ~28, 42, 56 or thirds of [w_begin, w_end]
    slots = {
        "early": max(w_begin + 4, min(w_end - 8, int(w_begin + (w_end - w_begin) * 0.25))),
        "mid": max(w_begin + 6, min(w_end - 6, int(w_begin + (w_end - w_begin) * 0.50))),
        "late": max(w_begin + 8, min(w_end - 4, int(w_begin + (w_end - w_begin) * 0.78))),
    }
    warning = max(w_begin, w_end - 12)
    impact = min(n - 4, w_end + 4)
    return {
        "body_masks": body_masks,
        "weak_masks": weak_masks,
        "window": [w_begin, w_end],
        "slots": slots,
        "warning": warning,
        "impact": impact,
        "glow_points": glow_points,
    }


def bbox_poly(cx, cy, rx, ry, sides=16):
    pts = []
    for k in range(sides):
        ang = 2.0 * np.pi * k / sides
        pts.append([int(round(cx + rx * np.cos(ang))), int(round(cy + ry * np.sin(ang)))])
    return pts


def contour_poly(mask, fallback_center, fallback_r=(55, 55)):
    """Always emit a fixed 16-vertex elliptical polygon matching TrackedRegion invariants."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return bbox_poly(fallback_center[0], fallback_center[1], fallback_r[0], fallback_r[1], sides=16)
    big = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(big) < 120:
        return bbox_poly(fallback_center[0], fallback_center[1], fallback_r[0], fallback_r[1], sides=16)
    x, y, bw, bh = cv2.boundingRect(big)
    cx, cy = x + bw * 0.5, y + bh * 0.5
    rx = max(24.0, min(fallback_r[0] * 1.6, bw * 0.65))
    ry = max(24.0, min(fallback_r[1] * 1.6, bh * 0.65))
    return bbox_poly(cx, cy, rx, ry, sides=16)


def extract_boss_regions():
    """Extract fixed-vertex polygon regions for S6 Taotie P1 hoops, P2 fireball, and P3 maw core."""
    reg_dir = WORLD / "regions"
    reg_dir.mkdir(parents=True, exist_ok=True)
    meta = {}

    # Phase 1: canister hoops on c1_boss_p1_{a,b,c}
    for letter in ("a", "b", "c"):
        take_id = f"c1_boss_p1_{letter}"
        mp4 = ART / "drama" / f"{take_id}.mp4"
        sha = hashlib.sha256(mp4.read_bytes()).hexdigest()
        frames = read_video(mp4)
        n = len(frames)
        mid = n // 2
        hoop_all = []
        hoop_l = []
        hoop_r = []
        for f, img in enumerate(frames):
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            amber = np.uint8(
                (hsv[:, :, 0] >= 12) & (hsv[:, :, 0] <= 34) &
                (hsv[:, :, 1] >= 100) & (hsv[:, :, 2] >= 145)
            ) * 255
            roi_l = np.zeros_like(amber)
            roi_l[60:320, 420:670] = amber[60:320, 420:670]
            poly_l = contour_poly(roi_l, (585, 165), (54, 58))
            roi_r = np.zeros_like(amber)
            roi_r[60:320, 620:880] = amber[60:320, 620:880]
            poly_r = contour_poly(roi_r, (715, 165), (54, 58))
            hoop_l.append({"frame": f, "polygon": poly_l})
            hoop_r.append({"frame": f, "polygon": poly_r})
            hoop_all.append({"frame": f, "polygon": poly_l if f < mid else poly_r})
        out_path = reg_dir / f"{take_id}.json"
        out_path.write_text(
            json.dumps({"sha256": sha, "regions": {"hoop": hoop_all, "hoop_l": hoop_l, "hoop_r": hoop_r}},
                       separators=(",", ":")),
            encoding="utf8",
        )
        meta[take_id] = {"sha256": sha, "frames": n, "left_aim": min(28, mid // 2), "right_aim": min(n - 20, mid + (n - mid) // 2)}

    # Phase 2: approaching fireball in c1_boss_p2_launch (trimmed 0..64; fireball flies f22..56)
    p2_mp4 = ART / "drama/c1_boss_p2_launch.mp4"
    p2_sha = hashlib.sha256(p2_mp4.read_bytes()).hexdigest()
    p2_frames = read_video(p2_mp4)
    p2_base = cv2.imread(str(KEYS / "K_TAOTIE_2.png"))
    fb_polys = []
    fb_scores = []
    for f, img in enumerate(p2_frames):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        diff = cv2.absdiff(img, p2_base).max(axis=2)
        fire = np.uint8(
            (hsv[:, :, 0] <= 34) & (hsv[:, :, 1] >= 120) & (hsv[:, :, 2] >= 180) & (diff > 38)
        ) * 255
        roi = np.zeros_like(fire)
        roi[180:690, 220:1040] = fire[180:690, 220:1040]
        cnts, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = max((cv2.contourArea(c) for c in cnts), default=0.0)
        if 22 <= f <= min(55, len(p2_frames) - 4) and area >= 250:
            poly = contour_poly(roi, (640, 410), (72, 72))
            fb_scores.append((f, area, poly))
        else:
            poly = bbox_poly(640, 405, 68, 68, sides=16)
        fb_polys.append({"frame": f, "polygon": poly})
    (reg_dir / "c1_boss_p2_launch.json").write_text(
        json.dumps({"sha256": p2_sha, "regions": {"fireball": fb_polys}}, separators=(",", ":")),
        encoding="utf8",
    )
    active_fb = [f for f, _, _ in fb_scores] or list(range(24, 54))
    b0, b1 = max(20, active_fb[0]), min(len(p2_frames) - 3, active_fb[-1])
    span = max(9, b1 - b0 + 1)
    p2_e = b0 + max(2, span // 4)
    p2_m = b0 + max(4, span // 2)
    p2_l = b0 + max(6, (span * 3) // 4)
    p2_imp = min(len(p2_frames) - 2, b1 + 2)
    meta["c1_boss_p2_launch"] = {
        "sha256": p2_sha, "frames": len(p2_frames),
        "begin": b0, "end": b1 + 1,
        "early": p2_e, "mid": p2_m, "late": p2_l, "impact": p2_imp,
    }

    # Phase 3: open-maw core in c1_boss_p3
    p3_mp4 = ART / "drama/c1_boss_p3.mp4"
    p3_sha = hashlib.sha256(p3_mp4.read_bytes()).hexdigest()
    p3_frames = read_video(p3_mp4)
    core_polys = []
    for f, img in enumerate(p3_frames):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        amber = np.uint8(
            (hsv[:, :, 0] >= 12) & (hsv[:, :, 0] <= 34) &
            (hsv[:, :, 1] >= 115) & (hsv[:, :, 2] >= 165)
        ) * 255
        roi = np.zeros_like(amber)
        roi[290:520, 500:780] = amber[290:520, 500:780]
        core_polys.append({"frame": f, "polygon": contour_poly(roi, (640, 410), (54, 54))})
    (reg_dir / "c1_boss_p3.json").write_text(
        json.dumps({"sha256": p3_sha, "regions": {"core": core_polys}}, separators=(",", ":")),
        encoding="utf8",
    )
    meta["c1_boss_p3"] = {"sha256": p3_sha, "frames": len(p3_frames)}
    return meta


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["extract_dukou_anchors", "extract_boss_anchors", "finalize_annotations"])
    args = parser.parse_args()

    plate_img = cv2.imread(str(KEYS / "PL_DUKOU.png"))

    if args.step == "extract_dukou_anchors":
        for w in m.DUKOU_WAVES:
            src_mp4 = m.WORK / "takes" / f"linyuan_{w}__v1" / "source.mp4"
            info = analyze_dukou_wave(src_mp4, plate_img, is_civilian=False)
            for slot, frame_idx in info["slots"].items():
                m.extract_anchor(w, slot, src_mp4, frame_idx)

    elif args.step == "extract_boss_anchors":
        for cid in ("c1_boss_p1_a", "c1_boss_p1_c"):
            src = m.WORK / "takes" / f"linyuan_{cid}__v1" / "source.mp4"
            frames = read_video(src)
            mid = len(frames) // 2
            m.extract_anchor(cid, "left_aim", src, max(18, mid // 2))
            m.extract_anchor(cid, "right_aim", src, min(len(frames) - 18, mid + (len(frames) - mid) // 2))
        p2_src = m.WORK / "takes/linyuan_c1_boss_p2_launch__v1/source.mp4"
        p2_frames = read_video(p2_src)
        p2_base = cv2.resize(cv2.imread(str(KEYS / "K_TAOTIE_2.png")), (p2_frames[0].shape[1], p2_frames[0].shape[0]))
        active = []
        for f, img in enumerate(p2_frames):
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            diff = cv2.absdiff(img, p2_base).max(axis=2)
            fire = ((hsv[:, :, 0] <= 32) & (hsv[:, :, 1] >= 120) & (hsv[:, :, 2] >= 175) & (diff > 30))
            if 8 <= f <= len(p2_frames) - 8 and fire[120:540, 180:840].sum() >= 100:
                active.append(f)
        b0 = active[0] if active else 14
        b1 = active[-1] if active else 54
        span = max(9, b1 - b0 + 1)
        m.extract_anchor("c1_boss_p2_launch", "early", p2_src, b0 + max(2, span // 4))
        m.extract_anchor("c1_boss_p2_launch", "mid", p2_src, b0 + max(4, span // 2))
        m.extract_anchor("c1_boss_p2_launch", "late", p2_src, b0 + max(6, (span * 3) // 4))
        m.extract_anchor("c1_boss_p2_launch", "impact", p2_src, min(len(p2_frames) - 4, b1 + 2))

    elif args.step == "finalize_annotations":
        dukou_meta = {"waves": {}, "glows": {}}
        for w in m.DUKOU_WAVES:
            mp4 = ART / "dukou" / f"{w}.mp4"
            info = analyze_dukou_wave(mp4, plate_img, is_civilian=False)
            sha = m.hash_file(mp4)
            dukou_meta["waves"][w] = {
                "sha256": sha,
                "frames": len(info["body_masks"]),
                "window": info["window"],
                "slots": info["slots"],
                "warning": info["warning"],
                "impact": info["impact"],
                "body_masks": info["body_masks"],
                "weak_masks": info["weak_masks"],
            }
            if info["glow_points"]:
                dukou_meta["glows"][w] = {"sha256": sha, "points": info["glow_points"]}
        ped_mp4 = ART / "dukou/c1_w_peddler.mp4"
        ped_info = analyze_dukou_wave(ped_mp4, plate_img, is_civilian=True)
        dukou_meta["peddler"] = {
            "sha256": m.hash_file(ped_mp4),
            "frames": len(ped_info["body_masks"]),
            "window": ped_info["window"],
            "body_masks": ped_info["body_masks"],
        }
        (WORLD / "dukou").mkdir(parents=True, exist_ok=True)
        (WORLD / "dukou/threat_glows.json").write_text(
            json.dumps(dukou_meta["glows"], separators=(",", ":")), encoding="utf8"
        )
        mats = build_dukou_materials()
        plate_sha = hashlib.sha256((ART / "dukou/c1_dukou_plate.mp4").read_bytes()).hexdigest()
        boss_meta = extract_boss_regions()

        # Persist serializable metadata (without raw numpy arrays) for linyuan_ch1.py
        serial_waves = {
            w: {k: v for k, v in d.items() if k not in ("body_masks", "weak_masks")}
            for w, d in dukou_meta["waves"].items()
        }
        meta_out = {
            "materials": mats,
            "materials_sha256": plate_sha,
            "dukou_waves": serial_waves,
            "peddler": {k: v for k, v in dukou_meta["peddler"].items() if k != "body_masks"},
            "boss": boss_meta,
        }
        m.write_json(m.PRODUCTION / "ch1_annotations.json", meta_out)
        # Save pickled numpy masks into temporary production binary cache for linyuan_ch1.py
        import pickle
        cache = {
            "waves": {w: (d["body_masks"], d["weak_masks"]) for w, d in dukou_meta["waves"].items()},
            "peddler": dukou_meta["peddler"]["body_masks"],
        }
        (m.PRODUCTION / "ch1_masks_cache.pkl").write_bytes(pickle.dumps(cache))
        print("Finalized Chapter 1 annotations & boss polygons cleanly!", flush=True)


if __name__ == "__main__":
    main()
