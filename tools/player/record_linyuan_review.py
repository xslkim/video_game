"""Record the packaged MVP, mux its real presentation clock and prepare six recognition trials."""

import argparse
from bisect import bisect_right
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

from test_linyuan_mvp import check_scenario


ROUTES = ("old", "new", "story-civilian", "raft-miss", "needle-miss")
TOOLS = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def isolate_raft_miss(scratch):
    normal = scratch / "new"
    target = scratch / "raft-input"
    (target / "bamboo").mkdir(parents=True, exist_ok=True)
    shutil.copy2(normal / "save_yunyi.json", target / "save_yunyi.json")
    events = read(normal / "bamboo/playthrough.json")["events"]
    inputs = [e for e in events if e["event"].startswith("shot_") or e["event"] == "reload_begin"]
    hit = inputs.pop()
    if hit["clip"] != "wave_10" or hit["event"] != "shot_purify" or hit["frame"] < 40:
        raise ValueError("Expected the normal final vine cut at its middle anchor")
    miss = dict(hit, event="shot_miss", frame=24, input_x=973, input_y=446)
    inputs.extend((miss, dict(hit, arrows=hit["arrows"] - 1)))
    write(target / "bamboo/playthrough.json", dict(events=inputs, purpose=
          "Authored listening trial. Fire into empty space at source frame 24, then cut the vine at the recorded frame."))
    return target


