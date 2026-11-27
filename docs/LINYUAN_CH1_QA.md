# 《临渊御剑》第一章：九曲渡 — 开发与验收报告（LINYUAN_CH1_QA）

## 1. 交付总览

- **章节标题**：`《临渊御剑》 第一章  九曲渡`（默认入口：[start.json](file:///D:/video_game/worlds/linyuan/start.json) -> `chapter_one`）
- **保留兼容入口**：`--campaign mvp`（[mvp.json](file:///D:/video_game/worlds/linyuan/mvp.json)）保留全部 26 条自动化回归用例；`Changan.exe` 与 CTest 双引擎测试套件保持全绿。
- **独立离线发行包**：
  - 解压目录：[dist/Linyuan-Chapter1](file:///D:/video_game/dist/Linyuan-Chapter1)（共 `325` 个文件，`480.41 MiB`）
  - 压缩包：`dist/Linyuan-Chapter1-Windows-x64.zip`（`449.26 MiB`，经 `zipfile.testzip()` 全校验无损坏，含 `manifest.json` 全量 SHA-256）

## 2. 资产与静态规范检查

| 检查脚本 | 结果 | 关键统计 |
|---|---|---|
| [check_linyuan_ch1.py](file:///D:/video_game/tools/player/check_linyuan_ch1.py) | PASS (exit 0) | 纯剧情播放 `55.45s`（`<= 75s`），S2 `11` 剑 + S5 `13` 剑 + S6 Boss `12` 剑，全部 MP4 `1280x720@24fps H.264 yuv420p bf=0 + 48kHz stereo AAC`、全部 `DCM1` 遮罩（含 `dukou/*.weak.mask` 禁止越界至左棚防呆检查）、36x64 材质网格与 Boss 16 顶点多边形 SHA-256 绑定通过 |
| [check_linyuan.py](file:///D:/video_game/tools/player/check_linyuan.py) | PASS (exit 0) | `stages=5`, `bamboo_nodes=10`, `bamboo_media=31`, `story_media=32` |
| `validate_soundbank` ([package_linyuan.py](file:///D:/video_game/tools/player/package_linyuan.py)) | PASS (exit 0) | `special`/`dukou_air`/全部 foley & ambience 均为 48kHz 16-bit 立体声 WAV；27 条中文配音（1-ch 48kHz 16-bit）与 7 条 ACE-Step 配乐齐备 |

## 3. CTest 单元测试与跨引擎回归

- `ctest --test-dir build-linyuan -C Release --output-on-failure`：**2 / 2 PASS**
  - `opening_rules` (`0.35s`)
  - `linyuan_rules` (`0.11s`，含 `hold_frame`、`allow_special` 万剑归宗 0 耗剑、`forbearance_bonus` 洁净加分/提前惊扰作废、三档难度动态归匣缩放)
- `Changan.exe --level m0 --scenario normal`：**PASS** (`ok=True`, `shots=5`, `hits=5`)
- `test_linyuan_mvp.py --campaign mvp --jobs 6`：**26 / 26 PASS**（涵盖 `early`、`scan-early`、`normal`、`late`、`needle-late`、`needle-miss`、`needle-repeat`、`raft-miss`、`raft-timeout`、`empty`、`ordinary-timeout`、`early-reload`、`frozen-input`、`story-miss`、`story-timeout`、`retry`、`story-civilian`、`story-first`、`story-last`、`story-boundaries`、`story-pause`、`shoulder`、`body`、`needle-core-closed`、`give-up`、`reload-held`）

## 4. 第一章三档难度全通实测（`--campaign chapter_one`）

| 难度 | 总耗时 (s) | 总出剑（不含 S3 剧情剑） | 命中 | 净杀敌数 | S2 弱点回剑 | 剩余剑穗 | 总分 | 纯剧情占比 (`55.45s / 总耗时`) |
|---|---|---|---|---|---|---|---|---|
| `easy` | `163.76` | `35`（Taotie P3 `2 HP`） | `35` | `23` | `11` | `5` | `12728` | `33.86%` |
| `normal` | `165.47` | `36`（S2 `11` + S5 `13` + S6 `12`） | `36` | `23` | `11` | `3` | `12794` | `33.51%` |
| `hard` | `167.65` | `37`（Taotie P3 `4 HP`） | `37` | `23` | `11` | `3` | `12852` | `33.07%` |

- 全难度均满足纯剧情 `<= 75s` 且 `<= 35%` 预算；S2 与 S5 击毁转场均流畅接回空场母版（S2 使用 `1.55x` 物理退回遮挡片、`<= 1.50s`，S6 Boss 完整播放并羽化贴合 `K_TAOTIE_1/2/3/END`）。

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

- 将 `dist/Linyuan-Chapter1` 完整复制至临时目录并在无 `--root` 参数下执行 `Linyuan.exe --level dukou --smoke <temp> --scenario normal`：
  - 返回码 `0`，`playthrough.json` 报告 `ok=True`, `shots=11`, `hits=11`。

## 7. 试玩反馈深度打磨（UI、视频接缝与弱点高精度专项）

- **视频接缝与视觉洁净度**：移除 `stabilize_to_plate` 全屏差分涂抹与端帧暴力腰斩；补绘并重制 20 余条 H3 视频（双翼白羽天空毕方、无爆炸干扰货郎、无大剑 `c1_15_lookup`、无直升机 `c1_13_conch`、背壳无角 `c1_20_smoke`/`c1_21_run`、锁广角左右交替 `c1_boss_p1_l/r` 与全长调速+端帧羽化的 15 条物理退回遮挡击毁片）。
- **高精度弱点与防误判**：采用同片段空场时序中值基底 + 空间车道 ROI + 机身内胸囊/肩罐子区过滤与高阈值开闭操作，将集市 11 波弱点锁定 100% 收敛到怪物胸囊/肩罐，彻底清除布棚/蒸笼/灯笼上的假圈及 `peddler_06` 越界误判（货郎遮罩紧凑至 `fill=32%`），Boss P1 多边形严格锁定双肩罐（`y>=88`）。
- **UI/VFX/难度强化**：新增主菜单左栏三档直选难度卡片（`1 简单 / 2 普通 / 3 困难` 即时生效）与 `F1/F2/F3` 关卡直达（`F3` 预充剑意）；实装高对比暗底双环剑锋锁定（`drawLinyuanTargetLock`）、三档准星锁定状态、十字双重剑气+弱点回剑飞弧、顶部不挡怪紧凑 HUD、Boss 战三阶段顶栏血条与反应镜头防误触。
- **独立玩家 Agent 二轮复测**：通过 57 张全流程实机 `--capture` 截图逐帧审计与三档全通校验。
