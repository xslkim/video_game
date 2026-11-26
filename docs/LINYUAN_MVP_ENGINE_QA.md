# 《临渊御剑》Windows 播放器工程验收

2026-11-26。本页记录播放器、剧情一剑和竹海接力规则的工程验证。诊断切片使用程序生成的纯色 H.264 视频、静音轨和人工矩形掩码，走正式的 SDL 输入、FFmpeg 解码、JSON 战役和结果页。它用于复现时间、分支与计分问题。成片的动作可读性、接缝、声音辨认和自愿重玩率须由正式版本的试玩报告给出。

## 从仓库根复验

在 Windows x64 上使用 Visual Studio 2022、CMake 和 vcpkg。下列命令在 PowerShell 中运行。输出目录必须是本次新建的目录，避免旧日志混入断言。

```powershell
.\tools\player\build_linyuan.ps1 -BuildOnly
ctest --test-dir build-linyuan -C Release --output-on-failure
python -X utf8 tools/player/test_linyuan_mvp.py build-linyuan/Release/Linyuan.exe build/qa/linyuan-mvp/recheck-normal --root build/qa/linyuan-mvp/diagnostic-fixture-eof --scenario normal
```

正式包交付后，直接检验包内资源。运行器会从系统临时目录启动游戏、等待进程结束，逐项检查退出码、战役阶段、输入、实际跳转、余命、出剑数和结果。第二行只跑一条失败恢复路线，适合定位故障。

```powershell
python -X utf8 tools/player/test_linyuan_mvp.py dist/Linyuan-MVP/Linyuan.exe build/qa/linyuan-mvp/package-matrix
python -X utf8 tools/player/test_linyuan_mvp.py dist/Linyuan-MVP/Linyuan.exe build/qa/linyuan-mvp/package-retry --scenario retry
python -X utf8 tools/player/test_linyuan_mvp.py dist/Linyuan-MVP/Linyuan.exe build/qa/linyuan-mvp/package-timing --timings
```

使用 `--capture` 时可录制实际画面、混音和章节事件，计时请另开一轮。真人试玩使用 `Linyuan.exe --log <新目录>`，由实时鼠标驱动可见窗口。两版反馈使用 `--feedback old` / `--feedback new`，减闪与关闭震屏使用 `--reduced-flash` / `--no-shake`。

分支矩阵允许 `--jobs 3` 有界并行。单波重试可附 `--scenario retry-wave-2`（编号 1–5、7–10。第 6 波用 `needle-miss`）。`--timings` 使用独占的无录制正常路线，输出 `normal/timing.json`。报告保留九个实际接力剪点，以及 1 柄剧情剑和 12 柄普通剑各自的输入至首次反馈提交时间。P50 取中位数、P95 取最近秩。精英进入、精英退出与藤索进入可从逐条表中单列。单机自动 SDL 鼠标输入用于比较引擎延迟。

同输入对照先记录一条路线，第二遍按其源帧与落点回放。接力逐条比较镜头、帧、输入结果、余剑和余命，剧情剑核对落点对应的结果及源帧。本机已分别从旧反馈记录和用新反馈重放，两次正常诊断路线均得 4439 分，重放断言通过。证据在 `build/qa/linyuan-mvp/same-input-feedback-check/`。

```powershell
$game = 'dist/Linyuan-MVP/Linyuan.exe'
$a = 'build/qa/linyuan-mvp/feedback-a'
$b = 'build/qa/linyuan-mvp/feedback-b'
python -c "import subprocess,sys; subprocess.run(sys.argv[1:],check=True)" $game --smoke $a --feedback old
if ($LASTEXITCODE) { throw '旧版反馈记录失败' }
python -c "import subprocess,sys; subprocess.run(sys.argv[1:],check=True)" $game --smoke $b --feedback new --input-replay $a
if ($LASTEXITCODE) { throw '新版反馈重放失败' }
```

上述两次运行须先后完成。PowerShell 直接调用 GUI 可执行文件时可能提前返回。批处理请用 Python 的 `subprocess.run(..., check=True)` 或 `Start-Process -Wait -PassThru` 并检查 ExitCode。

## 试玩整改后沉淀的引擎框架与 37 段实片复验

