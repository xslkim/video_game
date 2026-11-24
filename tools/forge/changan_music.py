"""Render the festival and farewell instrumental cues with the local ACE-Step model."""

import argparse
import json
from pathlib import Path
import sys

import torch


TRACKS = {
    "festival": (
        68, 38217,
        "Tang dynasty lantern festival, lively Chinese chamber ensemble, dancing transverse dizi "
        "and pipa exchanging a recurring pentatonic tune, crisp hand drum and wooden clappers, "
        "unhurried festive 96 bpm processional, an intimate acoustic recording, no vocals",
    ),
    "fireflies": (
        78, 38218,
        "Quiet Chinese cinematic farewell at dawn, a single warm xiao bamboo flute plays a "
        "descending five-note pentatonic motif, breathing between phrases, restrained guqin "
        "harmonics and bowed erhu, air and space, tender resolving final cadence, 60 bpm, no vocals",
    ),
}

TRACKS.update({
    "title": (60,38219,"Chinese historical fantasy main title, lyrical rising pentatonic erhu and xiao theme over pipa harmonics, restrained cinematic strings and distant temple bells"),
    "lantern_master": (54,38220,"Chinese historical film character theme, low solo guqin and bowed cello in the old lantern maker's workshop, tender unresolved four-note motif, quiet breath"),
    "city_night": (58,38221,"wide establishing score for Tang Chang'an at dusk, soft xiao, sparse bronze bells and low strings, slowly passing lantern procession, spacious"),
    "illusion_market": (54,38222,"Tang night market theatre underscore, playful pizzicato pipa, yangqin and small woodblock interlocking in an uneven pulse, shadows of puppets, restrained"),
    "qujiang": (64,38223,"gentle nocturne on a Chinese lake, floating guzheng notes, one breathy bamboo flute and very soft bowed strings, intimate 64 bpm"),
    "pagoda": (50,38224,"inside an ancient Chinese brick pagoda at night, low sustained string harmonics, single dark bronze bell, dry taps on wood with long natural reverb"),
    "palace": (64,38225,"quiet imperial court before dawn, guqin and deep ritual bells over a held viola tone, affectionate and solemn, spacious instrumental score"),
    "market_battle": (70,38226,"Chinese puppet theatre action music, plucked sanxian and pipa ostinato with crisp paiban and drums, supple rhythm at 104 bpm, instrumental"),
    "river_battle": (70,38227,"Chinese dragon boat pursuit instrumental, racing low festival drums, pipa tremolo and low bowed strings, churning syncopation at 112 bpm"),
    "tower_battle": (68,38228,"ascent of an ancient tower, Chinese ceremonial percussion, tense erhu ostinato, hammered dulcimer accents, 116 bpm, cinematic instrumental"),
    "palace_battle": (72,38229,"desperate ride beneath a Tang palace, fast pipa, large Chinese war drums and surging orchestral strings, clear downbeats at 124 bpm, instrumental"),
    "guardian_battle": (71,38230,"great mechanical silk lantern guardian, heavy measured drum ostinato and low brass, melodic Chinese bowed strings against wooden clappers, 106 bpm"),
    "xuanzhu_battle": (76,38231,"final Chinese fantasy confrontation, low guqin motif answered by high xiao, large drums and spacious brass swells, beautiful sorrow beneath urgent 122 bpm"),
    "farewell": (75,38232,"quiet Chinese orchestral farewell, a descending five-note xiao motif passed to erhu above sparse guqin, clear solo instrument, resolves warmly into silence"),
    "credits": (83,38233,"end credits of a Chinese historical fantasy film, wistful solo Chinese female vocal, soft bamboo flute and pipa, amber lantern festival at dawn, warm 72 bpm"),
})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_repo", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.model_repo))
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    torch.backends.cuda.preferred_blas_library("cublaslt")
    handler = AceStepHandler()
    handler.initialize_service(project_root=str(args.model_repo), config_path="acestep-v15-turbo", device="cuda")
    for name, (duration, seed, prompt) in TRACKS.items():
        dest = args.output / (name + ".wav")
        if dest.exists():
            continue
        lyrics = ("[Verse]\n一盏灯 穿过朱雀长街\n你走过 风吹起衣袂\n"
                  "[Chorus]\n明年上元 请记得点灯\n满城萤火 有一盏为你等\n"
                  "[Outro]\n今年的灯 很好看\n" if name == "credits" else "")
        params = GenerationParams(caption=prompt, lyrics=lyrics, duration=duration, instrumental=not bool(lyrics),
                                  inference_steps=8, seed=seed)
        config = GenerationConfig(batch_size=1, audio_format="wav", use_random_seed=False, seeds=[seed])
        result = generate_music(handler, None, params, config, save_dir=str(args.output))
        if not result.success:
            raise RuntimeError(result.error)
        Path(result.audios[0]["path"]).replace(dest)
        dest.with_suffix(".json").write_text(json.dumps({"seed": seed, "duration": duration,
            "prompt": prompt, "lyrics": lyrics, "model": "acestep-v15-turbo"}, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
