"""Temporary synthetic binding fixtures for the runtime assembler. No production art is used."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools/forge"))
from linyuan_level import ROUTE, TAKES, assemble
from check_linyuan import check_bamboo, read_mask, validate


def polygon(first, last, x=100):
    points = [[x, 100], [x + 100, 100], [x + 100, 160], [x, 160]]
    return [dict(frame=frame, polygon=points) for frame in sorted({first, last})]


def fixture(root):
    source = root / "working cuts/test-only.mp4"
    source.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=1280x720:rate=24",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-frames:v", "40",
                    "-t", "1.666667", "-c:v", "libx264", "-bf", "0", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True)
    common = dict(file=source.relative_to(root).as_posix(), frames=40,
                  sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    videos = {key: common.copy() for key in (*TAKES, "c1_bamboo_plate")}
    for name in dict.fromkeys(ROUTE):
        key = "c1_w_" + name
        if name == "pangolin_roof":
            for suffix in ("intercept_early", "intercept_late", "impact", "flinch", "kill"):
                videos["c1_pangolin_" + suffix] = common.copy()
            for media, start in ((key, 4), ("c1_pangolin_threat", 8)):
                videos[media] = dict(common, launch=start, warning=start-1, impact=start+12,
                                     regions=polygon(start, start+11),
                                     intercept_windows=[[start, start+5, "early"], [start+5, start+12, "late"]])
            videos[key]["core_regions"] = polygon(39, 39, 790)
        else:
            bounds = [5, 10, 15] if name == "raft" else [5, 10, 15, 20]
            entries = [[a, b, a] for a, b in zip(bounds, bounds[1:])]
            videos[key] = dict(common, hit_windows=entries, warning=13, impact=23,
                               regions=polygon(bounds[0], bounds[-1]-1))
            for _, _, anchor in entries:
                result = ("c1_raft_drop_" if name == "raft" else key + "_kill_") + str(anchor)
                videos[result] = common.copy()
            if name != "raft":
                # The shoulder is not visible in the first frame of the body window.
                videos[key]["weak_regions"] = polygon(6, bounds[-1]-1)

    def cues(names):
        return [dict(begin=i*3, end=i*3+3, voice=name, subtitle=name) for i, name in enumerate(names)]

    # Dummy PCM is confined to this temporary fixture, and covers the same ten dialogue IDs used by the level.
    for name in ("voice/qingping/noodle", "voice/luchen/noodle", "voice/yunyi/talon", "voice/qingping/talon",
                 "voice/qingping/scan", "voice/qingping/needles", "voice/qingping/elite_core",
                 "voice/qingping/raft", "voice/yunyi/thanks", "voice/yunyi/rebuke", "music/battle"):
        path = root / "assets/linyuan/audio" / (name + ".wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setparams((2 if name.startswith("music/") else 1, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(bytes(480))
    return dict(videos=videos, materials=[["earth"] * 64 for _ in range(36)],
                materials_sha256=common["sha256"], noodle_cues=cues(("qingping/noodle", "luchen/noodle")),
                story=dict(talon=dict(window_start=10, cues=cues(("yunyi/talon", "qingping/talon")),
                                      regions={"sac": polygon(10, 33), "yunyi": polygon(10, 33, 500)})))


class BindingAssemblyTest(unittest.TestCase):
    def test_runtime_and_rebuild(self):
        with tempfile.TemporaryDirectory(prefix="linyuan-fixture-") as temp:
            root = Path(temp)
            binding = fixture(root)
            level = assemble(root, binding)
            self.assertEqual(validate(root), dict(stages=5, bamboo_nodes=10, bamboo_media=31, story_media=6))
            folder = root / "worlds/linyuan/bamboo"
            clips = level["clips"]
            fox = read_mask(folder / "wave_01.mask", clips["wave_01"])
            self.assertFalse(any(fox[:5]))
            self.assertTrue(fox[5])
            self.assertEqual(clips["wave_09"]["windows"][0]["begin"], 4)
            self.assertEqual(clips["elite_flinch"]["next"], "elite_launch")
            self.assertEqual(clips["elite_impact"]["next"], "elite_launch")
            self.assertEqual(level["nodes"][7]["weak_damage"], 2)
            self.assertEqual(level["nodes"][1]["material"], "feather")
            self.assertEqual(level["nodes"][8]["tier"], 3)
            self.assertEqual(level["nodes"][9]["material"], "vine")
            self.assertEqual(clips["wave_02"]["attack"], "collision")
            self.assertEqual(clips["wave_09"]["attack"], "blast")
            self.assertEqual(clips["elite_launch"]["attack"], "blast")
            self.assertLess(clips["wave_02"]["start"], clips["wave_07"]["start"])
            self.assertEqual(clips["elite_launch"]["windows"][0]["begin"], 8)
            self.assertEqual(clips["elite_core"]["start"], 39)
            self.assertEqual(clips["elite_core"]["hold_seconds"], 2.)
            self.assertEqual(clips["elite_core"]["voice_cues"][0]["frame"], 39)
            self.assertTrue((root / "assets/linyuan/bamboo/c1_bamboo_plate.mp4").is_file())
            old_level = copy.deepcopy(level)
            old_level["clips"]["wave_09"]["weak_mask"] = True
            (folder / "level.json").write_text(json.dumps(old_level), encoding="utf-8")
            obsolete = folder / "wave_09.weak.mask"
            obsolete.write_bytes(b"old armoured enemy")
            before = (folder / "wave_01.mask").read_bytes()
            binding["videos"]["c1_w_fox_shrine"]["regions"] = polygon(5, 19, 200)
            binding["videos"]["c1_w_fox_shrine"]["weak_regions"] = polygon(6, 19, 200)
            assemble(root, binding)
            self.assertFalse(obsolete.exists())
            self.assertNotEqual(before, (folder / "wave_01.mask").read_bytes())
            prior = (folder / "level.json").read_bytes()
            prior_mask = (folder / "wave_01.mask").read_bytes()
            bad = copy.deepcopy(binding)
            bad["videos"]["c1_w_suanni_steps"]["weak_regions"] = polygon(6, 19, 615)
            with self.assertRaisesRegex(ValueError, "Weak region outside body"):
                assemble(root, bad)
            self.assertEqual(prior, (folder / "level.json").read_bytes())
            self.assertEqual(prior_mask, (folder / "wave_01.mask").read_bytes())
            bad = copy.deepcopy(binding)
            bad["videos"]["c1_11_miss"]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "requires new annotation"):
                assemble(root, bad)
            bad_level = json.loads(prior)
            bad_level["clips"]["wave_01"]["next"] = "missing_retry"
            with self.assertRaisesRegex(AssertionError, "Missing clip"):
                check_bamboo(bad_level, folder)
            (folder / "wave_01.mask").write_bytes(prior_mask[:10])
            with self.assertRaisesRegex(ValueError, "Stale mask"):
                check_bamboo(level, folder)
            assemble(root, binding)
            voice = root / "assets/linyuan/audio/voice/qingping/needles.wav"
            original = voice.read_bytes()
            voice.unlink()
            with self.assertRaisesRegex(ValueError, "Missing referenced audio"):
                validate(root)
            voice.write_bytes(original[:50])
            with self.assertRaisesRegex(ValueError, "Truncated referenced WAV"):
                validate(root)
            voice.write_bytes(original)
            (root / "assets/linyuan/drama/c1_11_miss.mp4").unlink()
            with self.assertRaisesRegex(ValueError, "Missing media"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
