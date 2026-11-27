"""Assemble Chapter 1 (九曲渡) runtime manifests: dukou/level.json, drama.json, chapter_one.json, start.json."""

import copy
import hashlib
import json
import pickle
import struct
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/forge"))
sys.path.insert(0, str(ROOT / "tools/player"))

from linyuan_level import TAKES as MVP_TAKES, dump_compact_json, write
from check_linyuan_ch1 import validate_ch1

ART = ROOT / "assets/linyuan"
WORLD = ROOT / "worlds/linyuan"
PRODUCTION = WORLD / "production"

DUKOU_NODES = [
    dict(id="wave_01", label="毕方 · 瞄准胸口琥珀囊", media="c1_w_bifang_awning", hp=1, score=100,
         material="feather", tier=1, attack="collision", hold=True,
         cues=[
             dict(voice="qingping/first", subtitle="青萍  看左边棚顶！胸口亮处就是弱点，瞄准琥珀出剑。", begin_rel=0),
             dict(voice="luchen/up", subtitle="陆沉  来吧！", begin_rel=24),
         ]),
    dict(id="wave_02", label="狻猊 · 瞄准肩上琥珀罐", media="c1_w_suanni_tables", hp=1, score=100,
         material="ceramic", tier=1, attack="claw",
         cues=[dict(voice="qingping/canister", subtitle="青萍  这头狻猊的罐子在肩侧！直击弱点能把剑弹回来。", begin_rel=0)]),
    dict(id="wave_03", label="毕方", media="c1_w_bifang_sky", hp=1, score=100,
         material="feather", tier=1, attack="collision", cues=[]),
    dict(id="wave_04", label="狻猊", media="c1_w_suanni_shrine", hp=1, score=100,
         material="ceramic", tier=1, attack="claw",
         cues=[dict(voice="qingping/shrine", subtitle="青萍  神龛右边又出来一只！", begin_rel=0)]),
    dict(id="wave_05", label="狻猊", media="c1_w_suanni_tables", hp=1, score=100,
         material="ceramic", tier=1, attack="claw", cues=[], peddler_after=True),
    dict(id="wave_06", label="喷火狻猊", media="c1_w_suanni_bridge", hp=1, score=100,
         material="ceramic", tier=1, attack="blast",
         cues=[dict(voice="qingping/bridge", subtitle="青萍  桥上那只在蓄火！", begin_rel=0)]),
    dict(id="wave_07", label="毕方", media="c1_w_bifang_awning", hp=1, score=100,
         material="feather", tier=1, attack="collision", cues=[]),
    dict(id="wave_08", label="狻猊", media="c1_w_suanni_shrine", hp=1, score=100,
         material="ceramic", tier=1, attack="claw", cues=[]),
    dict(id="wave_09", label="毕方", media="c1_w_bifang_sky", hp=1, score=100,
         material="feather", tier=1, attack="collision", cues=[]),
    dict(id="wave_10", label="重甲狻猊 · 瞄准肩罐", media="c1_w_suanni_tables", hp=2, score=150,
         material="ceramic", tier=2, attack="claw", weak_damage=2, flinch=True, cues=[]),
    dict(id="wave_11", label="喷火狻猊", media="c1_w_suanni_bridge", hp=1, score=100,
         material="ceramic", tier=1, attack="blast", cues=[]),
]


def rle_spans(mask_u8):
    small = cv2.resize(mask_u8, (640, 360), interpolation=cv2.INTER_NEAREST) > 0
    ys, xs = np.nonzero(np.diff(np.pad(small.astype(np.uint8), ((0, 0), (1, 1))), axis=1))
    return list(zip(ys[::2], xs[::2], xs[1::2]))


