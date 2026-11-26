"""Encode captured frames and postmix on the real presentation clock."""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("capture",type=Path)
    ap.add_argument("output",type=Path)
    args = ap.parse_args()
    root = args.capture.resolve()
    run = json.loads((root/"playthrough.json").read_bytes())
    audio = json.loads((root/"postmix.json").read_bytes())
    shots = run["captures"]
    lines = ["ffconcat version 1.0"]
    precise = "capture_target_hz" in run
    for i, frame in enumerate(shots):
        time = frame["time"] if i else 0
        end = shots[i+1]["time"] if i+1<len(shots) else run["seconds"]
        if end <= time:
            raise ValueError("Nonmonotonic capture timestamps")
        lines.append(f"file 'frames/{frame['capture']:05d}.bmp'")
        if precise:
            lines.append("option framerate 1000")
        length = end - time
        if precise and i+1 == len(shots):
            length = max(0.001, length - 0.002)
        lines.append(f"duration {length:.9f}")
    lines.append(f"file 'frames/{shots[-1]['capture']:05d}.bmp'")
    if precise:
        lines.append("option framerate 1000")
    timing = root/"capture.ffconcat"
    timing.write_text("\n".join(lines)+"\n",encoding="utf8")
    start = audio["start_time"]
    offset = f"adelay={round(start*1000)}:all=1" if start >= 0 else f"atrim=start={-start:.8f},asetpts=PTS-STARTPTS"
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp = args.output.with_suffix(".part.mp4")
    subprocess.run(["ffmpeg","-v","error","-nostdin","-y","-safe","0","-f","concat","-i",str(timing),
                    "-f","f32le","-ar",str(audio["sample_rate"]),"-ac",str(audio["channels"]),"-i",str(root/"postmix.f32"),
                    *(["-fps_mode","vfr","-enc_time_base","1:1000"] if precise else ["-vf","fps=24"]),
                    "-af",offset+",apad","-c:v","libx264","-crf","19","-preset","fast",
                    "-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-t",f"{run['seconds']:.6f}",
                    "-movflags","+faststart",str(tmp)],check=True)
    tmp.replace(args.output)


if __name__ == "__main__":
    main()
