"""Publish and stabilize all 49 Chapter 1 H3 takes into runtime MP4s, then extract annotations."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/forge"))
import linyuan_ch1_media as m


def main():
    # 1. Drama S1, S4, S7 (11 takes)
    for name in m.CH1_DRAMA:
        m.publish(name, variant=1, start=0, end=0, speed=1.0, note="ch1 drama")

    # 2. S2 Market Square plate + 6 wave takes (stabilized to PL_DUKOU)
    m.publish("c1_dukou_plate", variant=1, start=0, end=0, speed=1.0, note="dukou plate", stabilize_plate="PL_DUKOU")
    for w in m.DUKOU_WAVES:
        m.publish(w, variant=1, start=0, end=0, speed=1.0, note="dukou wave", stabilize_plate="PL_DUKOU")
    m.publish("c1_w_peddler", variant=1, start=46, end=100, speed=1.0, note="dukou peddler clean", stabilize_plate="PL_DUKOU")

    # 3. 15 S2 kill cuts: stabilized to PL_DUKOU and trimmed to <= 22 frames (<= 0.92s relay wait)
    for w in m.DUKOU_WAVES:
        for slot in m.DUKOU_SLOTS:
            m.publish(f"{w}_kill_{slot}", variant=1, start=0, end=22, speed=1.0, note="dukou kill", stabilize_plate="PL_DUKOU")

    # 4. 16 S6 Boss Taotie takes
    boss_trims = {
        "c1_boss_enter": (0, 72),
        "c1_boss_p1_a": (0, 0),
        "c1_boss_p1_b": (0, 0),
        "c1_boss_p1_c": (0, 0),
        "c1_boss_p1_flinch_l": (0, 26),
        "c1_boss_p1_flinch_r": (0, 26),
        "c1_boss_break": (0, 48),
        "c1_boss_p2_launch": (0, 64),
        "c1_boss_p2_intercept_early": (0, 26),
        "c1_boss_p2_intercept_mid": (0, 26),
        "c1_boss_p2_intercept_late": (0, 26),
        "c1_boss_p2_impact": (0, 26),
        "c1_boss_expose": (0, 48),
        "c1_boss_p3": (0, 0),
        "c1_boss_p3_flinch": (0, 26),
        "c1_boss_kill": (0, 60),
    }
    for name, (start, end) in boss_trims.items():
        m.publish(name, variant=1, start=start, end=end, speed=1.0, note="ch1 boss")

    # 5. Finalize masks, materials, threat_glows, and boss polygons
    subprocess.run([sys.executable, str(ROOT / "tools/forge/linyuan_ch1_annotate.py"), "finalize_annotations"], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/forge/linyuan_ch1.py")], check=True)


if __name__ == "__main__":
    main()
