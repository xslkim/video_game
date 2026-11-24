"""Light the nine practical heads in the filmed encounter, using final-frame tracks."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np


ORDER = [1, 5, 9, 4, 7, 2, 6, 3, 8]


def light_heads(frame, tracks, number, selected):
    for head in range(1, 10):
        poly = np.array(tracks["head_" + str(head)][number]["polygon"], dtype=np.float32)
        center = poly.mean(axis=0)
        # Include the paper cheeks and horns around the physical wick.
        radii = np.maximum(8, (poly.max(axis=0) - poly.min(axis=0)) * 0.95)
        x, y = center
        x0, y0 = np.maximum(0, np.floor(center - radii * 2)).astype(int)
        x1, y1 = np.minimum([frame.shape[1], frame.shape[0]], np.ceil(center + radii * 2)).astype(int)
        tile = frame[y0:y1, x0:x1].astype(np.float32) / 255
        yy, xx = np.ogrid[y0:y1, x0:x1]
        dist = ((xx - x) / radii[0]) ** 2 + ((yy - y) / radii[1]) ** 2
        light = np.exp(-2 * dist).astype(np.float32)[:, :, None]
        warm = np.clip((tile[:, :, 2] - tile[:, :, 0]) * 4, 0, 1)[:, :, None]
        if head == selected:
            intensity = np.clip((number - 10) / 10, 0, 1) * (0.94 + 0.06 * np.cos(number * 0.16))
            tile = (
                tile * (1 + 0.5 * light * warm * intensity)
                + (1 - tile) * light * np.array([0.22, 0.75, 0.98]) * intensity
            )
        else:
            tile *= 1 - 0.71 * light * warm
        frame[y0:y1, x0:x1] = np.uint8(np.clip(tile, 0, 1) * 255 + 0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    world = args.root / "worlds/changan/regions"
    media = args.root / "assets/changan/drama"
    for i, head in enumerate(ORDER):
        source = "dragon" if i % 4 == 0 else "dragon_pass_" + str(i % 4)
        region = json.loads((world / (source + ".json")).read_bytes())
        dest = "dragon_signal_" + str(i + 1)
        name = media / (dest + ".mp4")
        sheet = world / (dest + ".json")
        recipe = f"practical-lamp-v1/{region['sha256']}/{head}"
        if name.exists() and sheet.exists() and json.loads(sheet.read_bytes()).get("recipe") == recipe:
            continue
        original = media / (source + ".mp4")
        cap = cv2.VideoCapture(str(original))
        temp = name.with_suffix(".part.mp4")
        command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-s",
            "1280x720",
            "-pix_fmt",
            "bgr24",
            "-r",
            "24",
            "-i",
            "pipe:0",
            "-i",
            str(original),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-threads",
            "3",
            "-preset",
            "veryfast",
            "-crf",
            "17",
            "-bf",
            "0",
            "-g",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(temp),
        ]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
            try:
                for number in range(len(region["regions"]["head_1"])):
                    ok, frame = cap.read()
                    if not ok:
                        raise ValueError(f"Missing {source} frame {number}")
                    light_heads(frame, region["regions"], number, head)
                    proc.stdin.write(memoryview(frame))
            finally:
                proc.stdin.close()
                cap.release()
            if proc.wait():
                raise RuntimeError(source)
        temp.replace(name)
        with name.open("rb") as stream:
            region["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        region["recipe"] = recipe
        sheet.write_text(json.dumps(region, separators=(",", ":")) + "\n", encoding="utf8")
        print(dest, source, head, flush=True)


if __name__ == "__main__":
    main()