基于首轮真人／玩家视角试玩报告，游戏完成了美术与玩法系统升级，并将全部规则与数据约束沉淀至引擎（`apps/player/changan_game.*`、`changan.cpp`、`changan_story.*`、`linyuan_sword.hpp`、`linyuan_feedback.hpp`）与装配校验管线（`tools/forge/linyuan_level.py`、`tools/player/check_linyuan.py`）：

| 模块 | 沉淀后的引擎规范与实测结果 |
|---|---|
| 剑匣动态分段收剑与弱点回剑 | 主动收剑耗时统一为 `0.16 + 0.055 × (8 - arrows)` 秒（单剑快收 `0.215s`、双剑快收 `0.270s`、8 剑全收 `0.600s`），按实际召回柄数播放归鞘音并绘制飞剑从各落点弧线归匣（`returnSword` + `caseGlint`）。无辅助半径直击 `.weak.mask` 或 `elite_core` 时立即返还当柄飞剑（`++arrows, ++weakReturns`）并触发 100ms 顿帧与“弱点回剑”金色飘字；擦边吃 12px 辅助半径仅判普通机身命中、不误返飞剑 |
| 多连通域弱点、重甲与抢射惩罚 | `findWeakSpots()` 对 `.weak.mask` 自动聚类（`maxGap = 4`），支持隐狐额心+尾枢、狻猊双肩罐同时显示双弱点环；1–8 波全部配置琥珀弱点掩码。`Node::weakDamage` 支持重甲差异伤害（第 8 波重甲狻猊 `hp: 2, weak_damage: 2, flinch: "wave_08"`：白甲需 2 剑破甲且首剑 60ms 原地受击定格不切镜，直击肩罐 1 剑秒杀并回剑）。隐狐波次（1、5 波）开启 `allow_early_miss: true`，现形前抢射耗剑并出场景材质打空反馈 |
| 十节点递进与鲮鲤双轮攻防 | 节点 5 `c1_w_fox_grove` 统一为 `PL_BAMBOO` 同机位全景；节点 6–8 复用波次起播帧前推 `+12 / +14 / +14` 帧提速；节点 9 鲮鲤改为双轮攻防（首轮拦针→首击露芯→`c1_pangolin_flinch` 合鳞→`elite_launch` 以 `speed: 1.2` 二轮发针→二轮拦针→二轮露芯终击），每轮首次拦截各奖 150 分。基准 `normal` 路线为 **13 发 13 中、2 次拦截、6 次弱点回剑、1 次双剑快收（0.27s）、余 3 剑、3 命、11 击毁**；`shoulder` 全弱点路线为 **13 发 13 中、8 次弱点回剑、0 次手动收剑、余 5 剑** |
| 危急红芒与剧情一剑分支 | `worlds/linyuan/bamboo/threat_glows.json` 以 SHA-256 绑定 7 条攻击片在 `impact_frame` 前最后 0.5 秒（`12 × speed` 帧）的兽瞳／口器／针巢红芒坐标。`c1_10_talon` 慢放窗口前 0.5 秒（72–77 帧）加入翼羽半遮挡破绽；`yunyi_reply` 按 `after_civilian` 分流 `c1_12_thanks`（`yunyi/thanks`）与新增的第 37 段视频 `c1_12_rebuke`（第 10 句配音 `yunyi/rebuke`：“瞄准点儿！还不快去！”） |
| 数据驱动反馈 Schema | `Node` 沉淀 `material`（`ceramic / feather / vine / crystal / metal / phantom`）与 `tier`（`1..3`），`Scene` 沉淀 `attack`（`claw / collision / blast`），由 `linyuan_level.py` 自动写入 `level.json` 并经 `check_linyuan.py` 与 `linyuan_rules` 强校验，彻底解除引擎反馈对视频文件名的硬编码依赖 |

## 已验证的行为（初版 36 段基线归档）

