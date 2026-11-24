"""Edit the market encounters so the fox makes her first appearance after Aying joins."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil


def assemble(root):
    world = root / "worlds/changan"
    media = root / "assets/changan"
    target = world / "tutorial"
    target.mkdir(exist_ok=True)
    bank = media / "tutorial/once"
    bank.mkdir(parents=True, exist_ok=True)
    base = json.loads((world / "a1/level.json").read_bytes())
    template = base["clips"]
    nodes = base["nodes"][:9]
    clips = {k: deepcopy(v) for k, v in template.items() if k.startswith(("wave_", "seller_"))}
    masks = {k: k for k, v in clips.items() if v.get("windows")}
    next_key = "@complete"
    for index, model in reversed(list(enumerate([4, 3, 0], 9))):
        original = base["nodes"][model]
        old = original["id"]
        key = f"wave_{index + 1:02d}_" + old.split("_", 2)[2]
        node = {**original, "id": key}
        nodes.insert(9, node)
        threat = deepcopy(template[old])
        threat["next"] = key
        for window in threat["windows"]:
            outcome = deepcopy(template[window["hit"]])
            outcome["next"] = next_key
            window["hit"] = window["hit"].replace(old, key)
            window["node"] = index
            clips[window["hit"]] = outcome
        clips[key] = threat
        masks[key] = old
        next_key = key
    for clip in clips.values():
        if clip["next"] == "lantern":
            clip["next"] = next_key
    for dest, source in masks.items():
        shutil.copyfile(world / "a1" / (source + ".mask"), target / (dest + ".mask"))
    files = {"street.mp4"} | {x["media"] + ".mkv" for x in clips.values()}
    for file in files:
        src, dst = media / "a1/once" / file, bank / file
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    base.update(nodes=nodes, clips=clips)
    (target / "level.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )


if __name__ == "__main__":
    assemble(Path(__file__).resolve().parents[2])
