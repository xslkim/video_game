# 《临渊御剑》第一章：九曲渡 — 开发与验收报告（LINYUAN_CH1_QA）

## 1. 交付总览

- **章节标题**：`《临渊御剑》 第一章  九曲渡`（默认入口：[start.json](file:///D:/video_game/worlds/linyuan/start.json) -> `chapter_one`）
- **保留兼容入口**：`--campaign mvp`（[mvp.json](file:///D:/video_game/worlds/linyuan/mvp.json)）保留全部 26 条自动化回归用例；`Changan.exe` 与 CTest 双引擎测试套件保持全绿。
- **独立离线发行包**：
  - 解压目录：[dist/Linyuan-Chapter1](file:///D:/video_game/dist/Linyuan-Chapter1)（共 `338` 个文件，`500.32 MiB`）
  - 压缩包：`dist/Linyuan-Chapter1-Windows-x64.zip`（`451.34 MiB`，经 `zipfile.testzip()` 全校验无损坏，含 `manifest.json` 全量 SHA-256）

## 2. 资产与静态规范检查

| 检查脚本 | 结果 | 关键统计 |
|---|---|---|
| [check_linyuan_ch1.py](file:///D:/video_game/tools/player/check_linyuan_ch1.py) | PASS (exit 0) | 纯剧情播放 `57.57s`（`<= 75s`），S2 `11` 剑 + S5 `13` 剑 + S6 Boss `12` 剑，全部 MP4 `1280x720@24fps H.264 yuv420p bf=0 + 48kHz stereo AAC`、全部 `DCM1` 遮罩、36x64 材质网格与 Boss 16 顶点多边形 SHA-256 绑定通过 |
| [check_linyuan.py](file:///D:/video_game/tools/player/check_linyuan.py) | PASS (exit 0) | `stages=5`, `bamboo_nodes=10`, `bamboo_media=31`, `story_media=33` |
| `validate_soundbank` ([package_linyuan.py](file:///D:/video_game/tools/player/package_linyuan.py)) | PASS (exit 0) | `special`/`dukou_air`/全部 foley & ambience 均为 48kHz 16-bit 立体声 WAV；27 条中文配音（1-ch 48kHz 16-bit）与 7 条 ACE-Step 配乐齐备 |

## 3. CTest 单元测试与跨引擎回归

- `ctest --test-dir build-linyuan -C Release --output-on-failure`：**2 / 2 PASS**
  - `opening_rules` (`0.32s`)
  - `linyuan_rules` (`0.11s`，含 `hold_frame`、`allow_special` 万剑归宗 0 耗剑、`forbearance_bonus` 洁净加分/提前惊扰作废、三档难度动态归匣缩放)
- `Changan.exe --level m0 --scenario normal`：**PASS** (`ok=True`, `shots=5`, `hits=5`)
- `test_linyuan_mvp.py --campaign mvp --jobs 4`：**26 / 26 PASS**（涵盖 `early`、`scan-early`、`normal`、`late`、`needle-late`、`needle-miss`、`needle-repeat`、`raft-miss`、`raft-timeout`、`empty`、`ordinary-timeout`、`early-reload`、`frozen-input`、`story-miss`、`story-timeout`、`retry`、`story-civilian`、`story-first`、`story-last`、`story-boundaries`、`story-pause`、`shoulder`、`body`、`needle-core-closed`、`give-up`、`reload-held`）

## 4. 第一章三档难度全通实测（`--campaign chapter_one`）

| 难度 | 总耗时 (s) | 总出剑（不含 S3 剧情剑） | 命中 | 净杀敌数 | 受伤 | 剩余剑穗 | 总分 | 纯剧情占比 (`57.57s / 总耗时`) |
|---|---|---|---|---|---|---|---|---|
| `easy` | `169.26` | `35`（Taotie P3 `2 HP`） | `35` | `23` | `0` | `5` | `12131` | `34.01%` |
| `normal` | `170.67` | `36`（S2 `11` + S5 `13` + S6 `12`） | `36` | `23` | `0` | `3` | `12199` | `33.73%` |
| `hard` | `172.20` | `37`（Taotie P3 `4 HP`） | `37` | `23` | `0` | `3` | `12258` | `33.43%` |

- 全难度均满足纯剧情 `<= 75s` 且 `<= 35%` 预算；S2 与 S5 击毁转场均裁至 `<= 22` 帧（`< 0.92s`，满足 `<= 1.8s` 接力上限）。

## 5. S2、S3、S6 核心分支与断点续玩验证

- **S2 九曲渡集市广场 (`--level dukou`)**：
  - `normal`：`ok=True`, `shots=11`, `hits=11`, `civilian_hits=0`, `forbearance_outcome=True`（+500）
  - `tutorial-hold`：`ok=True`, `shots=11`, `hits=11`, `tutorial_held=True`（验证 `wave_01` 在 `hold_frame` 停帧引导后出剑）
  - `peddler-miss`：`ok=True`, `shots=12`, `hits=11`, `civilian_hits=0`, `forbearance_outcome=True`（提前空挥打断无伤克制，作废奖励）
  - `peddler-hit`：`ok=True`, `shots=12`, `hits=11`, `civilian_hits=1`, `peddler_hurt=True`, `forbearance_outcome=True`
- **S3 云姨脱险 & S6 饕餮 Boss 多阶段 (`--campaign chapter_one`)**：
  - `story-timeout`：`shots=36, hits=36, damage=0, lives=3, points=11198`（云姨铁勺自救、`c1_11_miss` -> `c1_12_thanks`）
  - `story-civilian`：`shots=36, hits=36, damage=1, lives=2, points=11098`（误伤扣血并触发 `c1_12_rebuke`）
  - `boss-thunder-3`：`shots=34, hits=34, damage=0, lives=3, points=11684`（P3 使用万剑归宗 `2 HP` 爆发少消耗普通飞剑 2 剑）
  - `boss-thunder-2`：`shots=34, hits=34, damage=0, lives=3, points=11350`
  - `fireball-miss`：`shots=36, hits=36, damage=1, lives=2, points=11931`（P2 火球漏防触发 `c1_boss_p2_impact` 受伤并重开该波次至通关）
- **Checkpoint 断点续玩**：
  - `--scenario checkpoint-interrupt` 在 `bamboo_card` 结束保存 `checkpoint.json`（`"next": "bamboo"`）；
  - 新目录加载该存档继续游戏，完整依次执行 `['bamboo', 'shoal_card', 'taotie_enter', 'taotie', 'xuanwu_outro', 'end_card']` 直至 `@complete`。

## 6. 脱离仓库独立冷启动测试

- 将 `dist/Linyuan-Chapter1` 完整复制至 `%TEMP%\Linyuan-Ch1-ColdTest`，在无 `--root` 参数下执行 `Linyuan.exe --level dukou --smoke %TEMP%\Linyuan-Ch1-ColdSmoke --scenario normal`：
  - 返回码 `0`，`playthrough.json` 报告 `ok=True`, `shots=11`, `hits=11`。
