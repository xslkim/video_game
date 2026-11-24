"""Match audition loudness and check the rendered Mandarin against the script."""

import argparse
import json
from pathlib import Path
import re
import subprocess


def loudness(source, dest, target):
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(source)]
    filt = f"loudnorm=I={target}:TP=-2:LRA=9"
    analysis = subprocess.run(args + ["-af", filt + ":print_format=json", "-f", "null", "-"],
                              capture_output=True, text=True, check=True).stderr
    values, _ = json.JSONDecoder().raw_decode(analysis[analysis.rfind("{"):])
    for key, field in [("measured_I","input_i"),("measured_TP","input_tp"),("measured_LRA","input_lra"),
                       ("measured_thresh","input_thresh"),("offset","target_offset")]:
        filt += f":{key}={values[field]}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(args + ["-loglevel", "error", "-y", "-af", filt + ":linear=true", "-ar", "48000",
                           "-c:a", "pcm_s16le", str(dest)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("work", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("recognizer", type=Path)
    args = ap.parse_args()
    from funasr import AutoModel
    recognizer = AutoModel(model=str(args.recognizer), device="cpu", disable_update=True, ncpu=3)
    script = Path(__file__).resolve().parents[2] / "worlds/changan/production/voice_audition.json"
    cast = json.loads(script.read_bytes())
    records = []
    for take in sorted((args.work / "voice").glob("*/*/*.wav")):
        engine, actor = take.parts[-3:-1]
        dest = args.output / "voice" / engine / actor / take.name
        loudness(take, dest, -19)
        recognized = recognizer.generate(input=str(dest), language="zh", use_itn=True)[0]["text"]
        recognized = re.sub(r"<\|.*?\|>", "", recognized).strip()
        expected = next(line[1] for line in cast[actor]["lines"] if line[0] == take.stem)
        records.append(dict(engine=engine, actor=actor, line=take.stem, expected=expected,
                            transcript=recognized, target_lufs=-19))
    for take in sorted((args.work / "music").glob("*.wav")):
        loudness(take, args.output / "music" / take.name, -23)
    (args.output / "audition.json").write_text(json.dumps(records, ensure_ascii=False, indent=2),encoding="utf8")


if __name__ == "__main__":
    main()
