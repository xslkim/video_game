"""Publish and stabilize all 49 Chapter 1 H3 takes into runtime MP4s, then extract annotations."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/forge"))
import linyuan_ch1_media as m


def main():
    # Clean up deprecated P1 close-up takes/regions so no orphan assets remain.
    for old_id in ("c1_boss_p1_a", "c1_boss_p1_b", "c1_boss_p1_c"):
        (m.ART / "drama" / f"{old_id}.mp4").unlink(missing_ok=True)
        (m.ROOT / "worlds/linyuan/regions" / f"{old_id}.json").unlink(missing_ok=True)
        (m.SELECTIONS_DIR / f"{old_id}.json").unlink(missing_ok=True)

    # 1. Drama S1, S4, S7 (11 takes)
    drama_variants = {"c1_13_conch": 2, "c1_15_lookup": 2, "c1_20_smoke": 2, "c1_21_run": 2}
    for name in m.CH1_DRAMA:
        m.publish(name, variant=drama_variants.get(name, 1), start=0, end=0, speed=1.0, note="ch1 drama")

    # 2. S2 Market Square plate + 6 wave takes (locked tripod, endpoint-feathered to PL_DUKOU)
    m.publish("c1_dukou_plate", variant=1, start=0, end=0, speed=1.0, note="dukou plate clean",
              in_anchor="PL_DUKOU", out_anchor="PL_DUKOU")
    for w in m.DUKOU_WAVES:
        v = 2 if w == "c1_w_bifang_sky" else 1
        m.publish(w, variant=v, start=0, end=0, speed=1.0, note="dukou wave clean",
                  in_anchor="PL_DUKOU", out_anchor="PL_DUKOU")
    m.publish("c1_w_peddler", variant=3, start=0, end=0, speed=1.15, note="dukou peddler full traverse",
              in_anchor="PL_DUKOU", out_anchor="PL_DUKOU")

    # 3. 15 S2 kill cuts: clean v3/v2 recoil-behind-cover takes scaled by 1.55x (~36f = 1.50s <= 1.8s)
    kill_variants = {w: (3 if w == "c1_w_bifang_sky" else 2) for w in m.DUKOU_WAVES}
    for w in m.DUKOU_WAVES:
        kv = kill_variants[w]
        valid = {
            f"{w}_kill_{json.loads((m.ANCHORS_DIR / f'{w}_{slot}.json').read_bytes())['frame']}.mp4"
            for slot in m.DUKOU_SLOTS
        }
        for old_mp4 in (m.ART / "dukou").glob(f"{w}_kill_*.mp4"):
            if old_mp4.name not in valid:
                old_mp4.unlink(missing_ok=True)
        for slot in m.DUKOU_SLOTS:
            m.publish(f"{w}_kill_{slot}", variant=kv, start=0, end=0, speed=1.55,
                      note="dukou kill recoil behind cover", in_anchor=f"@{w}/{slot}", out_anchor="PL_DUKOU")

    # 4. 15 S6 Boss Taotie takes (full source range scaled cleanly to target anchors — zero mid-smoke cuts)
    boss_specs = {
        "c1_boss_enter": (1, 1.65, "PL_SHOAL", "K_TAOTIE_1"),
        "c1_boss_p1_l": (1, 1.0, "K_TAOTIE_1", "K_TAOTIE_1"),
        "c1_boss_p1_r": (1, 1.0, "K_TAOTIE_1", "K_TAOTIE_1"),
        "c1_boss_p1_flinch_l": (2, 1.70, "@c1_boss_p1_l/aim", "K_TAOTIE_1"),
        "c1_boss_p1_flinch_r": (2, 1.70, "@c1_boss_p1_r/aim", "K_TAOTIE_1"),
        "c1_boss_break": (2, 1.45, "@c1_boss_p1_r/aim", "K_TAOTIE_2"),
        "c1_boss_p2_launch": (1, 1.35, "K_TAOTIE_2", "K_TAOTIE_2"),
        "c1_boss_p2_intercept_early": (1, 1.75, "@c1_boss_p2_launch/early", "K_TAOTIE_2"),
        "c1_boss_p2_intercept_mid": (1, 1.75, "@c1_boss_p2_launch/mid", "K_TAOTIE_2"),
        "c1_boss_p2_intercept_late": (1, 1.75, "@c1_boss_p2_launch/late", "K_TAOTIE_2"),
        "c1_boss_p2_impact": (1, 1.75, "@c1_boss_p2_launch/impact", "K_TAOTIE_2"),
        "c1_boss_expose": (1, 1.45, "K_TAOTIE_2", "K_TAOTIE_3"),
        "c1_boss_p3": (1, 1.15, "K_TAOTIE_3", "K_TAOTIE_3"),
        "c1_boss_p3_flinch": (1, 1.75, "K_TAOTIE_3", "K_TAOTIE_3"),
        "c1_boss_kill": (1, 1.20, "K_TAOTIE_3", "K_TAOTIE_END"),
    }
    for name, (v, spd, in_a, out_a) in boss_specs.items():
        m.publish(name, variant=v, start=0, end=0, speed=spd, note="ch1 boss clean",
                  in_anchor=in_a, out_anchor=out_a)

    # 5. Finalize masks, materials, threat_glows, and boss polygons
    subprocess.run([sys.executable, str(ROOT / "tools/forge/linyuan_ch1_annotate.py"), "finalize_annotations"], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/forge/linyuan_ch1.py")], check=True)


if __name__ == "__main__":
    main()