| 范围 | 工程证据 |
|---|---|
| 正常路线 | 普通独立剧情剑命中 +1000。竹海 12 发 12 中、1 次成功拦截、1 次收剑、4 柄余剑、3 命、11 只击毁。五个战役阶段顺序正确，结果页返回“结束”。诊断目录没有生成战役存档。 |
| 剧情一剑 | 击中囊、打空、超时、误伤云姨分别保留原始输入原因。误伤为 −100 分和 2 命进竹海。首个有效源帧及末个有效源帧可以击中。同一输入落在前一帧或截止帧只记为拒绝。按 24 fps、0.5 倍速实测两秒窗口，额外暂停 400 ms 后仍保留原可操作时间。 |
| 小怪及扫描 | 分别运行早、中、晚三条整链，断言每个节点实际播放的击毁片。扫描前扣扳机不消耗普通剑。未击毁的普通怪攻击抵达时扣 1 命，再开同一节点。 |
| 精英 | 飞针晚拦进入晚锚。漏拦走抵达、扣 1 命。圆芯首击后等下一轮发针仍保持 1 点耐久，重复拦截挡伤且不再加 150 分。 |
| 借势与续关 | 直接打藤索通关。打空再补射为 13 发 12 中。双兽扑到合计扣 1 命，在同一节点重开。误伤云姨后在竹海阵亡，续关以 3 命 8 剑重新开局。额外验证空扣、提前收剑、顿帧中的重复扳机。 |
| 已有播放器 | `opening_rules`、`linyuan_rules` 均通过。通过 `--world changan --level a1 --feedback new` 使用既有长安 A1 实际视频做兼容冒烟，14 发 14 中、3 命、40.39 秒。 |
| 长安旧档 | 从旧版 `build/qa/changan-campaign/extract-resume/interrupted.json` 的副本启动，同一战役主程序从 `west_market_opens` 连走 33 段至 `@complete`，五章成绩均保留。第一章原来的 5429 分及其余五个计数字段逐项相同。证据在 `build/qa/linyuan-mvp/legacy-save-20261125-17154139/`。 |

最初的空匣路线在设备提前取音频块时加快了视频。玩家在窗口首次可射时空扣并立即收剑，尚未完成 0.6 秒收剑就受伤。临渊现在以单调时钟给片内播放进度设上限。复测中该路线保有 3 命、4 柄余剑。长安使用原有片内时钟。

开发早期的长安 A1 实片对照已归档在 `dist/Linyuan-MVP-Review/evidence/early-a1/`。同一程序分别使用 `--world changan --level a1 --feedback old --capture` 与 `--feedback new --input-replay <旧反馈取证目录> --capture`。两局均 14 发全中、3 命，新版通过输入复现断言。两片均为 1280×720、H.264/AAC，ffmpeg 全片音视频解码通过。旧版实际采集 612 幅、70.81 秒（平均 8.6 幅/秒），新版 699 幅、92.10 秒（7.6 幅/秒）。同步读回和写图延长了实录，两片用于同输入的观感对照。60 fps 逐帧 F0、顿帧和正常节奏另行验收。原始时间戳及操作记录在 `build/qa/linyuan-mvp/a1-feedback-pair-013542/`。

采集器随后改为后台缩放、限量排队写图和按实际提交时间编码 VFR。同一版临渊首批四段正式素材从本机 NVMe 采到 832 幅／14.51 秒（57.33 幅/秒），间距 P50 16.65 ms、P95 25.63 ms。逐帧核对应查看事件附近的实际采样。此组原始数据在系统临时目录 `linyuan-pilot-capture-20261126-014836584`，较慢工程盘的对比采集在 `build/qa/linyuan-mvp/async-pilot-014524671/`。两条录像均全片音视频解码通过。

最终诊断矩阵 **26/26 通过**，证据在 `build/qa/linyuan-mvp/validated-full-012616177/matrix.json` 及同目录各场景报告。除表内路线，还分开验证四个狻猊节点的肩罐与普通机身、飞针飞行时朝闭芯打空、收剑时重复按下、阵亡选择结束。该组专门让 24 帧半速窗口恰好止于视频末尾。初轮 17 项矩阵存于 `build/qa/linyuan-mvp/validated-matrix-012037126/matrix.json`。空匣与剧情边界的 5 项复测存于 `build/qa/linyuan-mvp/validated-boundaries-012238188/matrix.json`。诊断视频和掩码保存在本地证据目录。

## 36 段实片及交付包

