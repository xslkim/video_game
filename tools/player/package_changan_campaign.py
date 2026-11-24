"""Assemble an offline campaign using only its referenced chapters, movies and masks."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from check_changan import validate_graph, verify_media


def read(path):
    return json.loads(path.read_bytes())


def safe(value):
    if not re.fullmatch(r"[a-z0-9_]+", value):
        raise ValueError(f"Invalid game asset identifier: {value}")
    return value


def copy(root, target, relative):
    dest = target / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / relative, dest)


def collect(story):
    levels, films, tracked, stages = set(), set(), set(), set()
    for chapter in story["chapters"]:
        for stage in chapter["stages"]:
            sid = safe(stage["id"])
            if sid in stages:
                raise ValueError(f"Duplicate stage {sid}")
            stages.add(sid)
            if stage["type"] == "encounter":
                levels.add(safe(stage["level"]))
            elif stage["type"] == "film":
                films.update(safe(f["id"]) for f in stage["takes"])
            elif stage["type"] == "trial":
                trial = stage["trial"]
                steps = trial["steps"]
                reached = set()
                todo = [trial["first"]]
                graph = {}
                while todo:
                    key = todo.pop()
                    if key in reached or key == "@complete":
                        continue
                    step = steps[key]
                    reached.add(key)
                    take = safe(step["take"])
                    tracked.add(take)
                    films.add(take)
                    outcomes = step["outcomes"]
                    if (
                        set(outcomes) != set(step["zones"]) | {"miss", "timeout"}
                        or step["answer"] not in step["zones"]
                    ):
                        raise ValueError(f"Incomplete trial choices at {sid}/{key}")
                    graph[key] = {outcome["next"] for outcome in outcomes.values()}
                    todo.extend(graph[key])
                    films.update(safe(o["response"]) for o in outcomes.values() if "response" in o)
                ends = {"@complete"}
                while new := {k for k in graph if k not in ends and ends & graph[k]}:
                    ends.update(new)
                if reached != set(steps) or not reached.issubset(ends):
                    raise ValueError(f"Incomplete trial graph at {sid}")
            else:
                raise ValueError(stage["type"])
    return levels, films, tracked


def validate_trials(root, story, index):
    """Check every enabled reaction window against the geometry actually shipped."""
    from functools import lru_cache

    @lru_cache(maxsize=16)
    def poses(take):
        packed = read(root / "worlds/changan/regions" / (take + ".json"))
        if packed["sha256"] != index[take]["sha256"]:
            raise ValueError("Tracking belongs to another film: " + take)
        return packed["regions"]

    for chapter in story["chapters"]:
        for stage in chapter["stages"]:
            for key, step in stage.get("trial", {}).get("steps", {}).items():
                take = step["take"]
                context = f"{stage['id']}/{key}/{take}"
                total = index[take]["frames"]
                start, length = step["window"]
                if not 0 <= start < total - 1 or length <= 0:
                    raise ValueError("Invalid window " + context)
                has_story = step.get("story_shot", False)
                strength = step.get("strength", 1)
                if not 1 <= strength <= 6 or has_story and strength != 1:
                    raise ValueError("Invalid target strength " + context)
                for role in step["zones"]:
                    track = poses(take).get(role, [])
                    if len(track) != total or any(
                        p["frame"] != i or len(p["polygon"]) < 3 or len(p["polygon"]) != len(track[0]["polygon"])
                        for i, p in enumerate(track)
                    ):
                        raise ValueError("Incomplete tracking " + context + "/" + role)
                    low, high = step.get("zone_windows", {}).get(role, [0, total])
                    if not 0 <= low < high <= total:
                        raise ValueError("Invalid visibility interval " + context + "/" + role)
                for warn, flight, story_len in [(1.4, 1.3, 72), (1, 1, 48), (0.65, 0.7, 29)]:
                    mult = flight if step.get("projectile") else warn
                    end = start + (
                        story_len if has_story else min(total - start - 1, int(length * mult + 0.5))
                    )
                    if end >= total:
                        raise ValueError("Window extends beyond film " + context)
                    zone = step["answer"]
                    low, high = step.get("zone_windows", {}).get(zone, [0, total])
                    active = range(max(start, low), min(end, high))
                    if len(active) < 1 + (strength - 1) * 4:
                        raise ValueError("Insufficient time for required hits " + context)
                    for f in active:
                        polygon = poses(take)[zone][f]["polygon"]
                        x = sum(p[0] for p in polygon) / len(polygon)
                        y = sum(p[1] for p in polygon) / len(polygon)
                        area = abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2
                        if area < 4:
                            raise ValueError(f"Degenerate target {context} at frame {f}")
                        if not 0 <= x < 1280 or not 0 <= y < 720:
                            raise ValueError(f"Target off screen {context} at frame {f}")


def assemble(root, name, binaries, out):
    world = Path("worlds/changan")
    assets = Path("assets/changan")
    manifest = world / (safe(name) + ".json")
    story = read(root / manifest)
    levels, films, tracked = collect(story)
    out.mkdir(parents=True, exist_ok=False)
    for path in [binaries / "Changan.exe", *sorted(binaries.glob("*.dll"))]:
        shutil.copy2(path, out / path.name)
    shutil.copytree(binaries / "licenses", out / "licenses")
    copy(root, out, manifest)
    if (root / assets / "title.bmp").exists():
        copy(root, out, assets / "title.bmp")
    for level in levels:
        folder = world / level
        declaration = read(root / folder / "level.json")
        validate_graph(declaration)
        verify_media(declaration, root / folder, root / assets / level)
        copy(root, out, folder / "level.json")
        for logical, clip in declaration["clips"].items():
            if clip.get("windows"):
                copy(root, out, folder / (logical + ".mask"))
        bank = assets / level
        if "street" in declaration:
            bank /= "once"
            copy(root, out, bank / "street.mp4")
        ext = ".mkv" if "street" in declaration else ".mp4"
        for take in {c.get("media", k) for k, c in declaration["clips"].items()}:
            copy(root, out, bank / (safe(take) + ext))
    index = read(root / world / "drama.json")
    validate_trials(root, story, index)
    subset = {}
    for take in sorted(films):
        movie = assets / "drama" / (take + ".mp4")
        sha = hashlib.file_digest((root / movie).open("rb"), "sha256").hexdigest()
        if sha != index[take]["sha256"]:
            raise ValueError(f"Changed film: {take}")
        copy(root, out, movie)
        subset[take] = index[take]
    for take in sorted(tracked):
        region = world / "regions" / (take + ".json")
        if read(root / region)["sha256"] != subset[take]["sha256"]:
            raise ValueError(f"Changed trial geometry: {take}")
        copy(root, out, region)
    for relative in [world / "start.json", world / "drama.json"]:
        data = {"campaign": name} if relative.name == "start.json" else subset
        (out / relative).write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    shutil.copytree(root / assets / "audio/foley", out / assets / "audio/foley")
    music = {"festival"}
    voices = set()
    for chapter in story["chapters"]:
        for stage in chapter["stages"]:
            if stage.get("music"):
                music.add(safe(stage["music"]))
            for shot in [*stage.get("takes", []), *stage.get("trial", {}).get("steps", {}).values()]:
                if shot.get("voice"):
                    actor, line = shot["voice"].split("/")
                    voices.add(assets / "audio/voice" / safe(actor) / (safe(line) + ".wav"))
    if name == "campaign":
        music.add("title")
    for file in sorted(voices | {assets / "audio/music" / (key + ".wav") for key in music}):
        copy(root, out, file)
    doc = root / "docs" / ("PLAY_CHANGAN_" + name.upper() + ".md")
    shutil.copy2(doc, out / "README.md")
    dest = out.with_name(out.name + "-Windows-x64.zip")
    with ZipFile(dest, "x", ZIP_DEFLATED, compresslevel=1) as archive:
        for file in sorted(out.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(out))
    with ZipFile(dest) as archive:
        if bad := archive.testzip():
            raise ValueError(f"Damaged release member: {bad}")
    return dest


def package(root, name, binaries, out):
    archive = out.with_name(out.name + "-Windows-x64.zip")
    if out.exists() or archive.exists():
        raise FileExistsError(f"Choose a new release path: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="." + out.name + "-", dir=out.parent) as temporary:
        staged = Path(temporary) / out.name
        compressed = assemble(root, name, binaries, staged)
        staged.rename(out)
        try:
            compressed.rename(archive)
        except OSError:
            out.rename(staged)
            raise
    with archive.open("rb") as stream:
        print(archive, hashlib.file_digest(stream, "sha256").hexdigest())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("campaign")
    ap.add_argument("binaries", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    package(Path(__file__).resolve().parents[2], args.campaign, args.binaries, args.output)
