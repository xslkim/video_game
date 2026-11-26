"""Conform the feedback-pass H3 takes and retain source-frame evidence for the gameplay bindings."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np

import linyuan_media as media


AUDIT = media.ART / "audit/tuning_20261126"
BASE = AUDIT / "baseline"
JOBS = media.PRODUCTION / "tuning_jobs.json"


def source(name, variant):
    return media.WORK / "takes" / f"linyuan_{name}__v{variant}" / "source.mp4"


def read_frames(path):
    capture = cv2.VideoCapture(str(path))
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            yield image
    finally:
        capture.release()


def write_video(path, pictures):
    temp = path.with_suffix(".tuning.mp4")
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s:v", "1280x720", "-r", "24", "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
               "-r", "24", "-pix_fmt", "yuv420p", "-bf", "0", "-g", "24", "-threads", "4", "-c:a", "aac",
               "-shortest", "-movflags", "+faststart", str(temp)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    count = 0
    try:
        for frame in pictures:
            if frame.shape[:2] != (720, 1280):
                frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LANCZOS4)
            process.stdin.write(frame.tobytes())
            count += 1
    finally:
        process.stdin.close()
        result = process.wait()
    if result or not count:
        raise RuntimeError(f"No complete movie written: {path}, {count}, ffmpeg {result}")
    actual = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v",
                 "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(temp)]))
    if actual != count:
        raise ValueError(f"Frame count mismatch {path}: {actual}, expected {count}")
    temp.replace(path)
    return count


def selection(name, pictures, changes):
    manifest = media.PRODUCTION / "selections" / (name + ".json")
    prior = json.loads(manifest.read_bytes())
    dest = media.ROOT / changes.get("file", prior["file"])
    frames = write_video(dest, pictures)
    prior.update(changes, sha256=media.hash_file(dest), frames=frames)
    media.write_json(manifest, prior)
    return dest


def talon():
    name = "c1_10_talon"
    approach = list(read_frames(source(name, 10)))
    uncover = list(read_frames(source(name, 11)))
    # Audited H3 source 0–8 has a feather across half the orb, 12 onward has a full circle.
    # The game plays these last 24 source frames at half-speed.
    expose = [0, 2, 4, 6, 8, 10, *range(12, 30)]
    dest = selection(name, [*approach[:72], *(uncover[i] for i in expose)], {
        "candidate": f"linyuan_{name}__v10", "source_sha256": media.hash_file(source(name, 10)),
        "first_source": 0, "end_exclusive": 72, "edit_speed": 1,
        "window_edit": {"candidate": f"linyuan_{name}__v11", "sha256": media.hash_file(source(name, 11)),
                        "frames": expose, "starts_at": 72, "fully_visible_from": 78},
        "editor_notes": "明亮的金属爪箍住右前臂中段，右手垂在爪外。半速窗前6源帧近翼扫过半个燃料囊，源78–95完全露芯。"
    })
    media.extract(name, "hover", dest, 84)


def response_jobs():
    jobs = json.loads(JOBS.read_bytes())
    first = json.loads((media.PRODUCTION / "anchors/c1_10_talon_hover.json").read_bytes())
    for index, outcome in enumerate(("hit", "miss")):
        name = "c1_11_" + outcome
        for variant in (10, 11):
            action = ("The round amber breast fuel chamber bursts with sharp sparks. Only then the raptor "
                      "opens its claws and drops the woman. The bird falls to the left beside the stove."
                      if outcome == "hit" else
                      "Her free natural left hand releases the post, grabs the hanging ladle, and swings it "
                      "up into the round amber fuel chamber. The short strike releases the talons, the "
                      "bird then tumbles left and the woman lands upright with an annoyed grimace.")
            jobs[f"linyuan_{name}__v{variant}"] = {
                "first": Path(first["anchor"]).stem, "last": "KF_C1_11_END", "length": 73,
                "prompt": "Locked camera. Start from the exact suspended pose: the bird's claw is gripping "
                "the woman's ceramic RIGHT FOREARM, the ceramic wrist and hand beyond the claw. Keep this "
                "physical contact visible until the release. " + action + " She lands on both feet; her "
                "left natural hand holds her intact right artificial forearm. The broken machine rests "
                "beside the stove with the fallen ladle on the ground. Match the shared final pose. "
                "Preserve right/left anatomy and stall layout throughout. No zoom or writing.",
                "prefix": "", "seed": 731200 + 20*index + variant,
            }
    media.write_json(JOBS, jobs)


def fixed_plate_frames(path, kill=False, matte_dir=None):
    """Stabilize the photographed action, then composite its matte onto one immutable landscape."""
    native = list(read_frames(path))
    h, w = native[0].shape[:2]
    plate = cv2.resize(cv2.imread(str(media.KEYS / "PL_BAMBOO.png")), (w, h), interpolation=cv2.INTER_AREA)
    orb = cv2.ORB_create(nfeatures=2800)
    template = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    keypoints, des = orb.detectAndCompute(template, None)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    transformed = []
    for raw in native:
        sample, raw_des = orb.detectAndCompute(cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY), None)
        correspondences = matcher.knnMatch(raw_des, des, k=2)
        good = [a for a, b in correspondences if a.distance < .72*b.distance]
        if len(good) < 15:
            raise ValueError("Insufficient landscape control points")
        current = np.float32([sample[m.queryIdx].pt for m in good])
        target = np.float32([keypoints[m.trainIdx].pt for m in good])
        matrix, inliers = cv2.estimateAffinePartial2D(current, target, method=cv2.RANSAC,
                                                     ransacReprojThreshold=1.8, maxIters=5000)
        if matrix is None or inliers.sum() < 15:
            raise ValueError("Tripod registration failed")
        transformed.append(cv2.warpAffine(raw, matrix, (w,h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))
    empty = transformed[-1] if kill else transformed[0]
    empty_float = empty.astype(np.float32)
    if matte_dir:
        matte_dir.mkdir(parents=True, exist_ok=True)
    for f, img in enumerate(transformed):
        if f == len(native)-1 or (f == 0 and not kill):
            yield plate.copy()
            continue
        diff = cv2.absdiff(img, empty)
        strength = diff.max(axis=2)
        strong = np.uint8(strength > 29)*255
        # Static distant objects and the shrine never enter the foreground matte.
        # The bounding envelope expands only when the rendered fox actually lunges past the lens.
        if kill:
            xmax, top, bottom = .82, .02, .99
        else:
            xmax = np.interp(f, [0,24,32,39,47,53,64,72], [.26,.28,.35,.47,.8,1,1,1])
            top = np.interp(f,[0,29,48,72],[.20,.20,0,0])
            bottom = np.interp(f,[0,25,43,72],[.85,.85,1,1])
        strong[:, int(xmax*w):] = 0
        strong[:int(top*h)] = 0
        strong[int(bottom*h):] = 0
        components = cv2.morphologyEx(strong, cv2.MORPH_CLOSE, np.ones((7,7),np.uint8))
        contours,_ = cv2.findContours(components, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros((h,w), np.uint8)
        for contour in contours:
            if cv2.contourArea(contour) > 55:
                cv2.drawContours(mask,[contour],-1,255,cv2.FILLED)
        if matte_dir:
            cv2.imwrite(str(matte_dir / f"{f:03}.png"), cv2.resize(mask,(1280,720),interpolation=cv2.INTER_NEAREST))
        mask = cv2.GaussianBlur(mask,(5,5),.85).astype(np.float32)/255
        # Carry the actual H3 scan flash as an additive light pass over the locked plate.
        out = plate.astype(np.float32)
        if not kill and f < 24:
            blue, green, red = cv2.split(img.astype(np.float32))
            cyan = np.clip((np.minimum(blue,green)-red-20)/65,0,1)
            scan = np.clip((strength.astype(np.float32)-20)/48,0,1)*cyan
            out += (img.astype(np.float32)-empty_float)*scan[...,None]
        out = out*(1-mask[...,None])+img.astype(np.float32)*mask[...,None]
        yield np.uint8(np.clip(out,0,255))


def grove():
    name = "c1_w_fox_grove"
    path = source(name,12)
    pictures = list(fixed_plate_frames(path, matte_dir=AUDIT/"grove_native_mattes"))
    # Remove only the repetitive first dwell on the scan. Keep the complete lunge and empty return.
    source_frames = [*range(0,20,2),*range(20,len(pictures))]
    dest = selection(name, (pictures[i] for i in source_frames), {
        "candidate": f"linyuan_{name}__v12", "source_sha256": media.hash_file(path),
        "first_source":0, "end_exclusive":len(pictures), "edit_speed":1,
        "scan_dissolve_frames":0, "source_frame_map":source_frames,
        "fixed_backplate":media.hash_file(media.KEYS/"PL_BAMBOO.png"),
        "editor_notes":"原机位左前竹丛入场。对H3渲染逐帧按石祠、溪石等固定地标配准，保留狐与青扫并合回同一张PL_BAMBOO。"
    })
    return dest


def anchor(name, label):
    entry = json.loads((media.PRODUCTION / "anchors" / f"{name}_{label}.json").read_bytes())
    return cv2.imread(str(media.ROOT / entry["anchor"]))


def finish_shots():
    for canonical, new in (("KF_C1_04", "KF_C1_04_EIGHT"), ("KF_C1_10", "KF_C1_10_FOREARM")):
        original = media.KEYS / (canonical + ".png")
        backup = BASE / original.name
        if not backup.exists():
            shutil.copy2(original, backup)
        shutil.copy2(media.KEYS / (new + ".png"), original)
    media.publish("c1_04_noodle", 11, 0, 120, 1,
                  "Eight separately countable sword hilts with guards and individual tassels on Lu Chen's casket.")
    for name, variant in (("c1_11_hit", 11), ("c1_11_miss", 10)):
        raw = source(name, variant)
        images = list(read_frames(raw))
        chosen = np.round(np.linspace(0,len(images)-1,72)).astype(int).tolist()
        edited = [images[i] for i in chosen]
        edited[0] = anchor("c1_10_talon","hover")
        edited[-1] = cv2.imread(str(media.KEYS / "KF_C1_11_END.png"))
        selection(name, edited, {"candidate":raw.parent.name, "source_sha256":media.hash_file(raw),
                  "first_source":0,"end_exclusive":len(images),"edit_speed":1,"source_frame_map":chosen,
                  "entry_anchor":{"source":"c1_10_talon","frame":84},
                  "end_anchor":"KF_C1_11_END","editor_notes":"Contact at the ceramic right forearm, then a shared landing."})
    plate = cv2.imread(str(media.KEYS/"PL_BAMBOO.png"))
    for label, stamp, variant, cleared in (("early",13,11,31),("mid",24,10,31),("late",36,11,35)):
        name = "c1_w_fox_grove_kill_" + label
        raw = source(name, variant)
        pictures = list(fixed_plate_frames(raw,kill=True))
        chosen = np.round(np.linspace(0,cleared,22)).astype(int).tolist()
        edited = [pictures[i] for i in chosen]
        edited[0] = anchor("c1_w_fox_grove",label)
        edited[-1] = plate
        ident = f"c1_w_fox_grove_kill_{stamp}"
        selection(name, edited, {"id":ident,"file":f"assets/linyuan/bamboo/{ident}.mp4","candidate":raw.parent.name,
                  "source_sha256":media.hash_file(raw),"first_source":0,"end_exclusive":cleared+1,
                  "edit_speed":round(cleared/21,4),"source_frame_map":chosen,"entry_anchor":{"source":"c1_w_fox_grove","frame":stamp},
                  "fixed_backplate":media.hash_file(media.KEYS/"PL_BAMBOO.png"),
                  "editor_notes":"Left-thicket retreat, registered to the immutable landscape. No live corpse or canister at cut."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["talon", "response-jobs", "grove","finish-shots"])
    args = parser.parse_args()
    if args.command == "talon":
        talon()
    elif args.command == "response-jobs":
        response_jobs()
    elif args.command == "grove":
        grove()
    elif args.command == "finish-shots":
        finish_shots()
