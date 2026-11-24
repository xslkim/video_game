"""Generate and conform short event cues from the installed Stable Audio Open 1.0 weights."""

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from diffusers import StableAudioPipeline


CUES = {
    "shot": ("a taut wooden bowstring twangs followed by a thin paper whistle", .38),
    "miss": ("one paper dart flicks past the microphone and taps soft wood", .36),
    "hit": ("one dry hollow wooden knock with a small brass bell overtone", .40),
    "purify": ("delicate silk lantern crumples with sparkling descending glass chimes", .79),
    "intercept": ("air bubble pops sharply followed by a brief shower of tiny embers", .54),
    "hurt": ("single low hide drum thump followed by a short ragged breath of wind", .46),
    "reload": ("bamboo box sliding open and small sticks rattling inside it", .45),
    "ready": ("one precise polished wooden latch closing with a crisp double click", .28),
    "special": ("deep distant thunder layered with a struck bronze temple bell", 1.20),
    "civilian": ("a small alarm bell rings twice in quick succession, dry intimate sound", .60),
}


def conform(wave, rate, limit):
    peak = float(np.abs(wave).max())
    if not np.isfinite(peak) or peak < .01:
        raise ValueError("Silent or invalid generated cue")
    loud = np.flatnonzero(np.max(np.abs(wave), axis=1) > peak * .09)
    begin = max(0, int(loud[0]) - rate // 100)
    wave = wave[begin:begin + int(limit * rate)].copy()
    fade = min(len(wave) // 2, rate // 15)
    wave[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return wave * (.62 / max(.01, np.abs(wave).max()))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--variants",type=int,default=1)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pipe = StableAudioPipeline.from_pretrained(str(args.model), torch_dtype=torch.float16,
                                              local_files_only=True).to("cuda")
    rate = pipe.vae.config.sampling_rate
    variants = [(i,name if variant==0 else f"{name}_{variant+1}",spec,variant)
                for variant in range(args.variants) for i,(name,spec) in enumerate(CUES.items())]
    for i, name, (description, limit), variant in variants:
        dest = args.output / (name + ".wav")
        if dest.exists():
            continue
        seed = 88130 + i + 93*variant
        prompt = "Isolated single game Foley sound, immediate onset: " + description + ". Quiet dry studio, no music."
        for attempt in range(3):
            selected = seed + 1009 * attempt
            take = pipe(prompt, audio_end_in_s=2.5, num_inference_steps=42,
                        generator=torch.Generator("cuda").manual_seed(selected)).audios[0]
            try:
                wave = conform(take.T.float().cpu().numpy(), rate, limit)
                break
            except ValueError:
                if attempt == 2:
                    raise
        sf.write(dest, wave, rate, subtype="PCM_16")
        dest.with_suffix(".json").write_text(json.dumps({"model": "stable-audio-open-1.0",
            "prompt": prompt, "seed": selected}, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
