"""Create a checked, relocatable Linyuan MVP package and ZIP."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import wave
import zipfile

from check_linyuan import validate

ROOT = Path(__file__).resolve().parents[2]

SOUNDS = (
    "shot", "hit_ceramic", "hit_wing", "canister", "kill", "miss_water",
    "miss_stone", "miss_earth", "miss_bamboo", "intercept", "hurt_claw",
    "hurt_impact", "hurt_blast", "civilian", "reload", "empty", "reveal", "warning",
)


def validate_soundbank(root):
    folder = root / "assets/linyuan/audio/foley"
    for name in SOUNDS:
        for suffix in ("", "_2", "_3"):
            file = folder / (name + suffix + ".wav")
            if not file.is_file():
                raise ValueError(f"Missing release sound: {file}")
    for file in folder.glob("*.wav"):
        with wave.open(str(file)) as sound:
            if (sound.getnframes() == 0 or sound.getsampwidth() != 2
                    or sound.getframerate() != 48000 or sound.getnchannels() != 2):
                raise ValueError(f"Invalid release sound: {file}")
            if len(sound.readframes(sound.getnframes())) != sound.getnframes() * 4:
                raise ValueError(f"Truncated release sound: {file}")


def package(root, runtime, output):
    validate(root)
    validate_soundbank(root)
    if output.exists() or output.with_name(output.name + "-Windows-x64.zip").exists():
        raise FileExistsError(f"Choose a new release directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="linyuan-package-", dir=output.parent) as temporary:
        staging = Path(temporary) / output.name
        staging.mkdir()
        for file in runtime.iterdir():
            if file.suffix.lower() in {".dll", ".exe"} and (
                    file.suffix.lower() == ".dll" or file.name == "Linyuan.exe"):
                shutil.copy2(file, staging / file.name)
        if not (staging / "Linyuan.exe").is_file():
            raise ValueError(f"Linyuan.exe missing from {runtime}")
        if (runtime / "licenses").is_dir():
            shutil.copytree(runtime / "licenses", staging / "licenses")
        shutil.copytree(root / "worlds/linyuan", staging / "worlds/linyuan",
                        ignore=shutil.ignore_patterns("production"))
        world = root / "worlds/linyuan"
        drama = json.loads((world / "drama.json").read_bytes())
        bamboo = json.loads((world / "bamboo/level.json").read_bytes())
        bamboo_films = {clip["media"] for clip in [bamboo["plate"], *bamboo["clips"].values()]}
        for folder, films in (("drama", drama), ("bamboo", bamboo_films)):
            target = staging / "assets/linyuan" / folder
            target.mkdir(parents=True)
            for name in sorted(films):
                shutil.copy2(root / "assets/linyuan" / folder / (name + ".mp4"), target)
        shutil.copytree(root / "assets/linyuan/audio", staging / "assets/linyuan/audio")
        (staging / "README.md").write_text(
            "# 临渊御剑 MVP\n\n运行 Linyuan.exe。左键出剑，右键或 R 收剑，Esc 暂停。"
            "空格跳过纯剧情。\n\n"
            "白甲和落空会消耗飞剑，直击琥珀弱点会让这柄飞剑自动返回。"
            "剑匣未空也可收剑，召回的剑越少，归匣越快。\n\n"
            "开发回放可用 Linyuan.exe --smoke <新目录> --scenario normal。"
            "真人试玩直接运行程序。\n",
            encoding="utf8")
        validate(staging)
        validate_soundbank(staging)
        manifest = {}
        for file in sorted(staging.rglob("*")):
            if file.is_file():
                manifest[file.relative_to(staging).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
        staging.replace(output)
    archive = output.with_name(output.name + "-Windows-x64.zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as zipped:
        for file in sorted(output.rglob("*")):
            if file.is_file():
                zipped.write(file, Path(output.name) / file.relative_to(output))
    with zipfile.ZipFile(archive) as zipped:
        if bad := zipped.testzip():
            raise ValueError(f"Corrupt ZIP member: {bad}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(package(args.root, args.runtime, args.output))
