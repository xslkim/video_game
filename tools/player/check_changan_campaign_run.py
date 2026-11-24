"""Summarize an actual full game run from its stage clock, input logs and checkpoint."""

import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("world", type=Path)
    ap.add_argument("run", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    campaign = read(args.world)
    trace = read(args.run / "timeline.json")
    state = read(args.run / "checkpoint.json")
    expected = [s["id"] for ch in campaign["chapters"] for s in ch["stages"]]
    if state["next"] != "@complete" or [row["stage"] for row in trace] != expected:
        raise ValueError("The evidence does not contain a complete playthrough")
    times = {row["stage"]: row for row in trace}
    chapters = {}
    for chapter in campaign["chapters"]:
        first, last = (times[chapter["stages"][i]["id"]] for i in (0, -1))
        report = dict(
            seconds=round(last["ended"] - first["opened"], 2),
            reloads=0,
            trial_windows=0,
            encounter_purifications=0,
            projectile_launches=0,
            trial_timeouts=0,
            specials=0,
            retry_count=0,
            skipped_cinematics=0,
            **state["scores"][chapter["id"]],
        )
        for stage in chapter["stages"]:
            sid = stage["id"]
            counted_stage = "reloads" in times[sid]
            report["reloads"] += times[sid].get("reloads", 0)
            if stage["type"] == "film":
                report["skipped_cinematics"] += int(times[sid].get("skipped", False))
            if stage["type"] == "trial":
                log = read(args.run / (sid + ".json"))
                if not log:
                    raise ValueError("Empty trial evidence " + sid)
                report["retry_count"] += max(r.get("attempt", 1) for r in log) - 1
                for r in log:
                    if not stage["trial"]["steps"][r["step"]].get("story_shot"):
                        report["trial_windows"] += 1
                    report["trial_timeouts"] += int(r["input"] == "timeout")
                    report["specials"] += int(r.get("special", False))
                    if not counted_stage:
                        report["reloads"] += r.get("reloads", 0)
                    if (
                        r.get("hit_frame", -1) >= 0
                        and not r["warning_frame"] <= r["hit_frame"] < r["window_end"]
                    ):
                        raise ValueError(f"Out-of-window hit in {sid}/{r['step']}")
            if stage["type"] == "encounter":
                run = read(args.run / sid / "playthrough.json")
                if not run["ok"]:
                    raise ValueError("Encounter failed " + sid)
                report["encounter_purifications"] += sum(e["event"] == "shot_purify" for e in run["events"])
                if not counted_stage:
                    report["reloads"] += run["reloads"]
                report["projectile_launches"] += run["launches"]
        chapters[chapter["id"]] = report
    output = dict(
        difficulty=state["difficulty"],
        seconds=round(trace[-1]["ended"], 2),
        stages=len(trace),
        chapters=chapters,
    )
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf8")
    print(rendered)


if __name__ == "__main__":
    main()