正式影片首版的 **26/26 场景通过**。每场均从标题经原生 SDL 播放器至“结束”或“阵亡结束”。原始事件、命中帧和结果随场景保存在 `build/qa/linyuan-mvp/selected36-matrix-20261126/`，输入版本见 `selected36-runtime-20261126/qa-snapshot.json`，程序 SHA-256 前缀为 `390b940a`。此轮冻结了 36 个视频、9 句对白、配乐及环境声，反馈事件使用开发时的兜底音。

随后更新了云姨口型、石祠和毕方的重试窗口，并加入最终三变体拟音。首版发布包以包外工作目录、无 `--root` 再跑 **5/5**（末锚、首狐受伤重开、剧情首帧、剧情末帧、正常）。证据在 `build/qa/linyuan-mvp/release-routes-20261126/`，程序前缀为 `7b3d2bc1`。关卡与蒙版的九波重试另由关卡专项记录。

实片联调还发现，快速击中圆芯会让原先按切镜清理的 2.637 秒教学台词只播约 0.1 秒。现在同一句语音及字幕随自然时长跨过命中和受击镜头，暂停后顺延，高优先级提示可以抢占，离场和续关清理。本机正常路线四句各起播一次并自然结束。证据记录单调起止时间、实际 WAV 时长和终止原因。对录像的长间隔计时按真实输入与画面提交计算。

### 封版 ZIP 的独占测量

程序 SHA-256 为 `08f3aa36fb42993e9014fc559dfe9ff023a644d88748c39b7518ef0e3cfdd5a5`。从“封版 离线解压验证”的独立解压目录启动，工作目录为系统临时目录，直接读取包内素材。机器为 RTX 5090、OpenGL、1920×1080／60 Hz，游戏逻辑画布 1280×720。关闭录像，单个游戏进程按固定源帧注入 SDL 鼠标事件。进入结果页 42.52 秒，其中竹海 26.63 秒。脚本在上一轮呈现与预读之后注入输入，真人扣扳机的刷新相位未在本轮采样。

| 接力 | 前一击源帧 | 下一目标首个已呈现可打帧 | 系统等待（秒） | 脚本开窗至出剑（秒） |
|---|---:|---:|---:|---:|
| 1 → 2 | 52 | 10 | 1.067 | 1.083 |
| 2 → 3 | 36 | 10 | 1.450 | 1.083 |
| 3 → 4 | 36 | 10 | 1.117 | 1.083 |
| 4 → 5 | 36 | 11 | 1.451 | 0.500 |
| 5 → 6，飞针 | 23 | 22 | 1.900 | <0.001 |
| 6 → 7，精英退出 | 113 | 10 | 1.512 | 1.083 |
| 7 → 8 | 36 | 10 | 1.450 | 1.083 |
| 8 → 9 | 36 | 10 | 1.117 | 1.083 |
| 9 → 10，藤索 | 36 | 10 | 1.400 | 1.417 |

六条普通接力中位 1.284 秒、最大 1.451 秒。竹海 12 剑输入至首次反馈提交 P50 **17.07 ms**、P95 **17.90 ms**。加入独立剧情剑（17.31 ms）后的 13 剑为 **17.08 / 17.90 ms**。本机单个刷新周期为 16.67 ms，两组 P50 均略超设计目标。逐剑源帧、秒表、刷新率和全部接力记录在 `build/qa/linyuan-mvp/locked-timing-20261126/normal/timing.json`，同目录 `voice-completion.json` 记录四句战斗对白自然结束。

### 加粗剑痕前的对照

同一解压游戏从系统临时目录再次从头启动，这次采集已归档在 `build/qa/linyuan-mvp/pre-stroke-capture-review-20261126/`。正常路线旧版录到 2577 幅／45.16 秒、平均 57.06 Hz。新版 2573 幅／45.17 秒、56.96 Hz。原始采样间距 P50 分别为 16.67 和 16.68 ms，P95 为 18.92 和 19.38 ms。编码保留实际呈现的可变帧率。13 剑逐项比较的源帧和结果相同，落点最大误差 0 像素。新版 13 次输入至首次反馈提交之间均采到一幅画面。`evidence/first-feedback/` 保存这 13 张原生呈现的无损静帧，`evidence/first-feedback-samples.json` 可查输入与提交时间。截图中狻猊击毁有可见剑痕、命中标记和浮分，在 960×540 下剑痕偏细。

