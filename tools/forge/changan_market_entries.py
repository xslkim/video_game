"""Select alternate entrances from actual outgoing H3 crowd poses and prepare H3 jobs."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from changan_market import WORLD, street_frames, write_json


def features(frame):
    gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    zones = [(237, 281, 397, 400), (570, 277, 719, 401), (392, 284, 565, 355), (4, 129, 196, 269)]
    return [cv2.resize(gray[y:h, x:w], (48, 34)).astype("float32") for x, y, w, h in zones]


def distance(left, right):
    return max(
        np.mean(np.abs((a - a.mean()) - (b - b.mean()))) * weight
        for a, b, weight in zip(left, right, (1, 1, 0.75, 0.6))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("production", type=Path)
    args = parser.parse_args()
    level = json.loads((args.base / WORLD / "level.json").read_text(encoding="utf-8"))
    shots = {k: street_frames(k, args.work, v["frames"]) for k, v in level["clips"].items()}
    poses = {k: [features(f) for f in plate] for k, plate in shots.items()}
    jobs, entries = {}, []
    for src, meta in level["clips"].items():
        for window in meta.get("windows", []):
            choices = [window["hit"]]
            if window["node"] == 2:
                choices.append("fox_flinch")
            for dest in choices:
                times = range(window["begin"], window["end"])
                costs = [distance(poses[src][f], poses[dest][0]) for f in times]
                ids = [None] * len(times)
                while max(costs) > 11.5:
                    at = times[int(np.argmax(costs))]
                    key = f"entry_{len(jobs) + 1:02d}"
                    first = key + "_in"
                    last = dest + "_join"
                    join = min(21, len(shots[dest]) - 1)
                    for name, picture in [(first, shots[src][at]), (last, shots[dest][join])]:
                        if not cv2.imwrite(str(args.work / "anchors" / (name + ".png")), picture):
                            raise OSError("Cannot write " + name)
                    jobs[key] = dict(
                        first=first,
                        last=last,
                        length=22,
                        seed=96800 + len(jobs),
                        prefix="",
                        prompt="Photoreal live-action at a Tang dynasty night market. A continuous locked tripod shot. The people continue their movement already underway. The women in pink and green take a step and turn with real weight, sleeves and fabric swaying as they arrive in the ending pose. People in the middle and the shoppers at the right shift and turn naturally. The awning and lantern tassels move in the breeze. Same warm night exposure. No cuts, dissolve, magic, titles or music.",
                    )
                    for ix, f in enumerate(times):
                        cost = distance(poses[src][f], poses[src][at])
                        if cost < costs[ix]:
                            ids[ix], costs[ix] = (key, at, join), cost
                for f, selected in zip(times, ids):
                    if selected is None:
                        continue
                    key, at, join = selected
                    if entries and entries[-1]["take"] == key and entries[-1]["end"] == f:
                        entries[-1]["end"] = f + 1
                    else:
                        entries.append(
                            dict(
                                source=src, dest=dest, begin=f, end=f + 1, anchor=at, join=join, take=key
                            )
                        )
    write_json(args.production / "market_entries.json", entries)
    write_json(args.production / "market_entry_jobs.json", jobs)
    print(len(jobs), "branch entrance takes")


if __name__ == "__main__":
    main()
