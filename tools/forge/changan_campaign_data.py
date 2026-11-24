"""Author chapter graphs from the approved narrative and tracked H3 performances."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

WORLD = Path(__file__).resolve().parents[2] / "worlds/changan"
END = "@complete"


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def film(stage, *takes):
    shots = [{"id": t} if isinstance(t, str) else {"id": t[0], "subtitle": t[1]} for t in takes]
    return {"id": stage, "type": "film", "takes": shots}


def section(identifier, steps):
    return {"id": identifier, "type": "trial", "trial": {"first": next(iter(steps)), "steps": steps}}


def threat(
    take,
    answer,
    prompt,
    repeat,
    following,
    *,
    points=100,
    begin=30,
    length=35,
    protected=(),
    wrong=(),
    expose=False,
    highlight=False,
    purified=0,
):
    zones = [*protected, answer, *wrong]
    attempts = {"miss": {"next": repeat}, "timeout": {"next": repeat, "damage": 1}}
    attempts[answer] = {"next": following, "points": points, "purified": purified}
    for name in [*protected, *wrong]:
        attempts[name] = {"next": repeat, "damage": 1}
    for name in protected:
        attempts[name]["civilian"] = True
    return {
        "take": take,
        "prompt": prompt,
        "answer": answer,
        "window": [begin, length],
        "zones": zones,
        "outcomes": attempts,
        "expose": expose,
        "highlight": highlight,
    }


def chapter_one():
    opening = json.loads((WORLD / "first_night.json").read_bytes())["chapters"][0]
    opening["stages"][-1] = film(
        "meet_aying", ("aying_help", "阿萤　“我能帮你们找到它们。”"), "meeting_reply"
    )
    opening["stages"] += [
        section(
            "fireflies_reveal",
            {
                "glimmer": threat(
                    "ying_reveal",
                    "wisp",
                    "跟着萤火，施符净化显形的青火",
                    "glimmer",
                    END,
                    protected=("aying",),
                    begin=48,
                    length=38,
                    purified=1,
                )
            },
        ),
        {"id": "spirit_relay", "type": "encounter", "level": "m0"},
        film("flying_carp", ("carp_gate", "朱雀门上方，一尾巨鲤游出了灯海。")),
        section(
            "carp_lantern",
            {
                "flame": threat(
                    "carp_ball",
                    "flame",
                    "拦下巨鲤吐出的青火",
                    "flame",
                    "scale",
                    begin=45,
                    length=40,
                    points=150,
                ),
                "scale": threat(
                    "carp_tail",
                    "scale",
                    "甩尾时，瞄准背上亮起的金鳞",
                    "scale",
                    "wick",
                    begin=58,
                    length=41,
                    points=300,
                    expose=True,
                ),
                "wick": threat(
                    "carp_wick_clean",
                    "wick",
                    "最后一箭，净化腹中的烛火",
                    "wick",
                    END,
                    begin=38,
                    length=41,
                    points=500,
                    expose=True,
                    purified=1,
                ),
            },
        ),
        film("westward", ("carp_small", "阿萤　“玄烛……他在西市。”")),
    ]
    return opening


def mirrors():
    def mirror(take, answer, extra, good):
        step = threat(
            take,
            answer,
            "萤火伴着真的阿萤　·　击碎两面假镜",
            "",
            END,
            begin=24,
            length=48,
            protected=("middle",),
            wrong=extra,
        )
        step["story_shot"] = True
        for key in step["outcomes"]:
            step["outcomes"][key] = (
                {"next": END, "response": "west_prophecy"} if key not in good else good[key]
            )
        return step

    return section(
        "hall_of_mirrors",
        {
            "three": mirror(
                "mirrors",
                "left",
                ("right",),
                {
                    "left": {"next": "left_broken", "points": 500},
                    "right": {"next": "right_broken", "points": 500},
                },
            ),
            "left_broken": mirror(
                "mirror_left_gone",
                "right",
                (),
                {"right": {"next": END, "points": 500, "response": "true_mirror"}},
            ),
            "right_broken": mirror(
                "mirror_right_gone",
                "left",
                (),
                {"left": {"next": END, "points": 500, "response": "true_mirror"}},
            ),
        },
    )


def duel(take, answer, prompt, repeat, following, *, guard):
    step = threat(
        take, answer, prompt, repeat, following, begin=28, length=60, wrong=(guard,), points=500, purified=1
    )
    step["guards"] = [guard]
    step["zone_windows"] = {guard: [28, 44], answer: [44, 120]}
    return step


def protect(stage, people):
    steps = {}
    for i, take in enumerate(people):
        key = f"person_{i + 1}"
        following = f"person_{i + 2}" if i + 1 < len(people) else END
        steps[key] = threat(
            take,
            "wick",
            "只取灯芯，避开百姓",
            key,
            following,
            protected=("civilian",),
            begin=30,
            length=42,
            points=100,
            purified=1,
        )
        steps[key]["outcomes"]["civilian"]["next"] = following
    result = section(stage, steps)
    result["trial"]["rescue_bonus"] = 1000
    return result


def chapter_two():
    return {
        "id": "west_market",
        "heading": "第二章　西市，幻术坊",
        "stages": [
            film("west_market_opens", ("market", "入夜的西市，皮影台上的纸人自己动了起来。")),
            section(
                "puppet_stage",
                {
                    "crane": threat(
                        "paper_cranes", "crane", "击散从纸堆里飞出的纸鹤", "crane", "leather", purified=1
                    ),
                    "leather": duel(
                        "shadow_duel",
                        "pin",
                        "等盾面移开，瞄准皮影头部的铜钉",
                        "leather",
                        "parasol",
                        guard="shield",
                    ),
                    "parasol": duel(
                        "umbrella_turn", "hub", "避开伞面，等伞骨收拢", "parasol", END, guard="shield"
                    ),
                },
            ),
            protect("west_possessions", ["possession", "west_weaver", "west_musician"]),
            mirrors(),
            section(
                "thousand_faces",
                {
                    "string": threat(
                        "puppet_boss",
                        "thread",
                        "先断操偶丝线",
                        "string",
                        "mask",
                        begin=18,
                        length=41,
                        highlight=True,
                    ),
                    "mask": threat(
                        "puppet_boss",
                        "mask",
                        "趁换面时击中面具",
                        "mask",
                        "heart",
                        begin=45,
                        length=39,
                        highlight=True,
                    ),
                    "heart": threat(
                        "puppet_boss",
                        "heart",
                        "击中胸前的机关",
                        "heart",
                        END,
                        begin=60,
                        length=35,
                        points=500,
                        purified=1,
                        expose=True,
                    ),
                },
            ),
            film(
                "master_revealed",
                ("marionette_boy", "面具落了。戏子深深一揖。"),
                ("west_prophecy", "玄烛　“你终于醒了，我的灯。”"),
            ),
        ],
    }


def chapter_three():
    heads = [f"head_{i}" for i in range(1, 10)]
    route = [0, 4, 8, 3, 6, 1, 5, 2, 7]
    dragon = {}
    for i, index in enumerate(route):
        key = f"signal_{i + 1}"
        following = f"signal_{i + 2}" if i < 8 else END
        target = heads[index]
        wrong = [h for h in heads if h != target]
        step = threat(
            "dragon",
            target,
            f"九首龙舟　·　击中第 {i + 1} 盏亮起的灯",
            key,
            following,
            begin=20,
            length=39,
            protected=("aying",),
            wrong=wrong,
            highlight=True,
            points=500 if i == 8 else 100,
            purified=int(i == 8),
        )
        for h in wrong:
            step["outcomes"][h] = {"next": key, "response": "dragon_recoil"}
        dragon[key] = step
    return {
        "id": "qujiang",
        "heading": "第三章　曲江池，夜船",
        "stages": [
            film(
                "on_the_river",
                ("river", "阿萤　“如果我真是他的灯，你还会信我吗？”"),
                ("river_look", "沈砚没有回答。他把河灯轻轻推向她。"),
            ),
            section(
                "lotus_ferry",
                {
                    "light": threat(
                        "lotus_water",
                        "flower",
                        "水上有妖　·　瞄准莲花河灯",
                        "light",
                        "flame",
                        begin=23,
                        length=42,
                        purified=1,
                    ),
                    "flame": threat(
                        "lotus_water",
                        "flame",
                        "拦截水面上的青火",
                        "flame",
                        END,
                        begin=44,
                        length=40,
                        points=150,
                    ),
                },
            ),
            film("dragon_takes_aying", ("river_capture", "青火裹住阿萤，将她卷上龙舟。"), "river_pass"),
            section(
                "river_chase",
                {
                    "parasol": duel(
                        "umbrella_turn", "hub", "追上龙舟　·　击中伞骨", "parasol", "wisp", guard="shield"
                    ),
                    "wisp": threat(
                        "lotus_water",
                        "flame",
                        "打散拦路的青火",
                        "wisp",
                        END,
                        begin=42,
                        length=40,
                        points=150,
                    ),
                },
            ),
            section("nine_lanterns", dragon),
            film(
                "toward_the_tower",
                ("river_sink", "灯灭船沉，青光却往大雁塔去了。"),
                ("peizhao_arrives", "裴照　“走。”"),
            ),
        ],
    }


def story_shot(take, answer, prompt, hit, miss, protected=()):
    step = threat(take, answer, prompt, "shot", END, begin=24, length=48, protected=protected)
    step["story_shot"] = True
    for key in step["outcomes"]:
        step["outcomes"][key] = {
            "next": END,
            "response": hit if key == answer else miss,
            "points": 1000 if key == answer else 0,
        }
    return {"shot": step}


def chapter_four():
    return {
        "id": "pagoda",
        "heading": "第四章　大雁塔",
        "stages": [
            film("pagoda_doors", ("tower_door", "塔门紧闭。石狮的眼睛亮了起来。")),
            section(
                "pagoda_stairs",
                {
                    "lamp": threat(
                        "tower_crow",
                        "lamp",
                        "阿萤不在，先射亮经卷旁的灯",
                        "lamp",
                        "crow",
                        begin=12,
                        length=48,
                        highlight=True,
                    ),
                    "crow": threat(
                        "tower_crow",
                        "crow",
                        "墨鸦现形　·　击中纸翼",
                        "crow",
                        END,
                        begin=36,
                        length=42,
                        purified=1,
                    ),
                },
            ),
            section(
                "guard_the_commander",
                story_shot(
                    "flock", "crow", "替裴照击散墨鸦", "flock_scatter", "flock_escape", ("commander",)
                ),
            ),
            film("wounded_commander", ("peizhao_rest", "裴照　“我在这里守着，你去把她带回来。”")),
            section(
                "stone_cubs",
                {
                    "cub": threat(
                        "stone_cub",
                        "crack",
                        "石狮跃起时，瞄准发亮的裂缝",
                        "cub",
                        END,
                        begin=32,
                        length=48,
                        points=500,
                        purified=1,
                    )
                },
            ),
            section(
                "stone_guardian",
                {
                    "left": threat(
                        "guardian",
                        "left_crack",
                        "击中左前爪上的金色裂缝",
                        "left",
                        "right",
                        begin=26,
                        length=44,
                        highlight=True,
                    ),
                    "right": threat(
                        "guardian",
                        "right_crack",
                        "击中另一侧的裂缝",
                        "right",
                        "pearl",
                        begin=36,
                        length=41,
                        highlight=True,
                    ),
                    "pearl": threat(
                        "guardian",
                        "pearl",
                        "石狮开口了　·　击中灯珠",
                        "pearl",
                        END,
                        begin=46,
                        length=39,
                        points=500,
                        expose=True,
                        purified=1,
                    ),
                },
            ),
            film(
                "chains_to_the_palace",
                "lion_statue",
                "tower",
                ("tower_chain", "青色灯链从塔顶绷向太极宫。沈砚转身下塔，追着灯火而去。"),
            ),
        ],
    }


def chapter_five():
    lamps = ["left", "middle", "low"]
    wards = {
        "fire": threat(
            "palace_fire", "flame", "拦下玄烛的青火", "fire", "ward_1", begin=32, length=36, points=150
        )
    }
    for i, lamp in enumerate(lamps):
        key = f"ward_{i + 1}"
        wards[key] = threat(
            "palace",
            lamp,
            f"玄烛的护灯　·　第 {i + 1} 盏",
            key,
            f"ward_{i + 2}" if i < 2 else END,
            begin=20 + i * 8,
            length=39,
            highlight=True,
            points=200,
        )
    return {
        "id": "palace",
        "heading": "第五章　太极宫，万灯鬼门",
        "stages": [
            film("the_lantern_maker", ("wife", "千年前。玄烛　“上元节，我带你去看灯。”")),
            film("imperial_gate", ("palace", "灯链尽头，阿萤被困在鬼门之前。")),
            section(
                "ride_of_lanterns",
                {
                    "fox": threat(
                        "fox_mask",
                        "mask",
                        "在狐火成形前击中白色面具",
                        "fox",
                        "rider",
                        points=500,
                        purified=1,
                    ),
                    "rider": threat(
                        "cavalry",
                        "wick",
                        "走马灯骑兵逼近　·　击中腹中灯芯",
                        "rider",
                        END,
                        points=500,
                        purified=1,
                    ),
                },
            ),
            protect("palace_possession", ["palace_servant"]),
            section("three_guard_lamps", wards),
            section(
                "release_the_chains",
                {
                    "far": threat(
                        "palace_chain",
                        "chain_a",
                        "斩断远端灯链，避开阿萤",
                        "far",
                        "near",
                        protected=("aying",),
                        highlight=True,
                    ),
                    "near": threat(
                        "palace_chain",
                        "chain_b",
                        "击碎靠近灯笼的链环",
                        "near",
                        END,
                        protected=("aying",),
                        highlight=True,
                        points=500,
                    ),
                },
            ),
            film("borrowed_light", ("aying_lends", "阿萤　“沈砚，接住。这一点光，我借给你。”")),
            section(
                "final_story_arrow",
                story_shot(
                    "final_wick", "wick", "按普通射击键，将这一点光送入灯芯", "wick_shattered", "wick_mercy"
                ),
            ),
            film(
                "fireflies_at_dawn",
                ("gate_end", "玄烛　“原来，你早就看见了。”"),
                ("farewell", "阿萤　“明年上元，你也要记得点灯。”"),
                "palace_dawn",
            ),
            film("one_year_later", ("epilogue", "一年后的上元夜。沈砚　“今年的灯，很好看。”")),
        ],
    }


def score_and_cast(chapters):
    themes = [
        ("city_night", "festival"),
        ("illusion_market", "market_battle"),
        ("qujiang", "river_battle"),
        ("pagoda", "tower_battle"),
        ("palace", "palace_battle"),
    ]
    overrides = {
        "meet_aying": "fireflies",
        "westward": "fireflies",
        "master_revealed": "lantern_master",
        "carp_lantern": "guardian_battle",
        "thousand_faces": "guardian_battle",
        "nine_lanterns": "guardian_battle",
        "stone_guardian": "guardian_battle",
        "the_lantern_maker": "lantern_master",
        "three_guard_lamps": "xuanzhu_battle",
        "release_the_chains": "xuanzhu_battle",
        "borrowed_light": "fireflies",
        "final_story_arrow": "farewell",
        "fireflies_at_dawn": "farewell",
        "one_year_later": "credits",
    }
    voices = {
        "patrol": "shenyan/patrol",
        "lantern_warning": "shenyan/warning",
        "meeting_reply": "peizhao/meeting",
        "market": "peizhao/west",
        "west_prophecy": "xuanzhu/return",
        "river": "aying/question",
        "river_look": "shenyan/river",
        "peizhao_arrives": "peizhao/walk",
        "tower_door": "peizhao/doors",
        "peizhao_rest": "peizhao/rest",
        "tower_chain": "shenyan/tower",
        "wife": "xuanzhu/promise",
        "aying_lends": "aying/lend",
        "gate_end": "xuanzhu/release",
        "farewell": "aying/farewell",
        "epilogue": "shenyan/epilogue",
        "palace": "xuanzhu/summon",
    }
    lines = {}
    for sheet in ("guard_voices", "voice_audition"):
        cast = json.loads((WORLD / "production" / (sheet + ".json")).read_bytes())
        for actor, spec in cast.items():
            for key, text, _ in spec["lines"]:
                name = {"aying": "阿萤", "xuanzhu": "玄烛", "peizhao": "裴照", "shenyan": "沈砚"}[actor]
                lines[actor + "/" + key] = f"{name}　“{text}”"
    reactions = {
        ("ying_reveal", "wisp"): "ying_clear",
        ("carp_ball", "flame"): "carp_interrupt",
        ("carp_tail", "scale"): "carp_shimmer",
        ("paper_cranes", "crane"): "crane_falls",
        ("shadow_duel", "pin"): "leather_bows",
        ("umbrella_turn", "hub"): "parasol_closes",
        ("puppet_boss", "thread"): "threads_loose",
        ("puppet_boss", "mask"): "mask_cracks",
        ("lotus_water", "flower"): "lotus_rests",
        ("lotus_water", "flame"): "flame_clear",
        ("stone_cub", "crack"): "stone_cub_rests",
        ("guardian", "left_crack"): "guardian_reacts",
        ("cavalry", "wick"): "cavalry_rests",
        ("fox_mask", "mask"): "fox_calm",
        ("palace_chain", "chain_b"): "palace_chain_falls",
        ("palace_fire", "flame"): "master_fire_clear",
        ("west_weaver", "wick"): "weaver_freed",
        ("west_musician", "wick"): "musician_freed",
        ("palace_servant", "wick"): "servant_freed",
        ("possession", "wick"): "citizen_freed",
        ("tower_crow", "lamp"): "crow_lamp_lit",
    }
    for chapter, (calm, battle) in zip(chapters, themes, strict=True):
        for stage in chapter["stages"]:
            stage["music"] = overrides.get(stage["id"], calm if stage["type"] == "film" else battle)
            for shot in stage.get("takes", []):
                voice = voices.get(shot["id"])
                if voice:
                    shot.update(voice=voice, subtitle=lines[voice])
            for step in stage.get("trial", {}).get("steps", {}).values():
                answer = step["answer"]
                reaction = reactions.get((step["take"], answer))
                if reaction:
                    step["outcomes"][answer]["response"] = reaction


def extended_edit(chapters, speaking=(), coda=False):
    # Each replacement is a filmed continuation from the preceding performance.
    inserts = {
        "city": ["festival_rooftops"],
        "patrol": ["patrol_stalls"],
        "blue_flame": ["white_robe_watch"],
        "meeting_reply": ["aying_lands"],
        "carp_small": ["little_carp_sky", "west_blue_row"],
        "market": ["market_drummer", "paper_wakes"],
        "marionette_boy": ["player_bows"],
        "west_prophecy": ["xuanzhu_vanishes"],
        "river": ["river_passing_lamps"],
        "river_look": ["river_lantern_gift"],
        "river_capture": ["river_blue_wake"],
        "river_sink": ["river_empty_deck"],
        "tower_door": ["pagoda_steps", "tower_scrolls"],
        "peizhao_rest": ["tower_pillar"],
        "tower": ["tower_roof_view"],
        "tower_chain": ["tower_departure"],
        "wife": ["artisan_worktable", "memory_firefly"],
        "palace": ["palace_avenue"],
        "gate_end": ["master_reaches"],
        "farewell": ["aying_fireflies"],
        "palace_dawn": ["city_wakes"],
        "epilogue": ["empty_lantern"],
    }
    if coda:
        inserts.update(
            {
                "lantern_warning": ["lantern_eyes"],
                "market": ["market_drummer", "market_silk", "paper_wakes", "screen_silhouette"],
                "mirror_hall_entry": ["mirror_reflection"],
                "marionette_boy": ["player_bows", "mask_abandoned"],
                "west_prophecy": ["ying_doubts", "xuanzhu_vanishes"],
                "river": ["river_passing_lamps", "boat_pole"],
                "river_look": ["river_lantern_gift", "lotus_ripples"],
                "river_capture": ["river_blue_wake", "prow_splash"],
                "river_pass": ["water_trail"],
                "river_sink": ["river_empty_deck", "pagoda_distance"],
                "tower_door": ["pagoda_steps", "lion_eyes", "tower_scrolls", "ink_on_wall"],
                "peizhao_rest": ["tower_pillar", "commander_bandage", "tower_vigil"],
                "lion_statue": ["stone_hush"],
                "tower_chain": ["tower_departure", "chain_over_tiles"],
                "wife": ["artisan_worktable", "split_bamboo", "memory_firefly", "wife_hand"],
                "palace": ["palace_avenue", "palace_wind"],
                "gate_end": ["master_reaches", "gate_folds"],
                "farewell": ["aying_fireflies", "last_sleeve"],
                "palace_dawn": ["city_wakes", "dawn_market"],
                "epilogue": ["empty_lantern", "festival_returns"],
            }
        )
    # Four separate filmed stances per enemy. Stronger lanterns require multiple
    # confirmed hits while a single film keeps playing and its region keeps moving.
    waves = {
        "fireflies_reveal": (4, [2]),
        "carp_lantern": (4, [1, 3, 2]),
        "puppet_stage": (4, [1, 2, 3]),
        "thousand_faces": (4, [2, 2, 2]),
        "lotus_ferry": (4, [3, 1]),
        "river_chase": (4, [3, 1]),
        "pagoda_stairs": (4, [1, 2]),
        "stone_cubs": (4, [3]),
        "stone_guardian": (4, [2, 2, 3]),
        "ride_of_lanterns": (4, [3, 3]),
        "three_guard_lamps": (2, [1, 2, 2, 2]),
        "release_the_chains": (3, [2, 2]),
    }
    filmed = json.loads((WORLD / "production/drama_wave_jobs.json").read_bytes())
    extra_lines = {
        line[0]: line[1]
        for line in json.loads((WORLD / "production/aying_lines.json").read_bytes())["aying"]["lines"]
    }
    extra_lines["reveal"] = "看灯影，那盏灯下有两道影子。"
    callouts = {
        ("carp_lantern", "flame", 0): "fire",
        ("lotus_ferry", "flame", 0): "fire",
        ("three_guard_lamps", "ward_1", 0): "left",
        ("ride_of_lanterns", "rider", 2): "wick",
    }
    for chapter in chapters:
        if chapter["id"] == "west_market":
            at = next(i for i, stage in enumerate(chapter["stages"]) if stage["id"] == "hall_of_mirrors")
            entrance = film("mirror_gallery_entry", "mirror_hall_entry")
            entrance["music"] = "illusion_market"
            chapter["stages"].insert(at, entrance)
        if coda:
            for before, identifier, take, track in [
                ("wounded_commander", "fallen_quill", "falling_quill", "pagoda"),
                ("three_guard_lamps", "three_lamps_circle", "guard_circle", "xuanzhu_battle"),
                ("release_the_chains", "light_on_stone", "chain_shadow", "xuanzhu_battle"),
            ]:
                for i, stage in enumerate(chapter["stages"]):
                    if stage["id"] == before:
                        preview = film(identifier, take)
                        preview["music"] = track
                        chapter["stages"].insert(i, preview)
                        break
        for stage in chapter["stages"]:
            if stage["id"] == "street_lanterns":
                stage["level"] = "tutorial"
            if stage["type"] == "film":
                takes = []
                for shot in stage["takes"]:
                    if coda and shot["id"] == "river_sink":
                        takes.append({"id": "dragon_keel"})
                    takes.append(shot)
                    takes.extend({"id": k} for k in inserts.get(shot["id"], []))
                if stage["id"] == "meet_aying":
                    takes.sort(key=lambda shot: shot["id"] != "aying_lands")
                    takes.append(
                        {
                            "id": "ying_sees_west",
                            "voice": "aying/reveal",
                            "subtitle": "阿萤　“" + extra_lines["reveal"] + "”",
                        }
                    )
                for shot in takes:
                    extra = {"aying_lands": "name", "west_blue_row": "west"}.get(shot["id"])
                    if extra and "voice" not in shot:
                        shot.update(voice="aying/" + extra, subtitle="阿萤　“" + extra_lines[extra] + "”")
                    if shot["id"] in speaking and "voice" in shot:
                        shot["id"] += "_speaking"
                stage["takes"] = takes
            if stage["id"] == "nine_lanterns":
                for i, step in enumerate(stage["trial"]["steps"].values()):
                    step["take"] = "dragon_signal_" + str(i + 1)
                    step["highlight"] = False
                    step["strength"] = 2
            if stage["id"] not in waves:
                continue
            rounds, strength = waves[stage["id"]]
            trial = stage["trial"]
            original = trial["steps"]
            first = trial["first"]
            steps = {}

            def visit(name, lap):
                return name if lap == 0 else f"{name}_wave_{lap + 1}"

            for lap in range(rounds):
                for i, (key, template) in enumerate(original.items()):
                    record = deepcopy(template)
                    variant = record["take"] + "_pass_" + str(lap)
                    if lap and variant in filmed:
                        record["take"] = variant
                    # Pick the takes in which the active weak point stays in shot.
                    if record["take"] == "guardian_pass_3" and record["answer"] != "pearl":
                        record["take"] = "guardian_pass_2"
                    if record["take"] == "guardian" and record["answer"] in {"left_crack", "right_crack"}:
                        record.setdefault("zone_windows", {})[record["answer"]] = [0, 73]
                    if record["take"] == "carp_ball_pass_2" and record["answer"] == "flame":
                        record["take"] = "carp_ball"
                        record["window"][0] = 61
                    if (
                        record["take"] in {"lotus_water_pass_1", "lotus_water_pass_2"}
                        and record["answer"] == "flame"
                    ):
                        record["take"] = "lotus_water_pass_3" if lap == 1 else "lotus_water"
                        record["window"][0] = 54
                    record["strength"] = strength[i]
                    record["projectile"] = record["answer"] == "flame"
                    line = callouts.get((stage["id"], key, lap))
                    if line:
                        record.update(voice="aying/" + line, subtitle="阿萤　“" + extra_lines[line] + "”")
                    if stage["id"] in {
                        "fireflies_reveal",
                        "puppet_stage",
                        "lotus_ferry",
                        "river_chase",
                        "pagoda_stairs",
                        "stone_cubs",
                        "ride_of_lanterns",
                    }:
                        record["thunder_strike"] = record["answer"] not in {"lamp", "flame"}
                    if stage["id"] not in {"three_guard_lamps", "release_the_chains"}:
                        record["prompt"] = f"第{lap + 1}阵　" + record["prompt"]
                    for edge in record["outcomes"].values():
                        target = edge["next"]
                        edge["next"] = (
                            (visit(first, lap + 1) if lap + 1 < rounds else END)
                            if target == END
                            else visit(target, lap)
                        )
                    steps[visit(key, lap)] = record
            trial["steps"] = steps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("full", "rehearsal", "integration"), default="full")
    parser.add_argument(
        "--speakers", nargs="*", help="Override the approved localized lip-sync performances"
    )
    args = parser.parse_args()
    chapters = [chapter_one(), chapter_two(), chapter_three(), chapter_four(), chapter_five()]
    score_and_cast(chapters)
    if args.edition != "integration":
        speakers = (
            args.speakers
            if args.speakers is not None
            else ["epilogue", "wife", "peizhao_rest", "aying_lends", "west_prophecy"]
        )
        extended_edit(chapters, set(speakers), args.edition == "full")
    for name, chapter in zip(["one", "two", "three", "four", "five"], chapters):
        write(WORLD / f"chapter_{name}.json", {"title": "长安灯妖录", "chapters": [chapter]})
    write(WORLD / "campaign.json", {"title": "长安灯妖录", "chapters": chapters})
