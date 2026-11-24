"""Mux actual SDL frames and every postmix stream from a campaign recording."""

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    data = json.loads((root / "recording.json").read_bytes())
    rows = [line.split() for line in (root / "frames.tsv").read_text().splitlines()]
    if len(rows) != data["frames"] or not rows:
        raise ValueError("Incomplete video capture")
    lines = ["ffconcat version 1.0"]
    for i, (name, stamp) in enumerate(rows):
        begin = float(stamp) if i else 0.0
        end = float(rows[i + 1][1]) if i + 1 < len(rows) else data["seconds"]
        if end <= begin:
            raise ValueError("Out of order presentation")
        lines.extend([f"file 'frames/{int(name)}.bmp'", f"duration {end - begin:.8f}"])
    lines.append(f"file 'frames/{int(rows[-1][0])}.bmp'")
    listing = root / "capture.ffconcat"
    listing.write_text("\n".join(lines) + "\n", encoding="utf8")
    streams = sorted((root / "audio").glob("*/postmix.json"))
    if len(streams) != data["streams"]:
        raise ValueError("Missing recorded audio device")
    master = root / "mixed-stereo.f32"
    rate = 48000
    mixed = np.memmap(master, dtype="<f4", mode="w+", shape=(int(np.ceil(data["seconds"] * rate)), 2))
    mixed[:] = 0
    for file in streams:
        info = json.loads(file.read_bytes())
        raw = file.with_name("postmix.f32")
        if info["sample_rate"] != rate or info["channels"] != 2:
            raise ValueError(f"Unexpected audio format in {file}")
        chunk = np.memmap(raw, dtype="<f4", mode="r").reshape(-1, 2)
        if len(chunk) != info["samples"]:
            raise ValueError(f"Incomplete audio in {raw}")
        begin = round(info["start_time"] * rate)
        first = max(0, -begin)
        count = min(len(chunk) - first, len(mixed) - max(0, begin))
        if count > 0:
            mixed[max(0, begin) : max(0, begin) + count] += chunk[first : first + count]
    if not np.isfinite(mixed).all() or np.abs(mixed).max() < 0.001:
        raise ValueError("Invalid gameplay audio")
    np.clip(mixed, -1, 1, out=mixed)
    mixed.flush()
    del mixed
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".part.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-safe",
            "0",
            "-f",
            "concat",
            "-i",
            str(listing),
            "-f",
            "f32le",
            "-ar",
            str(rate),
            "-ac",
            "2",
            "-i",
            str(master),
            "-vf",
            "fps=24",
            "-c:v",
            "libx264",
            "-crf",
            "19",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-t",
            str(data["seconds"]),
            "-movflags",
            "+faststart",
            str(tmp),
        ],
        check=True,
    )
    tmp.replace(output)
    print(f"{len(rows)} presentations, {len(streams)} audio streams, {data['seconds']:.2f}s")


if __name__ == "__main__":
    main()