def write_mask(path, sha256_hex, frames_list, windows, weak_of_body=None):
    n = len(frames_list)
    payload = bytearray(b"DCM1" + bytes.fromhex(sha256_hex))
    payload.extend(struct.pack("<H", n))
    has_any = False
    for f, mask_u8 in enumerate(frames_list):
        active = any(w["begin"] <= f < w["end"] for w in windows)
        spans = []
        if active:
            m = mask_u8
            if weak_of_body is not None:
                m = cv2.bitwise_and(m, weak_of_body[f])
            else:
                # Guarantee non-empty body mask throughout every active window
                if cv2.countNonZero(cv2.resize(m, (640, 360), interpolation=cv2.INTER_NEAREST)) == 0:
                    m = np.zeros_like(mask_u8)
                    cv2.circle(m, (m.shape[1] // 2, m.shape[0] // 2), 40, 255, -1)
            spans = rle_spans(m)
            if spans:
                has_any = True
        payload.extend(struct.pack("<H", len(spans)))
        for y, x0, x1 in spans:
            payload.extend(struct.pack("<HHH", int(y), int(x0), int(x1)))
    if weak_of_body is not None and not has_any:
        raise ValueError(f"Empty weak mask: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(payload))


def build_dukou(annot, masks_cache):
    dukou_dir = WORLD / "dukou"
    dukou_dir.mkdir(parents=True, exist_ok=True)
    plate_mp4 = ART / "dukou/c1_dukou_plate.mp4"
    cap = cv2.VideoCapture(str(plate_mp4))
    plate_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    plate_sha = hashlib.sha256(plate_mp4.read_bytes()).hexdigest()

    nodes = []
    clips = {}
    anchors = annot  # alias
    sel_dir = PRODUCTION / "ch1_selections"

    def kill_entry(wave_media, slot, next_clip):
        sel = json.loads((sel_dir / f"{wave_media}_kill_{slot}.json").read_bytes())
        return sel["id"], dict(
            media=sel["id"], sha256=sel["sha256"], frames=sel["frames"],
            in_anchor=wave_media, out_anchor="dukou",
            next=next_clip,
        )

    for idx, spec in enumerate(DUKOU_NODES):
        nid = spec["id"]
        wmedia = spec["media"]
        wmeta = annot["dukou_waves"][wmedia]
        bmasks, wmasks = masks_cache["waves"][wmedia]
        after_node = DUKOU_NODES[idx + 1]["id"] if idx + 1 < len(DUKOU_NODES) else "@complete"
        next_after_kill = "peddler_06" if spec.get("peddler_after") else after_node

        w0, w1 = wmeta["window"]
        anchor_frames = {
            slot: json.loads((sel_dir / f"{wmedia}_kill_{slot}.json").read_bytes())["id"].rsplit("_", 1)[1]
            for slot in ("early", "mid", "late")
        }
        fe, fm, fl = int(anchor_frames["early"]), int(anchor_frames["mid"]), int(anchor_frames["late"])
        m1 = max(w0 + 4, min(w1 - 8, (fe + fm) // 2))
        m2 = max(m1 + 4, min(w1 - 4, (fm + fl) // 2))
        slots_ranges = [
            ("early", w0, m1),
            ("mid", m1, m2),
            ("late", m2, w1),
        ]
        windows = []
        for s_name, sb, se in slots_ranges:
            if se <= sb:
                continue
            kid = f"{nid}_hit_{s_name}"
            if spec.get("flinch") and s_name == "mid":
                pass
            kname, kspec = kill_entry(wmedia, s_name, next_after_kill)
            clips[kid] = kspec
            hit_target = kid if not spec.get("flinch") else kid
            windows.append(dict(
                begin=sb, end=se, kind="target", node=idx,
                hit=hit_target,
            ))

        # Build clip entry
        cdict = dict(
            media=wmedia, sha256=wmeta["sha256"], frames=wmeta["frames"],
            start=max(0, w0 - 8), in_anchor="dukou", out_anchor="dukou",
            next=nid, windows=windows, warning_frame=min(wmeta["warning"], wmeta["impact"] - 1),
            impact_frame=max(w1, wmeta["impact"]), attack=spec["attack"], weak_mask=True,
        )
        if spec.get("hold"):
            cdict["hold_frame"] = min(w1 - 2, w0 + 10)
        if spec.get("cues"):
            vcues = []
            for c in spec["cues"]:
                cf = min(w1 - 1, w0 + c["begin_rel"])
                vcues.append(dict(frame=cf, voice=c["voice"], subtitle=c["subtitle"], priority=1))
            cdict["voice_cues"] = vcues
        clips[nid] = cdict
        write_mask(dukou_dir / f"{nid}.mask", wmeta["sha256"], bmasks, windows)
        write_mask(dukou_dir / f"{nid}.weak.mask", wmeta["sha256"], wmasks, windows, weak_of_body=bmasks)

        node_entry = dict(
            id=nid, label=spec["label"], hp=spec["hp"], score=spec["score"],
            material=spec["material"], tier=spec["tier"], weak_bonus=50,
        )
        if spec.get("weak_damage"):
            node_entry["weak_damage"] = spec["weak_damage"]
        if spec.get("flinch"):
            node_entry["flinch"] = nid
        nodes.append(node_entry)

        if spec.get("peddler_after"):
            pmeta = annot["peddler"]
            pb, pe = pmeta["window"]
            pwin = [dict(begin=pb, end=pe, kind="civilian", node=idx + 1, hit="wave_06")]
            clips["peddler_06"] = dict(
                media="c1_w_peddler", sha256=pmeta["sha256"], frames=pmeta["frames"],
                start=max(0, pb - 6), in_anchor="dukou", out_anchor="dukou",
                next="wave_06", windows=pwin, forbearance_bonus=500,
                voice_cues=[dict(frame=max(0, pb - 4), voice="qingping/civilian",
                                 subtitle="青萍  货郎经过！收剑别误伤，等他跑过去。", priority=2)],
            )
            write_mask(dukou_dir / "peddler_06.mask", pmeta["sha256"], masks_cache["peddler"], pwin)

    level = dict(
        version=1, ruleset="linyuan", title="临渊御剑", fps=24, size=[1280, 720],
        first="wave_01", selectable_difficulty=True, allow_special=True,
        ambience="dukou_air", progress_prefix="机关兽 ",
        location="临渊江 · 九曲渡",
        briefing="左键出剑 · 右键或 R 收剑 · 空格或中键万剑归宗",
        cleared="集市已定",
        nodes=nodes, clips=clips,
        plate=dict(media="c1_dukou_plate", sha256=plate_sha, frames=plate_frames),
        materials=annot["materials"], materials_sha256=annot["materials_sha256"],
    )
    write(dukou_dir / "level.json", level)


def build_drama():
    drama_path = WORLD / "drama.json"
    drama = json.loads(drama_path.read_bytes()) if drama_path.is_file() else {}
    for stale in ("c1_dukou_plate", "c1_boss_p1_a", "c1_boss_p1_b", "c1_boss_p1_c"):
        drama.pop(stale, None)
    sel_dir = PRODUCTION / "ch1_selections"
    for p in sorted(sel_dir.glob("*.json")):
        sel = json.loads(p.read_bytes())
        tid = sel["id"]
        if tid.startswith(("c1_w_", "c1_dukou_")):
            continue
        drama[tid] = dict(sha256=sel["sha256"], frames=sel["frames"], speed=sel.get("edit_speed", 1.0))
    write(drama_path, drama)
    return drama


def build_campaign(annot, drama):
    # S1..S7 Chapter 1 Campaign
    boss_steps = {}
    # Phase 1: 6 alternating left/right shoulder canisters on locked-wide shots
    p1_voices = {
        "p1_1": ("qingping/canisters", "青萍  背上那两只琥珀燃料罐！哪边发亮就打哪边！"),
    }
    for i in range(1, 7):
        sid = f"p1_{i}"
        left_side = (i % 2 == 1)
        take = "c1_boss_p1_l" if left_side else "c1_boss_p1_r"
        zone = "canister_l" if left_side else "canister_r"
        nf = annot["boss"][take]["frames"]
        win = [10, max(24, nf - 24)]
        resp = "c1_boss_p1_flinch_l" if left_side else ("c1_boss_p1_flinch_r" if i < 6 else "c1_boss_break")
        nxt = f"p1_{i + 1}" if i < 6 else "p2_1"
        prompt = ("瞄准饕餮左肩发光琥珀罐！" if left_side else
                  ("击碎右肩琥珀罐！" if i == 6 else "瞄准饕餮右肩发光琥珀罐！"))
        step = dict(
            take=take, start_frame=0, end_frame=nf,
            window=win, zones=[zone], answer=zone,
            prompt=prompt,
            outcomes={
                zone: dict(points=300, response=resp, next=nxt),
                "miss": dict(damage=1, next=sid),
                "timeout": dict(damage=1, next=sid),
            },
        )
        if sid in p1_voices:
            v, sub = p1_voices[sid]
            step["cues"] = [dict(voice=v, subtitle=sub, begin=2, end=win[0] + win[1])]
        boss_steps[sid] = step

    # Phase 2: 3 fireballs with early/mid/late intercept windows
    p2 = annot["boss"]["c1_boss_p2_launch"]
    b0, b1 = p2["begin"], p2["end"]
    span = max(9, b1 - b0)
    t1 = b0 + span // 3
    t2 = b0 + (2 * span) // 3
    iwins = [
        [b0, t1, "c1_boss_p2_intercept_early"],
        [t1, t2, "c1_boss_p2_intercept_mid"],
        [t2, b1, "c1_boss_p2_intercept_late"],
    ]
    for k in range(1, 4):
        sid = f"p2_{k}"
        hit_out = dict(points=400, next=f"p2_{k + 1}" if k < 3 else "p3")
        if k == 3:
            hit_out["transition"] = "c1_boss_expose"
            hit_out["transition_voice"] = "qingping/mouth"
            hit_out["transition_subtitle"] = "青萍  嘴张开了！瞄准口内核心！"
        step = dict(
            take="c1_boss_p2_launch", window=[b0, b1 - b0], projectile=True,
            zones=["fireball"], answer="fireball",
            intercept_windows=iwins,
            prompt="拦截饕餮吐出的火球！",
            outcomes={
                "fireball": hit_out,
                "miss": dict(damage=1, response="c1_boss_p2_impact", next=sid),
                "timeout": dict(damage=1, response="c1_boss_p2_impact", next=sid),
            },
        )
        if k == 1:
            step["cues"] = [dict(voice="qingping/fireball", subtitle="青萍  火球！迎着打碎它！", begin=max(0, b0 - 4), end=b1)]
        boss_steps[sid] = step

    # Phase 3: Open-maw core (boss_hp: 3 -> easy 2, normal 3, hard 4)
    p3_frames = annot["boss"]["c1_boss_p3"]["frames"]
    boss_steps["p3"] = dict(
        take="c1_boss_p3", window=[8, p3_frames - 24],
        zones=["core"], answer="core",
        boss_hp=3, thunder_strike=True,
        flinch_response="c1_boss_p3_flinch", kill_response="c1_boss_kill",
        prompt="击碎饕餮口内核心！",
        cues=[dict(voice="qingping/mouth", subtitle="青萍  快，就在它喉咙里面！", begin=4, end=p3_frames - 24)],
        outcomes={
            "core": dict(points=600, purified=1, next="@complete"),
            "miss": dict(damage=1, next="p3"),
            "timeout": dict(damage=1, next="p3"),
        },
    )

    mvp = json.loads((WORLD / "mvp.json").read_bytes())["chapters"][0]["stages"]
    mvp_stages = {s["id"]: s for s in mvp}
    yunyi_trial = copy.deepcopy(mvp_stages["save_yunyi"]["trial"])
    yunyi_trial["steps"][yunyi_trial["first"]]["highlight"] = True
    # Trim pure-story S1, S4, S7 cleanly so total non-interactive duration stays <= 75s
    stages = [
        dict(
            id="opening", type="film", music="jiuqu_story",
            takes=[
                dict(id="c1_01_vista", end_frame=84),
                dict(id="c1_02_descend", end_frame=84),
                dict(id="c1_03_market", end_frame=84),
                mvp_stages["noodle"]["takes"][0],
                dict(id="c1_05_redeye", end_frame=108, voice="qingping/redeye",
                     subtitle="青萍  山顶那个圈刚才闪了一下……江对岸的机关兽眼睛全红了！"),
                dict(id="c1_06_leap", end_frame=72),
            ],
        ),
        dict(id="dukou_card", type="card", text="九曲渡 · 集市", milliseconds=1200),
        dict(id="dukou", type="encounter", level="dukou", music="dukou_battle", linyuan=True, allow_special=True),
        dict(id="save_yunyi", type="trial", trial=yunyi_trial),
        mvp_stages["yunyi_reply"],
        dict(
            id="conch", type="film", music="jiuqu_story",
            takes=[
                dict(id="c1_13_conch", voice="laojiu/conch",
                     subtitle="老酒（传音螺）  陆沉！天机峰那道封印在泄能，竹海里全是红眼兽，东线过不去了……"),
                dict(id="c1_14_core", end_frame=96, voice="qingping/core",
                     subtitle="青萍  它不是突然发疯的。那个圆环在往周围的所有核心灌能量。"),
                dict(id="c1_15_lookup", end_frame=72),
            ],
        ),
        dict(id="bamboo_card", type="card", text="九曲渡 · 后山竹海", milliseconds=1200),
        dict(id="bamboo", type="encounter", level="bamboo", music="battle", linyuan=True, allow_special=True),
        dict(id="shoal_card", type="card", text="临渊江 · 浅滩", milliseconds=1200),
        dict(id="taotie_enter", type="film", music="boss_taotie",
             takes=[dict(id="c1_boss_enter")]),
        dict(id="taotie", type="trial", music="boss_taotie", linyuan=True, allow_special=True,
             trial=dict(first="p1_1", steps=boss_steps)),
        dict(
            id="xuanwu_outro", type="film", music="jiuqu_outro",
            takes=[
                dict(id="c1_20_smoke", end_frame=96),
                dict(id="c1_21_run", end_frame=72),
                dict(id="c1_22_board", end_frame=96, voice="qingping/xuanwu",
                     subtitle="青萍  坐稳了！玄武驮着咱们一直往天机峰渡过去。"),
            ],
        ),
        dict(id="end_card", type="card", text="第一章  完", milliseconds=1500),
    ]
    write(WORLD / "chapter_one.json", dict(title="临渊御剑", chapters=[
        dict(id="chapter_one", heading="第一章  九曲渡", stages=stages),
    ]))
    write(WORLD / "start.json", dict(campaign="chapter_one"))


def main():
    annot = json.loads((PRODUCTION / "ch1_annotations.json").read_bytes())
    masks_cache = pickle.loads((PRODUCTION / "ch1_masks_cache.pkl").read_bytes())
    build_dukou(annot, masks_cache)
    drama = build_drama()
    build_campaign(annot, drama)
    report = validate_ch1(ROOT)
    print("Assembled Chapter 1 successfully:", json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
