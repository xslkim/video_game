"""Verify the playable level against its final media and frame-local annotations."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


def require(test, message):
    if not test:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_mask(path, node):
    data = path.read_bytes()
    count = node["frames"]
    require(data[:4] == b"DCM1" and data[4:36].hex() == node["sha256"],
            f"{path.name}: invalid mask header or stale movie hash")
    require(struct.unpack_from("<H", data, 36)[0] == count, f"{path.name}: frame count")
    empty = []
    offset = 38
    for f in range(count):
        runs, = struct.unpack_from("<H", data, offset)
        offset += 2
        end = offset + runs * 6
        require(end <= len(data), f"{path.name}: truncated frame {f}")
        last_row, last_end = -1, 0
        for y, left, right in struct.iter_unpack("<HHH", data[offset:end]):
            require(y < 360 and left < right <= 640 and
                    (y > last_row or y == last_row and left >= last_end),
                    f"{path.name}: invalid span, frame {f}")
            last_row, last_end = y, right
        offset = end
        if runs == 0:
            empty.append(f)
    require(offset == len(data), f"{path.name}: trailing bytes")
    if node.get("civilian"):
        require(0 < len(empty) < count, f"{path.name}: civilian never appears or never leaves")
    else:
        require(all(f < node["opens"] or f >= node.get("expires", count) for f in empty),
                f"{path.name}: empty interactive frame")


def check_graph(level):
    nodes = level["clips"]
    require(level["version"] == 1 and level["size"] == [1280, 720] and level["fps"] == 24,
            "Unsupported timeline format")
    require(set(level["checkpoints"].values()) <= nodes.keys(), "Missing checkpoint")
    require(nodes["A4_change_doors"]["next"] == "@complete" and
            "beat" not in nodes["A4_change_doors"], "Interactive endpoint")
    visited = set()
    pending = ["A0_mayor_arrives"]
    while pending:
        name = pending.pop()
        if name in visited or name in ("@complete", "@failed"):
            continue
        require(name in nodes, f"Undefined destination: {name}")
        visited.add(name)
        node = nodes[name]
        require(0 <= node.get("start", 0) < node["frames"], f"{name}: invalid start")
        pending.append(node["next"])
        if "beat" in node:
            require(0 <= node["opens"] < node.get("expires", node["frames"]) <= node["frames"],
                    f"{name}: invalid window")
            pending.append(node["success"])
        if "expires" in node or node.get("civilian"):
            pending.append("D01_badge")
        if node.get("beat") == "porch":
            pending.append("A4_scare")
    require(visited == nodes.keys(), f"Unreachable clips: {nodes.keys() - visited}")


def verify(root):
    base = root / "assets/western"
    directory = root / "worlds/western/opening"
    manifest = read_json(base / "opening_slices/manifest.json")
    level = read_json(directory / "level.json")
    check_graph(level)
    require(len(manifest["clips"]) == 26 and level["clips"].keys() == manifest["clips"].keys(),
            "Expected the 26 selected clips")
    for name, node in level["clips"].items():
        selected = manifest["clips"][name]
        media = base / "opening_slices" / selected["file"]
        require(media.is_file(), f"Missing {media}")
        require(node["sha256"] == hashlib.sha256(media.read_bytes()).hexdigest() == selected["sha256"],
                f"{name}: media hash mismatch")
        require(node["frames"] == selected["frames"], f"{name}: frame count mismatch")
        if node.get("civilian") or node.get("beat") not in (None, "porch"):
            check_mask(directory / (name + ".mask"), node)
    require(len(manifest["input_sha256"]) == 15, "Expected 15 frame anchors")
    for name, sha in manifest["input_sha256"].items():
        require(hashlib.sha256((base / "kf" / name).read_bytes()).hexdigest() == sha,
                f"{name}: anchor mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    try:
        verify(parser.parse_args().root)
    except (OSError, ValueError, KeyError, struct.error) as error:
        sys.exit(str(error))
    print("OK: 26 reachable clips, 15 anchors, frame windows, mask spans and SHA-256")
