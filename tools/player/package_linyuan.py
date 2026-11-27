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


def collect_media(root, world, campaign_id):
    drama = json.loads((world / "drama.json").read_bytes())
    campaign = json.loads((world / f"{campaign_id}.json").read_bytes())
    folders = {"drama": set()}
    for chapter in campaign["chapters"]:
        for stage in chapter["stages"]:
            if stage["type"] == "film":
                for take in stage["takes"]:
                    folders["drama"].add(take["id"])
            elif stage["type"] == "trial":
                for step in stage["trial"]["steps"].values():
                    folders["drama"].add(step["take"])
                    for field in ("transition", "flinch_response", "kill_response"):
                        if step.get(field):
                            folders["drama"].add(step[field])
                    for iw in step.get("intercept_windows", ()):
                        folders["drama"].add(iw[2])
                    for outcome in step["outcomes"].values():
                        if outcome.get("response"):
                            folders["drama"].add(outcome["response"])
                        if outcome.get("transition"):
                            folders["drama"].add(outcome["transition"])
            elif stage["type"] == "encounter":
                lvl_id = stage["level"]
                lvl = json.loads((world / lvl_id / "level.json").read_bytes())
                folders.setdefault(lvl_id, set())
                folders[lvl_id].add(lvl["plate"]["media"])
                for clip in lvl["clips"].values():
                    folders[lvl_id].add(clip["media"])
    if not folders["drama"]:
        folders["drama"] = set(drama.keys())
    return folders


def package(root, runtime, output, campaign="chapter_one"):
    if campaign == "mvp":
        validate(root)
    else:
        from check_linyuan_ch1 import validate_ch1
        validate_ch1(root)
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
        for folder, films in collect_media(root, world, campaign).items():
            target = staging / "assets/linyuan" / folder
            target.mkdir(parents=True)
            for name in sorted(films):
                shutil.copy2(root / "assets/linyuan" / folder / (name + ".mp4"), target)
        title_bmp = root / "assets/linyuan/title.bmp"
        if title_bmp.is_file():
            shutil.copy2(title_bmp, staging / "assets/linyuan/title.bmp")
        shutil.copytree(root / "assets/linyuan/audio", staging / "assets/linyuan/audio")
        title = "临渊御剑 第一章：九曲渡" if campaign != "mvp" else "临渊御剑 MVP"
        controls = (
            "主菜单与标题界面可用鼠标点击或按 1/2/3 切换 简单 / 普通 / 困难 难度，也支持左下方关卡直达（F1/F2/F3）。\n"
            "战斗操作：左键出剑，右键或 R 收剑，空格或中键释放万剑归宗，Esc 暂停。"
            if campaign != "mvp"
            else "左键出剑，右键或 R 收剑，Esc 暂停。空格跳过纯剧情。"
        )
        (staging / "README.md").write_text(
            f"# {title}\n\n运行 Linyuan.exe。{controls}\n\n"
            "白甲和落空会消耗飞剑，直击琥珀弱点会让这柄飞剑自动返回。"
            "剑匣未空也可收剑，召回的剑越少，归匣越快。\n\n"
            "开发回放可用 Linyuan.exe --smoke <新目录> --scenario normal。"
            "真人试玩直接运行程序。\n",
            encoding="utf8")
        if campaign == "mvp":
            validate(staging)
        else:
            validate_ch1(staging)
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
    parser.add_argument("--campaign", default="chapter_one")
    args = parser.parse_args()
    print(package(args.root, args.runtime, args.output, args.campaign))
