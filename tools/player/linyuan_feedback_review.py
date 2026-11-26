"""Cut six anonymized visual and listening trials from real Linyuan SDL recordings."""

import argparse
from bisect import bisect_right
import json
from pathlib import Path
import subprocess
import wave


CASES = [
    ("命中未击毁", "new", "shot_hit", "elite_core", "V04", "A02"),
    ("击毁", "new", "shot_purify", "wave_03", "V01", "A05"),
    ("打空", "raft-miss", "shot_miss", "wave_10", "V06", "A03"),
    ("拦截", "new", "shot_intercept", "c1_w_pangolin_roof", "V02", "A06"),
    ("受击", "needle-miss", "hurt", "c1_w_pangolin_roof", "V05", "A01"),
    ("误伤", "story-civilian", "yunyi", "c1_10_talon", "V03", "A04"),
]


def read(path):
    return json.loads(path.read_bytes())


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def supplement_feedback_pictures(captures, evidence):
    samples = read(evidence / "first-feedback-samples.json")
    normal = read(captures / "new/bamboo/playthrough.json")["events"]
    ordinary = [e for e in normal if "first_feedback_submit_ms" in e]
    supplemental = []
    for index, item in enumerate(samples):
        if item.get("image") or index == 0:
            continue
        wanted = ordinary[index - 1]
        for route in ("story-civilian", "raft-miss", "needle-miss"):
            run = captures / route
            recorder = run / "recording"
            origin = read(recorder / "recording.json")["start_monotonic_seconds"]
            times = [float(line.split()[1]) for line in (recorder / "frames.tsv").read_text().splitlines()]
            row = next((e for e in read(run / "bamboo/playthrough.json")["events"] if
                        (e["event"], e["clip"], e["frame"]) == (wanted["event"], wanted["clip"], wanted["frame"])), None)
            if row is None:
                continue
            inp = row["monotonic_seconds"] - origin
            sub = inp + row["first_feedback_submit_ms"]/1000
            capture = bisect_right(times, inp)
            if capture == len(times) or times[capture] > sub:
                continue
            still = evidence / "first-feedback" / f"supplement-{index+1:02}-{route}.png"
            ffmpeg("-i", recorder / "frames" / f"{capture}.bmp", "-frames:v", "1", still)
            supplemental.append(dict(normal_shot_number=index+1, source_route=route, clip=row["clip"],
                                     event=row["event"], source_frame=row["frame"], capture=capture,
                                     input_seconds=inp, first_submit_seconds=sub, sampled_seconds=times[capture],
                                     image=still.relative_to(evidence).as_posix()))
            break
    (evidence / "supplemental-feedback-samples.json").write_text(json.dumps(supplemental, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", type=Path, help="Root containing new, raft-miss, needle-miss and story-civilian")
    parser.add_argument("review", type=Path, help="Existing review folder with the muxed campaign recordings")
    args = parser.parse_args()
    cards = args.review / "recognition"
    key_dir = args.review / "facilitator"
    for folder in (cards / "visual", cards / "audio", key_dir):
        folder.mkdir(parents=True, exist_ok=True)
    key = []
    for label, route, event, clip, visual, audio in CASES:
        source = args.captures / route
        recorder = source / "recording"
        meta = read(recorder / "recording.json")
        origin = meta["start_monotonic_seconds"]
        movie = (args.review / "linyuan-mvp-new.mp4" if route == "new" else
                 args.review / "evidence" / f"linyuan-{route}.mp4")
        if route == "story-civilian":
            shot = read(source / "save_yunyi.json")[0]
            if shot["input"] != event:
                raise ValueError("Expected a civilian hit in the story recording")
            timestamp = shot["t_feedback"] - origin
            frame = shot["hit_frame"]
        else:
            events = read(source / "bamboo/playthrough.json")["events"]
            shot = next(e for e in events if e["event"] == event and clip in (e["clip"],e.get("media")))
            clip = shot["clip"]
            timestamp = shot["monotonic_seconds"] + shot.get("first_feedback_submit_ms", 0) / 1000 - origin
            frame = shot["frame"]
            # A second sword in this listening window would reveal a different result.
            for e in events:
                delta = e["monotonic_seconds"] - shot["monotonic_seconds"]
                if e["event"].startswith("shot_") and 0 < delta < .65:
                    raise ValueError(f"{label}: another sword {delta:.3f} s later")
        begin = max(0., timestamp - .1)
        if begin + .72 > meta["seconds"]:
            raise ValueError(f"Event outside the recording: {label}")
        offset = f"{begin:.6f}"
        # The two fixed opaque bands obscure literal outcome text and tutorial subtitles.
        mask = "drawbox=x=0:y=0:w=iw:h=ih*0.205:color=black:t=fill,drawbox=x=0:y=ih*0.84:w=iw:h=ih*0.16:color=black:t=fill"
        silent = cards / "visual" / f"{visual}.mp4"
        listening = cards / "audio" / f"{audio}.wav"
        ffmpeg("-ss", offset, "-i", movie, "-t", "0.720", "-map", "0:v:0", "-an", "-vf", mask,
               "-fps_mode", "vfr", "-enc_time_base", "1:1000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", silent)
        ffmpeg("-f", "f32le", "-ar", 48000, "-ac", 2, "-ss", offset, "-i", recorder / "mixed-stereo.f32",
               "-t", "0.720", "-map", "0:a:0", "-c:a", "pcm_s16le", listening)
        streams = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                             "stream=codec_type,nb_frames", "-of", "json", silent]))["streams"]
        if len(streams) != 1 or streams[0]["codec_type"] != "video" or int(streams[0]["nb_frames"]) < 3:
            raise ValueError(f"Incomplete silent trial: {visual}")
        with wave.open(str(listening)) as samples:
            if (samples.getframerate(), samples.getnchannels(), samples.getnframes()) != (48000, 2, 34560):
                raise ValueError(f"Incomplete listening trial: {audio}")
            if not any(samples.readframes(34560)):
                raise ValueError(f"Silent listening trial: {audio}")
        stamps = [float(row.split()[1]) for row in (recorder / "frames.tsv").read_text().splitlines()]
        before = max(t for t in stamps if t <= timestamp)
        after = min(t for t in stamps if t > timestamp)
        key.append(dict(outcome=label, route=route, event=event, clip=clip, source_frame=frame,
                        visual=visual, audio=audio, recording=movie.relative_to(args.review).as_posix(),
                        recording_event_seconds=timestamp, excerpt_start_seconds=begin,
                        previous_presentation_ms=(timestamp-before)*1000,
                        next_presentation_ms=(after-timestamp)*1000))
    (key_dir / "recognition-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    supplement_feedback_pictures(args.captures, args.review / "evidence")
    (cards / "使用说明.txt").write_text(
        "视觉组按 V01–V06 播放无声片段；听觉组按 A01–A06 播放纯音频。两组顺序独立。\n"
        "请参加者记录编号及首次辨认的事件。选项为命中未击毁、击毁、打空、拦截、受击、误伤。\n"
        "记录未作答与不确定项，重播后的修正另记。两组都结束后由主持人按答案表逐项统计。\n", encoding="utf-8-sig")
    print(f"{len(key)} silent clips and {len(key)} listening trials in {cards}")


if __name__ == "__main__":
    main()
