"""Retarget a single speaker inside a two-shot without changing the other actor."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from changan_drama import index_media


TAKES = {
    "epilogue": ("shenyan/epilogue", (0, 0, 640, 600)),
    "wife": ("xuanzhu/promise", (0, 0, 576, 560)),
    "peizhao_rest": ("peizhao/rest", (480, 70, 650, 610)),
    "aying_lends": ("aying/lend", (260, 0, 700, 650)),
    "west_prophecy": ("xuanzhu/return", (0, 0, 610, 576)),
}


def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *map(str, args)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("model", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assets = root / "assets/changan"
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    failures = {}
    for take, (line, (x, y, w, h)) in TAKES.items():
        dest = assets / "drama" / (take + "_speaking.mp4")
        if dest.exists():
            continue
        folder = args.work / take
        folder.mkdir(parents=True, exist_ok=True)
        source = assets / "drama" / (take + ".mp4")
        clip = folder / "speaker.mp4"
        voiced = folder / "performance.mp4"
        try:
            ff("-i", source, "-vf", f"crop={w}:{h}:{x}:{y},fps=25", "-an", "-crf", 15, clip)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.inference",
                    "--unet_config_path",
                    "configs/unet/stage2_512.yaml",
                    "--inference_ckpt_path",
                    "checkpoints/latentsync_unet.pt",
                    "--inference_steps",
                    "20",
                    "--guidance_scale",
                    "1.5",
                    "--video_path",
                    str(clip),
                    "--audio_path",
                    str(assets / "audio/voice" / (line + ".wav")),
                    "--video_out_path",
                    str(voiced),
                    "--temp_dir",
                    str(folder / "temp"),
                    "--seed",
                    "25817",
                ],
                cwd=args.model,
                check=True,
            )
            full = folder / "full.mp4"
            ff(
                "-i",
                source,
                "-i",
                voiced,
                "-filter_complex",
                f"[1:v]scale={w}:{h},setsar=1,fps=24[v];[0:v][v]overlay={x}:{y}:eof_action=pass",
                "-map",
                "0:a",
                "-c:a",
                "copy",
                "-c:v",
                "libx264",
                "-crf",
                "17",
                "-bf",
                "0",
                "-g",
                "24",
                "-movflags",
                "+faststart",
                full,
            )
            import shutil

            tmp = dest.with_suffix(".part.mp4")
            shutil.copy2(full, tmp)
            tmp.replace(dest)
        except (OSError, subprocess.CalledProcessError) as e:
            failures[take] = str(e)
    (args.work / "failures.json").write_text(json.dumps(failures, indent=2), encoding="utf8")
    index_media(assets / "drama", root / "worlds/changan/drama.json")
    if failures:
        raise RuntimeError(failures)


if __name__ == "__main__":
    main()
