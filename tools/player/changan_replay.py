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
    for i, frame in enumerate(shots):
        time = frame["time"] if i else 0
        end = shots[i+1]["time"] if i+1<len(shots) else run["seconds"]
        if end <= time:
            raise ValueError("Nonmonotonic capture timestamps")
        lines.extend([f"file 'frames/{frame['capture']:05d}.bmp'",f"duration {end-time:.9f}"])
    lines.append(f"file 'frames/{shots[-1]['capture']:05d}.bmp'")
    timing = root/"capture.ffconcat"
    timing.write_text("\n".join(lines)+"\n",encoding="utf8")
    start = audio["start_time"]
    offset = f"adelay={round(start*1000)}:all=1" if start >= 0 else f"atrim=start={-start:.8f},asetpts=PTS-STARTPTS"
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp = args.output.with_suffix(".part.mp4")
    subprocess.run(["ffmpeg","-v","error","-nostdin","-y","-safe","0","-f","concat","-i",str(timing),
                    "-f","f32le","-ar",str(audio["sample_rate"]),"-ac",str(audio["channels"]),"-i",str(root/"postmix.f32"),
                    "-vf","fps=24","-af",offset+",apad","-c:v","libx264","-crf","19","-preset","fast",
                    "-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-t",f"{run['seconds']:.6f}",
                    "-movflags","+faststart",str(tmp)],check=True)
    tmp.replace(args.output)


if __name__ == "__main__":
    main()
