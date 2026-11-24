"""Run authored drama takes on the local H3 worker and conform selected takes for the player."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image, ImageOps

from changan_h3 import COMFY, generate, request


def render(work, root, only=None, reuse=False):
    camera = work / "anchors"
    camera.mkdir(parents=True, exist_ok=True)
    out = root / "assets/changan/drama"
    out.mkdir(parents=True, exist_ok=True)
    specs = json.loads((root / "worlds/changan/production/drama_jobs.json").read_bytes())
    for extra in sorted((root / "worlds/changan/production").glob("drama_*_jobs.json")):
        for key, spec in json.loads(extra.read_bytes()).items():
            if key in specs:
                raise ValueError(f"Duplicate H3 take: {key}")
            specs[key] = spec
    for name, spec in specs.items():
        if only and name not in only:
            continue
        if spec.get("selected") is False:
            continue
        source = root / "assets/changan/story-anchors" / (spec["first"] + ".png")
        if "from_take" in spec:
            previous, frame = spec["from_take"]
            raw = work / "takes" / previous / "source.mp4"
            if not raw.exists():
                print("No source performance yet:", name, flush=True)
                continue
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(raw),
                    "-vf",
                    f"select=eq(n\\,{frame})",
                    "-frames:v",
                    "1",
                    str(camera / source.name),
                ],
                check=True,
            )
            source = camera / source.name
        if not source.exists():
            print("No anchor yet:", name, flush=True)
            continue
        anchor = camera / source.name
        if source != anchor:
            with Image.open(source) as image:
                ImageOps.fit(image.convert("RGB"), (1024, 576), method=Image.Resampling.LANCZOS).save(
                    anchor
                )
        dest = out / (name + ".mp4")
        meta = work / "takes" / name / "conform.json"
        aperture = spec.get("aperture")
        cleanup = spec.get("cleanup_rect")
        speed = spec.get("speed", 1)
        if dest.exists() and meta.exists():
            prior = json.loads(meta.read_bytes())
            if (
                prior.get("aperture") == aperture
                and prior.get("cleanup_rect") == cleanup
                and prior.get("speed", 1) == speed
            ):
                continue
        raw = work / "takes" / name / "source.mp4"
        if reuse:
            if not raw.is_file():
                raise FileNotFoundError(raw)
        else:
            generate(name, spec, camera, work)
        tmp = dest.with_suffix(".part.mp4")
        filters = ["scale=1280:720:flags=lanczos", "setsar=1"]
        if aperture:
            filters.insert(0, "crop=" + ":".join(str(v) for v in aperture))
        if cleanup:
            filters.insert(0, "delogo=" + ":".join(str(v) for v in cleanup))
        if speed != 1:
            filters.extend([f"setpts=PTS/{speed}", "fps=24"])
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(raw),
                "-vf",
                ",".join(filters),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-bf",
                "0",
                "-crf",
                "17",
                "-g",
                "24",
                "-pix_fmt",
                "yuv420p",
                "-af",
                f"atempo={speed}",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(tmp),
            ],
            check=True,
        )
        tmp.replace(dest)
        meta.write_text(
            json.dumps(
                {
                    "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                    "anchor_sha256": hashlib.sha256(anchor.read_bytes()).hexdigest(),
                    "take": name,
                    "aperture": aperture,
                    "cleanup_rect": cleanup,
                    "speed": speed,
                },
                indent=2,
            ),
            encoding="utf8",
        )
    if not only:
        index_media(out, root / "worlds/changan/drama.json")


def index_media(directory, destination):
    records = {}
    for path in sorted(directory.glob("*.mp4")):
        if path.name.endswith(".part.mp4"):
            continue
        args = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,has_b_frames,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
        stream = json.loads(subprocess.check_output(args))["streams"][0]
        if (stream["width"], stream["height"], stream["has_b_frames"], stream["r_frame_rate"]) != (
            1280,
            720,
            0,
            "24/1",
        ):
            raise ValueError(f"Unplayable drama movie: {path}")
        records[path.stem] = {
            "frames": int(stream["nb_frames"]),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    with tempfile.NamedTemporaryFile("w", encoding="utf8", dir=destination.parent, delete=False) as staged:
        json.dump(records, staged, indent=2)
        staged.write("\n")
    Path(staged.name).replace(destination)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("work", type=Path)
    ap.add_argument(
        "--conform",
        nargs="+",
        metavar="TAKE",
        help="Reframe recorded sources without using the video model",
    )
    ap.add_argument("--index-only", action="store_true")
    ap.add_argument(
        "--shoot", nargs="+", metavar="TAKE", help="Generate only these authored H3 performances"
    )
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.index_only:
        root = Path(__file__).resolve().parents[2]
        index_media(root / "assets/changan/drama", root / "worlds/changan/drama.json")
        return
    if args.conform:
        render(args.work, Path(__file__).resolve().parents[2], args.conform, reuse=True)
        return
    with (args.work / "comfy.log").open("a") as log:
        process = subprocess.Popen(
            [str(COMFY / ".venv/bin/python"), "main.py", "--listen", "127.0.0.1", "--port", "8194"],
            cwd=COMFY,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("H3 worker exited during startup")
                try:
                    request("/system_stats")
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError("H3 worker did not start")
            render(args.work, Path(__file__).resolve().parents[2], args.shoot)
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
