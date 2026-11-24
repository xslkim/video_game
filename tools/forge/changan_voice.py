"""Render matched Chinese dialogue auditions using the installed local TTS models."""

import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np
import soundfile as sf
import torch


def synthesizer(engine):
    if engine == "qwen":
        from qwen_tts import Qwen3TTSModel
        cache=Path(os.environ["HF_HOME"])/"hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice"
        snapshot=cache/"snapshots"/(cache/"refs/main").read_text().strip()
        model = Qwen3TTSModel.from_pretrained(str(snapshot),
                                               device_map="cuda:0", dtype=torch.bfloat16)
        def render(text, character, direction):
            waves, rate = model.generate_custom_voice(text=text, language="Chinese",
                speaker=character["speaker"], instruct=character["voice"]+direction, max_new_tokens=512)
            return waves[0], rate
    else:
        # This local service includes the matching Chinese tokenizer for VoxCPM2.
        os.environ["VOXCPM_ENABLE_DENOISER"]="0"
        sys.path.insert(0,str(Path.home()/"tts-server"))
        from server import run_generate
        def render(text, character, direction):
            return run_generate(text,character["voice"]+direction,None,2.0,10,False,True,False),48000
    return render


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("engine",choices=["qwen","vox"])
    ap.add_argument("output",type=Path)
    ap.add_argument("--script",type=Path,default=Path(__file__).resolve().parents[2]/"worlds/changan/production/voice_audition.json")
    args=ap.parse_args()
    os.environ.setdefault("HF_HOME",str(Path.home()/"SoundGame/models/hf"))
    os.environ.setdefault("HF_HUB_OFFLINE","1")
    render=synthesizer(args.engine)
    sheet=args.script
    for actor,spec in json.loads(sheet.read_text(encoding="utf8")).items():
        for i,(key,text,direction) in enumerate(spec["lines"]):
            torch.manual_seed(73500+i)
            name=args.output/args.engine/actor/(key+".wav")
            name.parent.mkdir(parents=True,exist_ok=True)
            minimum = .16 if len(text.strip("。，！？")) <= 2 else .5
            if name.exists() and sf.info(name).duration>=minimum:
                continue
            wave,rate=render(text,spec,direction)
            wave=np.asarray(wave).squeeze()
            if not np.isfinite(wave).all() or len(wave)<rate*minimum or np.max(np.abs(wave))<.01:
                raise ValueError(f"Invalid spoken take for {actor}/{key}")
            tmp=name.with_suffix(".part.wav")
            sf.write(tmp,wave,rate,subtype="PCM_16")
            tmp.replace(name)
            print(name,len(wave)/rate,flush=True)


if __name__=="__main__":
    main()
