# 《长安灯妖录》制作与回归记录

## 2026-11-24 · 1.0 五章正式交付

发布目录为 `dist/Changan-1.0/`。Windows 与 Android 均提供完整五章、三档难度、语音、字幕、章节存档与总评。长版标题、实际播放时间、设备覆盖、回放和校验值以[正式交付验收](CHANGAN_RELEASE_QA.md)为准。下文按时间保留各版当时的结果。

## 2026-11-24 · 五章联调版

Windows 已从独立目录完成五章 38 段，普通自动路线为 335.28 秒。实际存档完成标记为 `@complete`，五章分数均保留。独立包是 `dist/Changan-FiveChapters-Windows-x64.zip`，SHA-256 为 `5b6f9f4ab1d1e11b8b8e56d84886addb7f75402ee81aca4383453e5373257035`。完整时间线与成绩在 `build/qa/changan-campaign/offline-scored/`。[五章操作说明](PLAY_CHANGAN_CAMPAIGN.md)

| 专项 | 实际结果 |
| --- | --- |
| 两面假镜 | 简单难度先右后左，各得 500 分，余五条命。见 `mirror-right/hall_of_mirrors.json`。 |
| 九首龙舟 | 困难难度先故意打第三盏，再打正确的第一盏，之后完成九盏与本章。见 `dragon-order/nine_lanterns.json`。 |
| 终章一箭 | 普通难度打空、超时分别得到 0 分，各自通往结局并完成存档。见 `final-story-miss/` 和 `final-story-timeout/`。 |
| 配乐、角色对白 | 制作了 17 首 ACE-Step 配乐，沈砚、裴照各六句新增 Qwen3-TTS 台词。普通话识别对照见 `build/qa/changan-casting/guards-asr.json`，专名有同音转写。 |
| Android | 五章共享原 H3 片和显示帧区域数据。API 36 模拟器已通过开场、街战、巨鲤和西市假镜。剧情前后段在继续验证。双路视频解码曾在街上暂停，互动场改用原片逐帧合成后完成了同一段。 |
| 长度与硬件 | 本轮包的普通通关时间仍低于原订目标。补拍的剧情和分阵战斗正在另一版集成。实体手机、电视与摄像头标定仍待实机。 |

以下是各次独立交付时的记录。

## 可试玩版本

- 三节点基线保留在 `dist/Changan-Market/`。
- 长版朱雀大街发行包为 `dist/Changan-A1-Windows-x64.zip`。SHA-256 为 `1fb2defe292267d087b44c0c238a46a80486d40c0227763a076b6b5de100fdad`。普通路线、保护对象、三难度、雷符从零充满的运行记录见 [长版验收](CHANGAN_A1_QA.md)。
- 上元夜前段可直接运行 `dist/Changan-FirstNight/Changan.exe`。离线包为 `dist/Changan-FirstNight-Windows-x64.zip`，SHA-256 为 `f1d77faafbc8b22b7ad0a09c4869d91a7069c02e91b88662c4b6b86481afb3e0`。这个版本从长安俯瞰、巡街到救阿萤和初次交谈，使用阶段自动存档。首章后半段在独立开发版本中接入。包内人物对白主要用字幕，阿萤新配音及口型镜头进入后续版本。
- 前段在游戏正常输入路径跑过射中吊索、打空、超时三种情况。三个结果均进入交谈，救人得分依次为 1000、0、0。回放及存档在 `build/qa/changan-campaign/first-night-*/`。把包移至单独目录后，使用其他工作目录启动并通关的记录在 `offline-first-night/`。

## 视听资产

定妆稿含阿萤、沈砚、裴照、玄烛。故事成片以 H3 的 1024 × 576 输出制作并交付为 1280 × 720、24 帧每秒。人物定妆、章节关键帧、定稿戏剧片分别在 `assets/changan/casting/`、`story-anchors/`、`drama/`。玩家已选定写实方向，本轮角色声音、配乐和新镜头由制作方选用。

拍摄任务、种子和分支首帧在 `worlds/changan/production/drama_jobs.json`。候选 `carp_wick` 因无关人物遮住鱼腹退片，改用首尾双锚点的鱼腹近景 `carp_wick_clean`。阿萤初遇等片段按选定画幅裁去模型生成的底部文字。实际成片哈希和帧数在 `worlds/changan/drama.json`，剧情判定多边形与最终视频哈希绑定。

阿萤与玄烛各录五句、每句两种本地模型。试听文件统一至 −19 LUFS，文字对照用本地 SenseVoiceSmall 识别，见 `build/qa/changan-casting/audition.json`。初选阿萤用 VoxCPM2，玄烛用 Qwen3-TTS Uncle_Fu。识别结果中，阿萤的“我能帮你们找到它们”和“如果我真是他的灯”在 Vox 版本更贴近原句。阿萤的首句用 LatentSync 在 H3 真人面部近景上做口型，产物为 `assets/changan/drama/aying_help.mp4`。两首器乐有上元节奏曲和阿萤主题。十种短拟音来自 Stable Audio Open，街战内使用独立音轨播放。

## 构建与实机范围

长版使用 `tools/player/build_changan.ps1 -Level a1`。剧情打包器为 `tools/player/package_changan_campaign.py`，按章节图选择视频、判定与离线 DLL。PC 端恢复点记录于当前 Windows 账号的 SDL 首选项目录，开发回放写入各自证据目录。原版西部游戏共用解码和音频，长安修改后运行了原有 Windows 回放。

手机控制器源代码在 `D:/tvgun/android`。新增雷符按钮可发 UDP SPECIAL 或 HTTP /special，已成功编译签名 APK。PC 上用 F2 或 --tvgun 启用定位白框，失锁暂停，重新定位后按开始键继续。ADB 当前未枚举到手机或电视，硬件瞄准精度、延迟和长时间运行仍待实机。

五章全流程、各章弹量与攻击机会、全套剧情声音、移动端游戏客户端及电视实机尚待整体验收。后续提交给玩家的完整版本应包含最终剧情清单、自动与实机测试范围、回放及成品包哈希。