```powershell
$game = (Resolve-Path 'build/qa/linyuan-mvp/封版 离线解压验证/Linyuan-MVP/Linyuan.exe').Path
$scratch = Join-Path $env:TEMP 'linyuan-review-fresh'
python -X utf8 tools/player/record_linyuan_review.py $game $scratch dist/Linyuan-MVP-Review-rerun --a1-root .
```

### 封版实录与辨认材料

封版剑痕使用深色外沿、淡青色带与亮芯，寿命 50 ms。打击标记和准星有独立线宽与描边。960×540 实际呈现的狻猊击毁证据为 `dist/Linyuan-MVP-Review/evidence/first-feedback/04-wave_03.png`。

五段录像均来自同一份 `08f3aa36` 解压程序，工作目录位于系统临时目录，使用包内全部 36 段视频、定稿语音及拟音。按后台采到的原始帧时间戳生成 H.264/AAC，五片均已通过全片音视频解码。详细帧时间表、场景事件、文件 SHA-256 和程序版本保存在 `dist/Linyuan-MVP-Review/evidence/`。

| 路线 | 文件（相对于评审目录） | 原始采样数 | 时长 | 实际平均采样 |
|---|---|---:|---:|---:|
| 正常旧反馈 | `linyuan-mvp-old.mp4` | 2571 | 45.19 秒 | 56.90 Hz |
| 相同输入，新反馈 | `linyuan-mvp-new.mp4` | 2159 | 45.29 秒 | 47.67 Hz |
| 误伤云姨 | `evidence/linyuan-story-civilian.mp4` | 2114 | 45.21 秒 | 46.76 Hz |
| 藤索打空、补射 | `evidence/linyuan-raft-miss.mp4` | 2214 | 45.24 秒 | 48.94 Hz |
| 飞针漏拦、受击 | `evidence/linyuan-needle-miss.mp4` | 2239 | 46.51 秒 | 48.14 Hz |

正常两版的 13 剑源帧、结果和落点逐项一致，最大坐标偏差 0 像素。新录像的采样间距 P50 16.74 ms、P95 42.44 ms，13 次输入中有 11 次在对应首次提交前直接采到 F0。第 8 剑（圆芯首击，源帧 113）和第 10 剑（节点 7 击毁，源帧 36）在同程序的误伤路线中采到相同事件、相同源帧，两幅分别标注来源。原始时间索引见 `first-feedback-samples.json` 与 `supplemental-feedback-samples.json`。

`recognition/visual/` 的 6 个匿名片段均无音轨，统一遮住直接写出结果和教学信息的 HUD 区域。`recognition/audio/` 的 6 个匿名 WAV 从实录混音截取，为 48 kHz 双声道、每条 0.72 秒。两组编号独立。藤索失手这一条专门在源帧 24 朝空地出剑，保留原来第 44 帧的补射，听辨片段只含第一剑。主持人从 `facilitator/recognition-key.json` 查答案、原始录像、事件和时码。六类的实际辨认率等待真人填写。

长安 A1 对照亦使用封版 `08f3aa36` 的播放器，以 `--world changan --level a1 --root <仓库>` 读取已有真实长安素材。交付目录根下的 `changan-a1-old.mp4` 为 1432 幅／42.95 秒（33.34 Hz），`changan-a1-new.mp4` 为 1410 幅／42.75 秒（32.98 Hz）。两片 1280×720，均全片音视频解码通过。17 次扳机的源帧、结果与坐标逐项相同（误差 0 像素），其中 14 次消耗弹药且全部命中，另 3 次为顿帧内的重复扳机。两局剩余 3 命，细目保存在 `evidence/a1/`。早期同步录屏版独立归档在 `evidence/early-a1/`。

同一解压包又分别以 `--reduced-flash` 和 `--no-shake` 回放新版正常路线。每种设置的 15 条预警及出剑事件均和原版有相同源片、帧号、结果，结算均为 12/12 命中、3 命。证据在 `build/qa/linyuan-mvp/locked-accessibility-20261126/settings.json`。独占计时的程序路径、封包清单哈希、报告哈希及工作目录在 `build/qa/linyuan-mvp/locked-timing-20261126/origin.json`。
