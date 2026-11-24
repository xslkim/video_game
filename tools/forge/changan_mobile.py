"""Transcode the campaign to hardware-decodable video and package shared runtime data."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/player"))
from package_changan_campaign import collect
from changan_mobile_frames import atlas


def read(path):
    return json.loads(path.read_bytes())


def run(args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def transcode(job):
    source, dest, kind = job
    if dest.is_file():
        return
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    if kind == "audio":
        run(["-i", source, "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "128k", tmp])
    else:
        args = ["-i", source, "-vf", "scale=960:540:flags=lanczos,setsar=1"]
        run(
            args
            + [
                "-threads",
                "3",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "19",
                "-profile:v",
                "main",
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
                tmp,
            ]
        )
    tmp.replace(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--campaign", default="campaign")
    args = ap.parse_args()
    out = args.output
    (out / "media").mkdir(parents=True, exist_ok=True)
    world = ROOT / "worlds/changan"
    assets = ROOT / "assets/changan"
    campaign = read(world / (args.campaign + ".json"))
    banks, films, tracked = collect(campaign)
    jobs = {}

    def asset(path, kind):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()[:24]
        rel = "media/" + kind + "-" + digest + (".m4a" if kind == "audio" else ".mp4")
        jobs[rel] = (path, out / rel, kind)
        return rel

    bundle = {"campaign": campaign, "banks": {}, "films": {}, "regions": {}, "audio": {}, "legacyFilms": {}}
    for bank in sorted(banks):
        declaration = read(world / bank / "level.json")
        media = {}
        for key, clip in declaration["clips"].items():
            name = clip.get("media", key)
            if name not in media:
                media[name] = atlas(assets / bank / "once" / (name + ".mkv"), out / "media", True)
                media[name]["audio"] = asset(assets / bank / "once" / (name + ".mkv"), "audio")
            if media[name]["frames"] != clip["frames"]:
                raise ValueError(f"Frame count changed in the mobile take: {bank}/{key}")
            if clip.get("windows"):
                path = Path("masks") / bank / (key + ".mask")
                (out / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(world / bank / path.name, out / path)
        bundle["banks"][bank] = {
            "level": declaration,
            "layers": media,
            "street": atlas(assets / bank / "once/street.mp4", out / "media", False),
        }
    def film_frames(take):
        return take, atlas(assets / "drama" / (take + ".mp4"), out / "media", False, 24 if take in tracked else 12)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for take, frames in pool.map(film_frames, sorted(films)):
            movie = assets / "drama" / (take + ".mp4")
            bundle["films"][take] = asset(movie, "video")
            frames["audio"] = asset(movie, "audio")
            bundle["legacyFilms"][take] = frames
    for take in sorted(tracked):
        path = Path("regions") / (take + ".json")
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(world / path, out / path)
        bundle["regions"][take] = path.as_posix()
    for file in sorted((assets / "audio").rglob("*.wav")):
        key = file.relative_to(assets / "audio").with_suffix("").as_posix()
        bundle["audio"][key] = asset(file, "audio")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(transcode, jobs.values()))
    # Keep the published bundle readable while its replacement is encoding.
    (out / "bundle.tmp").write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf8"
    )
    (out / "bundle.tmp").replace(out / "bundle.json")
    run(
        [
            "-i",
            assets / "drama/city.mp4",
            "-frames:v",
            "1",
            "-vf",
            "scale=960:540",
            "-q:v",
            "3",
            out / "poster.jpg",
        ]
    )
    print(f"{len(jobs)} unique media files and {len(tracked)} tracked performances")


if __name__ == "__main__":
    main()
