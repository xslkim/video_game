"""Run the Windows player through Linyuan's story and encounter branches."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path
import statistics
import subprocess
import tempfile


STORY = {
    "story-miss": ("miss", 0, 3),
    "story-timeout": ("timeout", 0, 3),
    "story-civilian": ("yunyi", -100, 2),
    "retry": ("yunyi", -100, 2),
    "story-boundaries": ("timeout", 0, 3),
    "story-pause": ("timeout", 0, 3),
    "give-up": ("yunyi", -100, 2),
}
SCENARIOS = (
    "normal", "early", "late", "scan-early", "needle-late", "needle-miss",
    "needle-repeat", "raft-miss", "raft-timeout", "ordinary-timeout", "empty",
    "early-reload", "frozen-input", "retry", "story-miss", "story-timeout", "story-civilian",
    "story-first", "story-last", "story-boundaries", "story-pause",
    "shoulder", "body", "needle-core-closed", "reload-held", "give-up",
)
RETRY_SCENARIOS = tuple(f"retry-wave-{n}" for n in range(1, 11) if n != 9)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(test, message):
    if not test:
        raise ValueError(message)


def timing_report(output):
    run = read(output / "bamboo/playthrough.json")
    story = read(output / "save_yunyi.json")[0]
    shots = [dict(clip=e["clip"], media=e["media"], frame=e["frame"], event=e["event"],
                  milliseconds=e["first_feedback_submit_ms"]) for e in run["events"]
             if "first_feedback_submit_ms" in e]
    require(len(shots) == run["shots"] and len(run["feedback_submit_ms"]) == len(shots),
            "Each consumed ordinary sword must have one feedback presentation")
    require(story["t_input"] >= 0 and story["t_feedback"] >= story["t_input"],
            "Missing independent story-sword feedback timestamp")
    story_sample = dict(clip=story["take"], frame=story["hit_frame"], event=story["input"],
                        milliseconds=1000 * (story["t_feedback"] - story["t_input"]))
    waits = run["intervals"]
    ordinary = [e["wait_ms"] for e in waits if e["from"] != "wave_09" and
                e["to"] not in ("wave_09", "wave_10")]
    def distribution(values):
        values = sorted(values)
        return dict(n=len(values), p50_ms=statistics.median(values), p95_ms=values[math.ceil(.95*len(values))-1])
    result = dict(renderer=run["renderer"], display_refresh_hz=run["display_refresh_hz"],
                  input="automated SDL mouse events", campaign_seconds=read(output / "result.json")["seconds"],
                  bamboo_seconds=run["play_seconds"], refresh_period_ms=1000 / run["display_refresh_hz"],
                  story_sword=story_sample, bamboo_swords=shots,
                  bamboo_feedback=distribution([s["milliseconds"] for s in shots]),
                  combined_feedback=distribution([s["milliseconds"] for s in [story_sample, *shots]]),
                  relay_intervals=waits, ordinary_wait=distribution(ordinary))
    (output / "timing.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def check_scenario(output, scenario):
    timeline = read(output / "timeline.json")
    expected = ["noodle", "save_yunyi", "yunyi_reply", "bamboo_card", "bamboo"]
    abandoned = scenario == "give-up"
    require([stage["stage"] for stage in timeline] == (expected[:-1] if abandoned else expected),
            "Incorrect campaign route")
    if not abandoned:
        require(timeline[-1]["next"] == "@complete", "Campaign did not finish")
    require(not (output / "checkpoint.json").exists(), "MVP wrote a campaign checkpoint")
    choices = [json.loads(line) for line in (output / "choices.jsonl").read_text(encoding="utf-8").splitlines()]
    require([row["event"] for row in choices] == ["start", "give_up" if abandoned else "finish"],
            "Missing start or exit choice")
    story = read(output / "save_yunyi.json")
    require(len(story) == 1, "Story sword must be resolved exactly once")
    shot = story[0]
    key, points, lives = STORY.get(scenario, ("sac", 1000, 3))
    require((shot["input"], shot["points"], shot["lives"]) == (key, points, lives), "Wrong story result")
    reply = "rebuke" if key == "yunyi" else "thanks"
    reply_stage = next(s for s in timeline if s["stage"] == "yunyi_reply")
    require(reply_stage.get("films") == [{"take": f"c1_12_{reply}", "voice": f"yunyi/{reply}"}],
            "Story outcome did not select its matching close-up and voice")
    response = "c1_11_hit" if key == "sac" else "c1_11_miss"
    require(shot["response"] == response and shot["arrows"] == 8, "Wrong story branch or ammo")
    require(shot["window_end"] - shot["warning_frame"] == 24, "Expected 24 source frames at half speed")
    if key == "timeout":
        require(shot["hit_frame"] == -1, "Timeout unexpectedly fired a sword")
        require(shot["t_closed"] - shot["t_open"] >= 1.95, "The two-second window closed too early")
    else:
        require(shot["warning_frame"] <= shot["hit_frame"] < shot["window_end"], "Hit outside the window")
    if scenario == "story-first":
        require(shot["hit_frame"] == shot["warning_frame"], "Expected the first hittable frame")
    if scenario == "story-last":
        require(shot["hit_frame"] == shot["window_end"] - 1, "Expected the last hittable frame")
    if scenario == "story-boundaries":
        require(shot["prewindow_inputs"] == 1 and shot["postwindow_inputs"] == 1, "Missing rejected boundary inputs")
    if scenario == "story-pause":
        require(shot["t_closed"] - shot["t_open"] >= 2.35, "Pausing shortened the playable window")
    run = read(output / "bamboo/playthrough.json")
    checks = run["assertions"]
    require(run["scenario"] == scenario and run["ok"] and checks and all(checks.values()),
            f"Encounter assertions failed: {[name for name, ok in checks.items() if not ok]}")
    if abandoned:
        require(run["lives"] == 0 and run["attempts"] == 1 and run["kills"] == 0, "Incorrect give-up state")
        require(not (output / "result.json").exists(), "An abandoned encounter committed a result")
        return {"story": key, "lives": 0, "attempts": 1, "assertions": len(checks)}
    extra = int(scenario == "needle-repeat")
    chips = [e for e in run["events"] if e["clip"] == "wave_08" and e["event"] == "shot_hit"]
    require(run["kills"] == 11 and run["hits"] == 13 + extra + len(chips) and len(chips) <= 1,
            "Wrong kill, armor or hit count")
    misses = 2 if scenario == "scan-early" else int(scenario in {"raft-miss", "needle-core-closed"})
    require(run["shots"] == run["hits"] + misses, "Wrong fired sword count")
    require(run["intercepts"] == 2 + extra, "Wrong number of interceptions")
    expected_lives = 3 if scenario == "retry" else lives
    expected_lives -= int(scenario in {"needle-miss", "raft-timeout", "ordinary-timeout"} or scenario in RETRY_SCENARIOS)
    require(run["lives"] == expected_lives and timeline[-1]["lives"] == expected_lives, "Wrong final health")
    result = read(output / "result.json")
    require(result["points"] == points + run["score"], "Failed attempt or story score was counted incorrectly")
    require(result["damage"] == shot["damage"] + run["hurts"], "Damage was counted across a failed attempt")
    require(all(result[name] == run[name] for name in ("hits", "shots", "arrows", "lives", "kills")),
            "Results screen disagrees with the runtime state")
    require((output / "title.bmp").is_file() and (output / "results.bmp").is_file(),
            "Missing title or final screen capture")
    if scenario == "normal":
        require(run["weak_returns"] >= 4 and run["reloads"] == 1 and not chips, "Normal route ignored return or partial recall")
        recall = next((e for e in run["events"] if e["event"] == "reload_begin"), None)
        require(recall is not None, "Partial recall did not record the input")
        ready = next((e for e in run["events"] if e["event"] == "ready" and
                      e["monotonic_seconds"] >= recall["monotonic_seconds"]), None)
        duration = .16 + .055 * (8 - recall["arrows"])
        require(ready is not None and abs(recall["duration_seconds"] - duration) < 1e-5 and
                ready["monotonic_seconds"] - recall["monotonic_seconds"] >= duration - .001,
                "Recall filled before the swords had time to return")
        starts = [e for e in run["events"] if "duration_seconds" in e and e["event"].startswith("voice_")]
        if starts:
            voices = {}
            for entry in starts:
                name = entry["event"].removeprefix("voice_")
                require(name not in voices, f"Repeated first-use voice: {name}")
                endings = [e for e in run["events"] if e["event"] == "voice_end" and e["voice"] == name]
                require(len(endings) == 1 and endings[0]["reason"] == "finished", f"Interrupted voice: {name}")
                seconds = endings[0]["monotonic_seconds"] - entry["monotonic_seconds"]
                require(seconds >= entry["duration_seconds"] - .005, f"Shortened voice: {name}")
                voices[name] = dict(began=entry["monotonic_seconds"], ended=endings[0]["monotonic_seconds"],
                                    source_seconds=entry["duration_seconds"], elapsed_seconds=seconds)
            require(set(voices) == {f"qingping/{name}" for name in ("scan", "needles", "elite_core", "raft")},
                    "Normal route did not complete all four combat voice lines")
            (output / "voice-completion.json").write_text(json.dumps(voices, indent=2), encoding="utf-8")
    return {"story": key, **{name: run[name] for name in ("hits", "shots", "kills", "lives", "arrows", "reloads")},
            "assertions": len(checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("player", type=Path, help="Path to Linyuan.exe")
    parser.add_argument("output", type=Path, help="New evidence directory; one subdirectory per route")
    parser.add_argument("--root", type=Path, help="Development or fixture root. Omit to test packaged assets.")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS + RETRY_SCENARIOS,
                        help="Repeat to select a subset or probe an individual retry wave")
    parser.add_argument("--capture", action="store_true", help="Record images and audio; timings are diagnostic")
    parser.add_argument("--jobs", type=int, default=1, help="Concurrent players for branch checks; use 1 for timings")
    parser.add_argument("--timings", action="store_true", help="Run a single unrecorded normal route and summarize G1/G2")
    args = parser.parse_args()
    exe = args.player.resolve(strict=True)
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    if args.timings:
        require(not args.capture and args.jobs == 1 and args.scenario in (None, ["normal"]),
                "--timings needs one normal player without capture")
    routes = args.scenario or (("normal",) if args.timings else SCENARIOS)
    require(len(routes) == len(set(routes)), "Use distinct scenarios")
    require(args.jobs >= 1, "--jobs must be positive")

    def run(scenario):
        out = folder / scenario
        cmd = [str(exe), "--smoke", str(out), "--scenario", scenario]
        if args.root:
            cmd.extend(["--root", str(args.root.resolve(strict=True))])
        if args.capture:
            cmd.append("--capture")
        result = subprocess.run(cmd, cwd=tempfile.gettempdir(), timeout=240, check=False)
        if result.returncode:
            detail = out / "error.txt"
            reason = detail.read_text(encoding="utf-8") if detail.is_file() else f"exit code {result.returncode}"
            raise RuntimeError(f"{scenario} at {out}: {reason}")
        summary = check_scenario(out, scenario)
        if args.timings:
            timing_report(out)
        return summary

    summary = {}
    failures = {}
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(routes))) as pool:
        pending = {pool.submit(run, scenario): scenario for scenario in routes}
        for item in as_completed(pending):
            scenario = pending[item]
            try:
                summary[scenario] = item.result()
            except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
                failures[scenario] = str(error)
                (folder / "failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
                print(scenario, error, flush=True)
            else:
                (folder / "matrix.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                print(scenario, summary[scenario], flush=True)
    require(not failures, f"{len(failures)} failed scenario(s), see {folder / 'failures.json'}")


if __name__ == "__main__":
    main()