def record_a1(exe, assets, scratch, review, identity):
    evidence = review / "evidence" / "a1"
    evidence.mkdir(parents=True, exist_ok=True)
    runs = {}
    for mode in ("old", "new"):
        target = scratch / f"a1-{mode}"
        if not (target / "playthrough.json").is_file():
            cmd = [str(exe), "--world", "changan", "--root", str(assets), "--level", "a1", "--smoke",
                   str(target), "--capture", "--feedback", mode]
            if mode == "new":
                cmd += ["--input-replay", str(scratch / "a1-old")]
            subprocess.run(cmd, cwd=tempfile.gettempdir(), timeout=300, check=True)
        data = read(target / "playthrough.json")
        if not data["ok"] or (data["shots"], data["hits"], data["lives"]) != (14, 14, 3):
            raise ValueError(f"Incomplete A1 reference run: {mode}")
        if mode == "new" and not data["assertions"].get("recorded_inputs_reproduced"):
            raise ValueError("A1 input replay diverged")
        movie = review / f"changan-a1-{mode}.mp4"
        subprocess.run([sys.executable, TOOLS / "changan_replay.py", target, movie], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", movie, "-map", "0:v", "-map",
                        "0:a", "-fps_mode:v", "passthrough", "-enc_time_base:v", "demux", "-f", "null", "-"],
                       check=True)
        dst = evidence / mode
        dst.mkdir(exist_ok=True)
        for name in ("playthrough.json", "postmix.json"):
            shutil.copy2(target / name, dst / name)
        runs[mode] = dict(frames=len(data["captures"]), seconds=data["seconds"],
                          actual_average_hz=len(data["captures"])/data["seconds"],
                          active_play_seconds=data["play_seconds"], sha256=sha256(movie.read_bytes()).hexdigest())
        write(evidence / "recordings.json", dict(**identity, routes=runs))
        print("A1", mode, runs[mode], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("player", type=Path)
    parser.add_argument("scratch", type=Path, help="Local NVMe with enough free space for uncompressed frames")
    parser.add_argument("review", type=Path, help="Deliverable folder for encoded movies, trial cards and event logs")
    parser.add_argument("--a1-root", type=Path, help="Existing Changan asset root for the A1 same-input comparison")
    args = parser.parse_args()
    exe, scratch, review = args.player.resolve(strict=True), args.scratch.resolve(), args.review.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    ev = review / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    identity = dict(player_sha256=sha256(exe.read_bytes()).hexdigest(),
                    manifest_sha256=sha256((exe.parent / "manifest.json").read_bytes()).hexdigest())
    stamp = scratch / "release.json"
    if stamp.exists() and read(stamp) != identity:
        raise ValueError("Scratch contains recordings from another release")
    write(stamp, identity)
    index = {}
    for route in ROUTES:
        run = scratch / route
        scenario = "normal" if route in ("old", "new") else route
        recorder = run / "recording"
        if not (recorder / "recording.json").exists():
            cmd = [str(exe), "--smoke", str(run), "--scenario", scenario, "--capture",
                   "--feedback", "old" if route == "old" else "new"]
            if route == "new":
                cmd += ["--input-replay", str(scratch / "old")]
            if route == "raft-miss":
                cmd += ["--input-replay", str(isolate_raft_miss(scratch))]
            subprocess.run(cmd, check=True, timeout=300, cwd=tempfile.gettempdir())
        stats = check_scenario(run, scenario)
        report = read(run / "bamboo/playthrough.json")
        if route in ("new", "raft-miss") and not report["assertions"].get("recorded_inputs_reproduced"):
            raise ValueError(f"Recorded input diverged: {route}")
        if route == "new":
            controls = []
            for source in (scratch / "old", run):
                shot = read(source / "save_yunyi.json")[0]
                combat = read(source / "bamboo/playthrough.json")["events"]
                controls.append([(shot["take"], shot["hit_frame"], shot["input"], shot["input_x"], shot["input_y"]),
                                 *[(e["clip"], e["frame"], e["event"], e["input_x"], e["input_y"])
                                   for e in combat if e["event"].startswith("shot_")]])
            diffs = [math.hypot(a[3]-b[3], a[4]-b[4]) for a, b in zip(*controls)]
            if len(controls[0]) != len(controls[1]) or any(a[:3] != b[:3] for a, b in zip(*controls)) or max(diffs) > .1:
                raise ValueError("Source frames, outcomes or screen-space source points differ between versions")
            write(ev / "same-input.json", dict(shots=len(diffs), max_source_pixel_error=max(diffs),
                                               source_frames_and_outcomes_identical=True))
        movie = review / f"linyuan-mvp-{route}.mp4" if route in ("old", "new") else ev / f"linyuan-{route}.mp4"
        if not movie.exists() or not (recorder / "mixed-stereo.f32").exists():
            subprocess.run([sys.executable, TOOLS / "changan_campaign_replay.py", recorder, movie], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", movie, "-map", "0:v", "-map",
                        "0:a", "-fps_mode:v", "passthrough", "-enc_time_base:v", "demux", "-f", "null", "-"],
                       check=True)
        for name in ("bamboo/playthrough.json", "recording/frames.tsv", "recording/recording.json",
                     "choices.jsonl", "timeline.json", "result.json", "save_yunyi.json", "voice-completion.json"):
            if (run / name).is_file():
                dst = ev / route / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(run / name, dst)
        data = read(recorder / "recording.json")
        times = [float(line.split()[1]) for line in (recorder / "frames.tsv").read_text().splitlines()]
        intervals = sorted(1000 * (b-a) for a, b in zip(times, times[1:]))
        if route == "new":
            story = read(run / "save_yunyi.json")[0]
            stamps = [(story["take"], story["hit_frame"], story["t_input"], story["t_feedback"])]
            stamps.extend((e["clip"], e["frame"], e["monotonic_seconds"],
                           e["monotonic_seconds"] + e["first_feedback_submit_ms"]/1000)
                          for e in report["events"] if "first_feedback_submit_ms" in e)
            origin = data["start_monotonic_seconds"]
            evidence = []
            pictures = ev / "first-feedback"
            pictures.mkdir(exist_ok=True)
            for clip, frame, start, presented in stamps:
                first = bisect_right(times, start-origin)
                stop = bisect_right(times, presented-origin)
                item = dict(clip=clip, source_frame=frame, input_seconds=start-origin,
                            first_submit_seconds=presented-origin, captured_between_input_and_submit=list(range(first, stop)))
                if first < stop:
                    still = pictures / f"{len(evidence)+1:02}-{clip}.png"
                    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", recorder / "frames" / f"{first}.bmp",
                                    "-frames:v", "1", still], check=True)
                    item["image"] = still.relative_to(ev).as_posix()
                evidence.append(item)
            write(ev / "first-feedback-samples.json", evidence)
        index[route] = dict(file=movie.relative_to(review).as_posix(), frames=len(times), seconds=data["seconds"],
                            actual_average_hz=len(times)/data["seconds"], frame_interval_p50_ms=statistics.median(intervals),
                            frame_interval_p95_ms=intervals[math.ceil(.95*len(intervals))-1],
                            longest_gap_ms=max(intervals), sha256=sha256(movie.read_bytes()).hexdigest(), result=stats)
        write(ev / "recordings.json", dict(**identity, routes=index))
        print(route, len(times), round(index[route]["actual_average_hz"], 2), movie, flush=True)
    subprocess.run([sys.executable, TOOLS / "linyuan_feedback_review.py", scratch, review], check=True)
    if args.a1_root:
        record_a1(exe, args.a1_root.resolve(strict=True), scratch, review, identity)


if __name__ == "__main__":
    main()
