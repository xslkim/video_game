# 《临渊御剑》第一章：出图与视频提示词 v1.0

修订于 2026-11-26。镜号、出场位和时间结构见 [第一章分镜](LINYUAN_CH1_STORYBOARD.md)。人物与设计语言见 [世界观](LINYUAN_WORLD.md)，风格基准和已选测试图见 [美术风格](LINYUAN_ART_HORIZON.md)。

提示词用英文书写：关键帧用 ChatGPT 出图，视频用本机 H3。每条可整段复制。`[S]`、`[N]` 等方括号段落是本文第 1.4 节的公共段，使用时展开成全文。提示词里不写任何现有游戏的名字。

---

## 1. 使用说明

### 1.1 制作顺序

1. 角色设定图（第 2 节）和敌人设定图（第 3 节）。已有测试图的条目以测试图为底图做局部修订，其余新出。狻猊最先定稿，其余机关兽上传它作材质参考。
2. 场面母版（第 4 节）。PL_MARKET 是九曲渡的风格母版，PL_BAMBOO 是竹海的母版，同一地点的其他场面都上传它作风格参考。
3. 剧情首帧和状态锚帧（第 5 节）。按每条写明的参考图上传。
4. 视频（第 6–8 节）。先定波次成片和可命中帧，再从该成片取击毁片首帧。普通波次从空景回空景，普通击毁从敌人在场回空景。借势、鲮鲤和 Boss 分支按各条列出的状态锚帧收尾。

MVP 按[原型方案 §4.1](LINYUAN_MVP.md) 分批。首批用已选的 AH_CAMP_02 派生面摊，先做 PL_NOODLE，再由它做 PL_STALL。第二批修订 PL_MARKET 时回看两张已锁定的面摊母版，核对布棚、蓝光灶台和光向。PL_DUKOU 在完整第一章制作。

### 1.2 尺寸和存放

- 关键帧输出 16:9 满幅，不留黑边。H3 以 1024 × 576 生成，成片 1280 × 720。重要内容避开画面上下各 5% 的边缘。
- 测试图在 `output/imagegen/linyuan_art_horizon_20261125/`，文件名为 `AH_*`。正式关键帧存到 `assets/linyuan/kf_raw/horizon_v1/`，文件名用编号，例如 `CH_LUCHEN.png`、`PL_BAMBOO.png`。同一 ID 有多个候选时加后缀 `_b`、`_c`。投递视频时登记实际选用的场景母版、设定图和状态锚帧。
- 视频任务写进 `worlds/linyuan/production/c1_jobs.json`，每条登记 `first`、可选的 `last`、`length`、`seed`、`prompt` 和 `prefix`。长安脚本省略 `prefix` 时会自动填入唐代上元灯市的描述。临渊各条将展开后的公共段放入 `prefix`（末尾留空格），镜头正文放入 `prompt`；独立成句、无公共段的镜头显式写 `"prefix": ""`。

### 1.3 检查项

所有图：
- 画面里没有可读的文字和汉字。旗帜、匾额、石碑一律无字。模型画出文字就重抽，不靠后期修。
- 没有真实品牌、血、断肢，没有任何现有游戏的角色和机器。
- 质感是风格化写实的游戏过场：不是真人照片，也不是卡通。
- 画面明亮。缩到 960 × 540 时暗部仍有细节。

角色：
- 陆沉的机关义肢在左臂，右臂是普通的手；剑匣口露出 8 柄剑柄，剑柄有小护手，不能像箭矢。面摊里剑匣靠在凳边，离开时斜背。云姨的机关义肢在右前臂。
- 青萍是半透明的淡青光身，能透过她看见背景，脚离地，没有影子。

机关兽：
- 一眼看得出是机器，不是真动物。米白陶瓷甲、深石墨框架、黑色肌肉纤维，四种机关兽像同一家工厂的产品。
- 眼睛只有两种颜色：平静是冷蓝，敌对是赤红。
- 琥珀金色只出现在弱点部件上。
- 以 960 × 540 无 HUD 在同一屏幕看一遍。先认出是哪种机关兽、它在蓄力还是在攻击，再指出琥珀色弱点。弱点和背景里的暖光、阳光挨在一起时，先改出场位或朝向。
- 在 1280 × 720 的**成片可命中帧**逐帧查可见短边：普通目标至少 48 像素，远处目标至少 32 像素，弱点至少 20 像素。MVP 在 Windows 按 960 × 540 实际显示复查燃料囊、藤索结和鲮鲤圆芯；电视实机留到 M4。弱点被翅膀、烟或高光盖住的帧移出窗口，剩余帧数不够就重选或改构图。

场面母版：
- 战斗母版没有人和机关兽。剧情的集市远景 PL_MARKET 保留人群。
- 分镜表里列出的每个遮挡物都在，位置大致正确。
- 中景留出安静的空地给敌人出场；花草、藤蔓只在画面边缘密集。
- 太阳不进画，或至少远离出场位和可打区域。

### 1.4 公共段

**[S] 风格段（所有关键帧）**

```
High-end AAA open-world action-adventure game cinematic in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
```

**[N] 负面段（所有关键帧）**

```
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork, no photographic live-action look. No underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore, no severed human limbs. No weapon or hands of the viewer in frame.
```

**[M] 机关兽设计语言（所有含机关兽的图）**

```
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
```

**[F] 出图格式（场面和独立构图的剧情首帧）**

```
Use case: cinematic-scene. Asset: keyframe for an interactive full-motion video game. Output one single full-bleed 16:9 landscape frame, image only, no borders or letterboxing.
```

**[E] 编辑格式（在已有图上加入人物或机关兽）**

```
Use case: compositing. Asset: a full-bleed 16:9 game-cinematic keyframe. The first image sets location, props, sunlight direction, time of day and screen geography. Keep its camera, framing, exposure and color grade unless the shot specifies a new viewpoint. Other references supply identity, materials and silhouette only; relight the inserted subject from the sun and light sources already in the location, with matching shadows and contact on the ground. Where an action is playable, stage the acting limb and the weak point against a quiet patch of the existing background, away from the sun, lanterns and bright highlights.
```

**[C] 设定图格式**

```
Use case: production-design reference sheet for a game cinematic. One 16:9 image showing exactly four views of the same subject, evenly spaced left to right with clear separation, on location in the environment and light specified below, not in a studio. Every view fully readable from head to foot. Same identity, proportions, materials and colors in every view. Image only, no labels, frames, arrows or lettering.
```

## 2. 角色设定图

### CH_LUCHEN 陆沉

以测试图 `AH_LUCHEN_02` 为底图修订。修两处：剑匣看起来像箭筒，左右臂的义肢不一致。

参考图：AH_LUCHEN_02。

```
Use case: precise edit of the supplied character reference sheet. Keep the same man, face, scar, hair, all four views, the terrace, background, light and every costume detail except the two corrections below. 1) The case on his back must read clearly as a sword case, not a quiver: a flat, wide, old wooden case with iron-bound edges and rope lashing, its open top showing exactly eight slim sword hilts in one neat row, each hilt with a small crossguard and a wrapped grip, each with a short pale-cyan glowing tassel. No arrows, no feathers, no bolts. 2) Only his LEFT arm, from shoulder to fingers, is a mechanical prosthesis of graphite frame, black muscle fibers and pale ceramic plates wrapped with cloth strips; his RIGHT arm is a normal human arm and hand in a cloth sleeve with a leather bracer. Keep this consistent in every view. [N]
```

### CH_QINGPING 青萍

测试图 `AH_QINGPING_02` 可直接用作定妆。若需修订，只改一处：脸部去掉偶像式的妆感，保留俏皮的神情。

参考图：AH_QINGPING_02。

```
Use case: precise edit of the supplied character reference sheet. Keep the same girl, pose, costume, ponytail, ribbon, the semi-transparent pale-cyan light body, the hovering feet, the terrace and the light. Only in the face close-up and the small faces: give her a more distinctive, natural, slightly asymmetric face with a cheeky half-smile and lively eyes, less make-up, no glamour retouching. She remains clearly semi-transparent with the background visible through her. [N]
```

### CH_YUNYI 云姨

新出。参考图：AH_CAMP_02（只取画面左侧掌勺女人的长相和衣着）。

```
[C] Location: a sunlit mossy stone terrace in an old water-town camp with soft out-of-focus bamboo awnings and steam behind, warm afternoon sunlight. Views: full-body front, full-body three-quarter, full-body back, and a larger face close-up on the right.
Subject: Aunt Yun, a Chinese woman in her early fifties who runs the noodle stall, the same woman as the cook in the reference. Sturdy build, round weathered face, laugh lines, quick sharp eyes, grey-streaked hair tied up under a red cloth headscarf. Hand-woven indigo and rust-red layered clothes, a stained cream apron, rolled sleeves, straw sandals. Her RIGHT forearm and hand are a mechanical prosthesis of graphite frame, black muscle fibers and pale ceramic plates, wrapped and patched with cloth strips; her left arm is human. In the close-up she is mid-scold, eyebrows raised, but warm.
[S] [N]
```

## 3. 敌人设定图

### EN_SUANNI 狻猊

测试图 `AH_SUANNI_02` 定稿，不再修订。它是其余机关兽的材质基准。

### EN_BIFANG 毕方

测试图 `AH_BIFANG_02` 定稿，不再修订。

### EN_TAOTIE 饕餮

测试图 `AH_TAOTIE_02` 定稿，不再修订。

### EN_FOX 隐狐

新出。参考图：EN_SUANNI（只取材质和接缝）。

```
[C] Location: a sunlit bamboo-forest clearing with a mossy stone shrine, golden light shafts through the canopy. Views: 1) cloaked, nearly invisible: its shape is defined only by a few floating bamboo leaves, drifting pollen and bent light shafts passing around an invisible fox-like body; 2) revealed, calm, standing in side profile; 3) revealed, hostile, low crouch about to dash forward; 4) destroyed, lying on its side.
Subject: an Yinhu cloaking fox, a predator machine the size of a large wolf, lean and fast, long narrow head, tall ears, nine long slender flexible tail fins fanning behind it. When revealed: off-white ceramic plates with a faint pearly light-bending sheen on their surface. One small amber-gold cell glows on its forehead and one at the root of the tails. View 4: eyes dark, cloaking plates cracked and flickering with fragments of the background, tail fins scattered, thin smoke.
[M] [S] [N]
```

### EN_PANGOLIN 鲮鲤

新出。参考图：EN_SUANNI（只取材质和接缝）。

```
[C] Location: a sunlit bamboo-forest clearing with a mossy stone shrine, golden light shafts through the canopy. Views: 1) front, calm, scales closed, walking; 2) side profile; 3) firing: back scales fanned open into a large semicircular fan, a ring of scales flipped over to cover the center, a burst of glowing needle darts launching from the fan edge; 4) open-core: scales still fanned, the center ring flipped back to reveal one large round glowing amber-gold core in the middle of the fan, as wide as its head.
Subject: a Lingli pangolin machine the size of an ox, low and heavy, long tail, powerful clawed forelegs, overlapping large off-white ceramic scale plates over its whole back. The open fan of scales is the dominant shape, clearly readable from a distance.
[M] [S] [N]
```

### EN_XUANWU 玄武

新出，非敌人。参考图：AH_VISTA_02（取玄武的造型）。

```
[C] Location: a wide jade-green river among karst peaks, bright afternoon sun. Views: 1) wading, side profile, calm blue eyes; 2) front, long neck raised; 3) close view of the shell edge and a hind leg, showing climbable armor ridges and plates; 4) top of the shell: terraced dome of off-white plates carrying trees and a small Buddhist temple with tiled roofs, stone stairs and lanterns.
Subject: Xuanwu, a colossal tortoise machine about forty meters long, the same creature as in the reference. Long armored serpentine neck, thick pillar-like legs of graphite frame and black muscle fibers, water streaming off them. A control hub at the back of its neck under a raised plate, glowing cool blue.
[M] [S] [N]
```

## 4. 场面母版

### PL_VISTA 临渊江与天机峰（c1_05、c1_15 的远景参考）

参考图：AH_VISTA_02（只取风格和地貌）。

```
[F] A wide view across the jade-green Linyuan river from the Jiuqu ferry bank in mid-afternoon sunlight. Karst peaks with pine trees and waterfalls on the far bank, soft mist between them. In the far distance, one tall peak rises above all others into the clouds, and on its summit hangs a colossal ancient broken ring of white stone and metal, split by a gap at the top; both broken ends glow faintly red. On the far grassy slope, a few calm lion-like machines graze, eyes cool blue. Empty river, no giant tortoise.
[M] [S] [N]
```

### PL_MARKET 九曲渡集市（c1_03）

以测试图 `AH_CAMP_02` 为底图。只做两处修订。

参考图：AH_CAMP_02。

```
Use case: precise edit of the supplied frame. Keep the camera, the whole market, all people, lighting and color. 1) Replace any shapes on banners, awnings and signboards that resemble writing with plain cloth or simple woven patterns. 2) Make sure the large horned machine skull shrine on the right has two empty dark eye sockets. Change nothing else. [N]
```

### PL_NOODLE 面摊（c1_04）

参考图：MVP 用 AH_CAMP_02 的面摊和光照，清除棚布上的拟字纹；完整章节有定稿时可用 PL_MARKET。

```
[F] The same Jiuqu ferry noodle stall as the reference, now seen from the side at seated eye height, medium shot, 35mm lens. A long worn wooden table runs across the frame with a bench, a blue-and-white bowl, chopsticks in a bamboo cup and a basket of greens. Behind it, the cook's stove with big steaming pots, heated by a salvaged machine power cell glowing soft blue under the stove. A patched red-and-cream cloth awning overhead, paper lanterns, warm afternoon sunlight from the left, the busy blurred market and the river behind. Nobody in frame.
[S] [N]
```

### PL_DUKOU 集市广场空景（S2 战斗）

参考图：PL_MARKET。

```
[F] The same Jiuqu ferry market square as the reference, empty a moment after everyone has fled, seen from under the noodle stall's awning at eye height, 35mm lens, locked camera. Foreground left: the edge of the stall's long table with steaming bowls and an overturned bench. Mid-left (about 35%, 60%): another long table with a tall stack of bamboo steamers. Upper left (about 22%, 22%): the cloth awning roof of the neighbouring stall. Center distance (about 54%, 42%): the old granite arch bridge over the river. Above it (about 62%, 12%): the top of a ruined stone archway against the sky. Right (about 80%, 52%): the huge horned machine skull shrine with flowers and red cords. Open paved square in the middle ground for action. Warm afternoon sunlight from the upper left, the sun itself out of frame. Gentle breeze. Nobody in frame, no animals, no machines.
[S] [N]
```

### PL_STALL 面摊侧面（S3 一剑）

参考图：PL_NOODLE 定道具和光向。完整章节已有 PL_DUKOU 时可附作远处广场方位参考。

```
[F] Side view of the same noodle stall at eye height, medium-wide, 35mm lens. Left third: the stove with steaming pots and the soft blue power cell, an iron ladle hanging on a hook, one thick vertical bamboo post holding up the awning. A horizontal bamboo beam crosses the upper frame from the post to the right. Right two-thirds: the empty market square and a wide stretch of clear bright sky with a few clouds above the far roofs, kept calm and uncluttered. Warm afternoon sunlight from the left. Nobody in frame.
[S] [N]
```

### PL_BAMBOO 竹海空地（S5 战斗）

以测试图 `AH_BAMBOO_02` 为底图修订。

参考图：AH_BAMBOO_02。

```
Use case: precise edit of the supplied gameplay plate. Keep the camera, the mossy stone shrine on the left with its toppled statue and incense burner, the stream, the stone steps in the distance, the large mossy boulder on the right and the overall light and color. Make these changes only: 1) Move the sun out of frame above the upper right edge; keep the golden light shafts slanting down through the bamboo, but no sun disk or lens flare. 2) On the slope just behind and above the large boulder (about 80%, 26%), add a big bundle of freshly cut long bamboo poles lying across the slope, held in place by one thick twisted vine rope tied in a large visible knot around a wooden stake. 3) Clear the middle ground around the stream and the steps of loose leaves and small flowers so it reads as a calm open arena; keep the dense plants at the frame edges only. Nobody in frame, no animals, no machines. [N]
```

### PL_BAMBOO_X 竹排已落（c1_raft_drop 尾帧）

参考图：PL_BAMBOO。

```
Use case: precise continuity edit of the supplied plate, same camera and the same moment of light. Only change the area behind and below the large boulder on the right: the vine rope is snapped and hanging loose from the stake, the bamboo bundle is gone from the slope, and a messy pile of fallen bamboo poles lies across the stream bank below (about 76%, 62%), with a few broken off-white armor plates sticking out from under it, no glow. Keep every other pixel, the light shafts, shrine, steps and stream unchanged. [N]
```

### PL_SHOAL 江滩（S6 Boss）

参考图：AH_TAOTIE_02（只取地貌）、PL_VISTA。

```
[F] A wide stony river shoal downstream from the Jiuqu ferry at golden-hour sunset, camera low behind a few large foreground rocks, locked. Smooth round pebbles, shallow water reflecting the warm sky, the wide river behind. Karst peaks across the river in layered haze, and the tall peak with the colossal broken ring on its summit, both ends glowing faintly red. The center of the frame is a large open area of shoal and shallow water for a giant creature. The setting sun is out of frame at the upper right, its warm light raking across the stones. Nobody in frame, no machines.
[S] [N]
```

### PL_XUANWU 玄武过浅滩（c1_21、c1_22）

参考图：PL_SHOAL、EN_XUANWU。

```
[E] Same shoal and river at sunset as image 1, camera turned toward the river. The colossal tortoise machine from image 2 wades through the shallows close to the shore from left to right, filling the upper two-thirds of the frame: one huge hind leg lifting out of the water near the camera, water streaming off it, the climbable armored edge of its shell above, the temple on its back with lanterns just lit. Calm cool-blue eyes. Nobody in frame.
[M] [S] [N]
```

## 5. 剧情首帧和状态锚帧

### 5.1 S1 开场

**KF_C1_01**　参考：PL_VISTA、EN_XUANWU

```
[E] Wide panoramic establishing frame of the location in image 1, mid-afternoon. Add the colossal tortoise machine from image 2 wading slowly across the middle of the river, side-on, trees and the small temple on its shell, calm blue eye, water streaming from its legs, a flock of egrets lifting off the water. The far peak with the broken ring stays clearly visible.
[M] [S] [N]
```

**KF_C1_02**　参考：PL_MARKET

```
[F] Aerial shot low over the jade river, flying toward the Jiuqu ferry from the reference: an old granite arch bridge, a half-ruined pagoda wrapped in vines, colorful cloth awnings, smoke and steam rising from the market, egrets flying below the camera. Afternoon sunlight.
[S] [N]
```

**KF_C1_04**　参考：PL_NOODLE、CH_LUCHEN、CH_QINGPING、CH_YUNYI

```
[E] Add exactly three characters once each to image 1. Lu Chen (image 2) sits sideways on the bench at the near left of the table, in profile facing right, head down, eating noodles from the blue-and-white bowl with chopsticks in his natural RIGHT hand; his mechanical LEFT arm rests on the table; his sword case leans against the bench with its eight hilts and pale-cyan tassels visible. Qingping (image 3), semi-transparent pale-cyan light body, sits cross-legged on the table beside his bowl, chin in her hands, staring at the noodles, the stall clearly visible through her body. Aunt Yun (image 4) stands behind the stove at center-right, ladling soup into a bowl with her mechanical RIGHT forearm, steam rising, the power cell glowing under the stove.
[S] [N]
```

**KF_C1_05**　参考：PL_NOODLE、PL_VISTA、EN_SUANNI

```
[E] A view past the edge of the noodle stall's awning in image 1 toward the river and far bank of image 2, medium-wide. In the far distance, both broken ends of the colossal ring on the peak now glow bright red. On the far grassy slope, three lion-like machines from image 3 have raised their heads at once, eyes glowing red. In the foreground, out-of-focus diners at the stall have stopped and look up.
[M] [S] [N]
```

**KF_C1_06**　参考：PL_MARKET、EN_SUANNI

```
[E] Low-angle wide shot in the market square of image 1. One lion-like machine from image 2 lands heavily in the middle of the square after leaping over the low stone wall, mane plates flared, red eyes, two amber-gold canisters bright on its shoulders, dust bursting from the paving. People in hand-woven clothes scatter away to both sides, a dropped basket of vegetables rolling. A flock of crane-like flying machines circles above the archway.
[M] [S] [N]
```

### 5.2 S3 一剑

**KF_C1_10**　参考：PL_STALL、EN_BIFANG、CH_YUNYI

```
[E] Medium side shot in image 1. A crane-like flying machine from image 2 hovers beside the bamboo beam, held aloft by its wings. Its single large talon grips Aunt Yun's (image 3) mechanical RIGHT forearm and pulls her upward. Aunt Yun hugs the vertical bamboo post with her human left arm, her feet just off the ground, face furious. The machine's large amber-gold fuel sac in its chest glows clearly above her head, with a clear patch of bright sky between the sac and her head and hands. Red eyes.
[M] [S] [N]
```

**KF_C1_11_END**　参考：KF_C1_10、CH_YUNYI

```
[E] Same camera and light as image 1, about two seconds later. Aunt Yun stands on the ground by the stove, rubbing her mechanical right forearm with her left hand, looking toward the camera, breathing hard, alive and unhurt. The crane-like machine lies crashed on the ground beside the stove, wings broken and scattered plates around it, chest sac burst and dark, eyes dark, thin smoke. The iron ladle lies on the ground near her feet.
[M] [S] [N]
```

**KF_C1_12**　参考：KF_C1_11_END、CH_YUNYI

```
[E] Chest-up close shot of Aunt Yun from image 2, same location and light as image 1, along the same axis. She glances at Lu Chen just beside the camera with a stern, reluctant almost-smile, lips about to speak; both eyes and mouth clearly visible. She rubs the wrist of her cloth-wrapped mechanical right forearm at lower chest level. The crashed machine is a soft out-of-focus shape at the lower right behind her.
[S] [N]
```

### 5.3 S4、S7 剧情

**KF_C1_13**　参考：PL_NOODLE、CH_LUCHEN

```
[E] Chest-up medium-close shot of Lu Chen (image 2) standing under the noodle stall's awning of image 1, right-facing profile, eyes lowered, listening intently. With his natural RIGHT hand he holds a small spiral conch shell fitted with salvaged machine parts and a faint blue light to his right ear. His sword case is slung on his back with the hilts and tassels visible over his shoulder. A crane-like machine circles small in the sky behind.
[S] [N]
```

**KF_C1_14**　参考：KF_C1_13、CH_QINGPING

```
[E] Medium shot, same place and light as image 1. Qingping (image 2) rises from the top of Lu Chen's sword case and hovers beside him at shoulder height, semi-transparent pale-cyan light body, ponytail and ribbon drifting, her expression serious for the first time. Lu Chen in three-quarter back view.
[S] [N]
```

**KF_C1_15**　参考：KF_C1_13、PL_VISTA

```
[E] Low angle over Lu Chen's right shoulder, his sword case and hilts in the near foreground. He looks up across the river toward the tall peak and the colossal broken ring of image 2, both ends glowing red, the sky still bright with afternoon light turning golden.
[S] [N]
```

**KF_C1_20**　参考：K_TAOTIE_END、PL_XUANWU

```
[E] Same camera as image 1 at sunset. The defeated giant machine kneels smoking on the shoal. Behind it on the river, the colossal tortoise machine of image 2 wades past from left to right, the temple on its back with lanterns just lit, its silhouette against the golden sky.
[M] [S] [N]
```

**KF_C1_21**　参考：PL_XUANWU、CH_LUCHEN

```
[E] Following shot from behind Lu Chen (image 2) as he sprints through the shallows of image 1 toward the huge lifting hind leg of the tortoise machine, water splashing up, sword case on his back, sunset light on the spray.
[M] [S] [N]
```

**KF_C1_22**　参考：PL_XUANWU、CH_LUCHEN

```
[E] Wide side shot. Lu Chen (image 2), small in frame, has leapt onto the armored hind leg of the colossal tortoise of image 1 and grips the edge of its shell. The tortoise wades toward the middle of the river into the setting sun; the far peak and its red-glowing broken ring stand on the horizon.
[M] [S] [N]
```

### 5.4 状态锚帧

**K_PANGOLIN**　参考：PL_BAMBOO、EN_PANGOLIN

```
[E] Insert one pangolin machine from image 2 crouching on the roof ridge of the mossy stone shrine at left in image 1 (about 26%, 16%), facing the camera, its back scales fanned open into a large semicircular fan above it, the center ring of scales flipped back to reveal one large round glowing amber-gold core as wide as its head. Red eyes. Behind the core, a quiet patch of bamboo in shade, no light shaft passing directly behind it. No projectiles, no smoke. Keep everything else of image 1.
[M] [S] [N]
```

**K_TAOTIE_1**　参考：PL_SHOAL、EN_TAOTIE

```
[E] Insert the colossal Taotie machine of image 2 standing on all four legs in the middle of the shoal of image 1, facing the camera, about eight meters tall, filling the center of the frame. Red eyes, horns raised, wet from rising out of the river. On its back, two huge amber-gold fuel canisters, each banded by three metal hoops; the hoops are unlit. Water dripping, ripples around its feet.
[M] [S] [N]
```

**K_TAOTIE_2**　参考：K_TAOTIE_1

```
[E] Same camera, light and creature as image 1. Both back canisters are gone, blown off; torn mounts smoke on its back. It stands lower, head forward, a fiery orange glow showing between its closed jaws. Red eyes. No projectiles.
[M] [S] [N]
```

**K_TAOTIE_3**　参考：K_TAOTIE_2

```
[E] Same camera, light and creature as image 1. It lowers its huge taotie-masked head close to the ground toward the camera, jaws opened wide, revealing one large round glowing amber-gold core deep in its maw, clearly framed by the teeth. Red eyes. Smoke still rising from its back.
[M] [S] [N]
```

**K_TAOTIE_END**　参考：K_TAOTIE_3

```
[E] Same camera and light as image 1, now at deeper golden sunset. The creature kneels on its front legs on the shoal, head down, one horn broken off and lying on the pebbles, the core in its mouth dark, eyes dark, cracked armor plates, thick smoke and a few sparks.
[M] [S] [N]
```

## 6. H3 视频：剧情

### 6.1 公共前缀

**[P_FILM] 剧情镜头前缀**

```
One continuous high-end game-cinematic shot in stylized realism, matching the keyframe's look exactly: clean detailed materials, rich natural color, bright readable light. Follow the stated camera move. Keep the keyframe's sun direction, exposure and color grade. Preserve reference faces, costumes, machines, props and scale. Gentle breeze moves cloth, leaves and steam. Location ambience only. No captions, writing or UI.
```

**[P_PLATE] 场面底片前缀**

```
Locked-off high-end game-cinematic plate in stylized realism. Fix the lens, exposure, sun direction and color grade to the reference. Only a gentle breeze moves leaves, cloth and steam, water flows and light shimmers on it; no falling objects crossing the frame. At the loop seam everything matches the original plate. Empty scene, natural ambience, no music, captions, writing or UI.
```

### 6.2 S1、S3、S4、S7

格式：视频 ID　首帧 → 尾帧 · 长度。没有写尾帧的不锚尾帧。

**c1_01_vista**　KF_C1_01 · 119

```
[P_FILM] Very slow lateral drift along the river. The colossal tortoise machine wades steadily, water streaming from its legs; egrets lift off the water; mist moves between the peaks. The broken ring on the far peak stays still. River and birds ambience.
```

**c1_02_descend**　KF_C1_02 · 119

```
[P_FILM] Smooth fast aerial flight low over the river toward the ferry, passing egrets and rising to reveal the bridge, pagoda and colorful awnings of the market. Wind, then distant market voices.
```

**c1_03_market**　PL_MARKET · 119

```
[P_FILM] Locked-off wide shot of the lively market: steam rising from pots, people eating and talking at long tables, children running and climbing on the fallen machine plate, cloth awnings moving in the breeze. Market voices, clatter of bowls, children laughing.
```

**c1_04_noodle**　KF_C1_04 · 119

```
[P_FILM] Locked-off medium shot. Lu Chen eats slowly without looking up. Qingping, semi-transparent the whole time with the stall visible through her, leans closer to the bowl and tilts her head curiously, then glances at him. Aunt Yun ladles soup with her mechanical forearm, steam rising. Lu Chen's head stays lowered; Qingping speaks with small natural mouth movements.
```

**c1_05_redeye**　KF_C1_05 · 119

```
[P_FILM] Slow push-in past the awning toward the far bank. The red glow on both broken ends of the distant ring pulses brighter. On the far slope the machines' eyes flare red as they lift their heads. The blurred diners in the foreground freeze and look up. A low hum rises over the market noise.
```

**c1_06_leap**　KF_C1_06 · 73

```
[P_FILM] Low-angle locked shot. The lion-like machine lands from its leap with a heavy impact, dust bursting, mane plates flaring, and roars toward the camera. People scatter to both sides. Crane-like machines dive from the sky above the archway. Heavy thud, hydraulic hiss, screams.
```

**c1_10_talon**　KF_C1_10 · 119（成片中段 0.5 倍慢放）

```
[P_FILM] Locked side view. The single talon holds Aunt Yun’s mechanical RIGHT forearm aloft; her flesh LEFT hand stays wrapped around the bamboo post. At the opening of slow motion a passing feather briefly covers half the amber chest sac. During the remaining three quarters of the aim window the whole sac is exposed above her hands; keep both hit and self-rescue exits in the same staging.
```

**c1_11_hit**　c1_10_talon 的悬停锚帧 → KF_C1_11_END · 73

```
[P_FILM] The chest fuel sac bursts with an amber flash and sparks. The machine releases its talon, its wings break apart into scattered plates and it crashes beside the stove, knocking the iron ladle off its hook onto the ground. Aunt Yun drops to her feet and pulls her arm back. End on the anchor.
```

**c1_11_miss**　c1_10_talon 的悬停锚帧 → KF_C1_11_END · 73

```
[P_FILM] Aunt Yun lets go of the post, grabs the iron ladle from its hook with her free hand and smashes it into the machine's chest sac. The sac cracks and sprays sparks; the machine releases her and crashes to the ground beside the stove. She lands on her feet, unhurt, and drops the ladle. End on the anchor.
```

**c1_12_thanks**　KF_C1_12 · 73（`after_civilian: false`）

```
[P_FILM] Locked chest-up shot. Aunt Yun rubs her mechanical right wrist, glances at the noodle stall and gives Lu Chen a little upward nod to send him on his way, half smiling as she speaks one short line. Keep her mouth visible for lip sync.
```

**c1_12_rebuke**　KF_C1_12 · 73（`after_civilian: true`）

```
[P_FILM] Locked chest-up shot from the same anchor. Aunt Yun winces slightly as she checks her mechanical right forearm, shoots Lu Chen an exasperated scolding glare and waves him off urgently toward the mountain pass as she delivers her rebuke line. Keep her mouth clearly visible for lip sync.
```

**c1_13_conch**　KF_C1_13 · 119

```
[P_FILM] Locked medium-close shot. Lu Chen listens to the conch, eyes narrowing as the news sinks in. The conch's small blue light flickers with the voice. The awning cloth moves in the breeze; a flying machine circles far behind.
```

**c1_14_core**　KF_C1_14 · 119

```
[P_FILM] Qingping's light body rises a little higher beside Lu Chen, semi-transparent throughout, ribbon drifting, and turns to him with a serious face as she speaks. Soft particles of light trail from her outline.
```

**c1_15_lookup**　KF_C1_15 · 119

```
[P_FILM] Slow tilt up over Lu Chen's shoulder to the far peak and the red-glowing broken ring. He shifts the sword case higher on his shoulder. The afternoon light turns a little more golden.
```

**c1_20_smoke**　KF_C1_20 · 119

```
[P_FILM] Slow push-in. The defeated machine keeps kneeling, dark and smoking. Behind it the colossal tortoise wades past through the golden river, lanterns glowing on its temple. Smoke hiss, deep call of the tortoise.
```

**c1_21_run**　KF_C1_21 · 119

```
[P_FILM] Handheld-feeling follow shot behind Lu Chen as he sprints through the shallows, water splashing high, toward the huge hind leg lifting out of the river. Footsteps in water, ground shaking with each step of the tortoise.
```

**c1_22_board**　KF_C1_22 · 119

```
[P_FILM] Wide side shot. Lu Chen climbs onto the shell edge as the tortoise wades steadily into the middle of the river toward the setting sun. The far peak and its red-glowing ring hold on the horizon. Hold on the tortoise's silhouette for the chapter end.
```

### 6.3 场面底片

**c1_dukou_plate**　PL_DUKOU → PL_DUKOU · 175

```
[P_PLATE] Steam rises from the bowls, the awnings and lanterns sway a little, light glitters on the distant river.
```

**c1_bamboo_plate**　PL_BAMBOO → PL_BAMBOO · 175

```
[P_PLATE] The bamboo sways gently, pollen drifts in the golden light shafts, the stream flows over the stones.
```

## 7. H3 视频：战斗

### 7.1 公共前缀

**[P_WAVE] 波次前缀**（首尾帧都是场面母版，99 帧）

```
Locked-off high-end game-cinematic shot in stylized realism, fixed lens and exposure, matching the plate's light, color and every background detail through the whole shot. Only the specified machine appears. Within the first half second it emerges from behind its cover into a clear, calm patch of the scene. It holds a readable body silhouette for about a second with its amber-gold weak points visible, then its eyes turn red and it charges up for about a second, attacks toward the camera and retreats behind its cover to the empty plate. Gentle breeze only. No people, music, captions, writing or UI.
```

**[P_KILL] 普通击毁前缀**（从可见目标的早、中、晚锚帧起，回到场面母版，47 帧）。普通波次优先取第 28、42、56 帧。隐狐的竹林首秀约在第 30 帧现形，竹丛复现应在第 10 帧左右现形。两处均从各自扫描完成后的有效窗口取样，按实际帧号登记。

```
Locked-off high-end game-cinematic shot. Match the source hit frame's pose, light and color. The machine reacts in the first frames: an amber-gold canister or cell blows off with a bright amber burst, armor plates break loose, its eyes go dark and it loses support and falls. Stage the fall behind its cover, into water or into the grass, and reach the empty plate by the cut within 22 frames at 24 fps. Hold that clean end state through the last picture. Gentle breeze, no people, blood, music, captions, writing or UI.
```

**[P_FIXED] 特殊交互分支前缀**（首尾状态和可出现的角色由单条提示词指定）

```
Locked-off high-end game-cinematic shot in stylized realism. Fix framing, exposure, light and color to the source plate. Sparks, smoke and debris move only around their source. Match the end anchor's state. Gentle breeze. No player sword trail, camera shake, full-screen flash, HUD, subtitles, text or music.
```

机械动作、罐体炸飞和局部碎裂拍入视频。弹道、命中标记、震屏和全屏闪由引擎在实际输入时叠加。审接缝时关 HUD，以石桥、头骨神龛、石祠和溪石作对照，逐帧看亮度、位置和姿态能否接上，尤其注意竹叶和花草有没有跳动。再缩至 960 × 540 检查张鬃、收翼、扫描和开扇动作。若机身与背景融在一起，先改出场位置、朝向或遮挡关系。隐狐在扫描前只让落叶和光斑显出轮廓。

### 7.2 S2 波次

**c1_w_bifang_awning**

```
[P_WAVE] A crane-like flying machine with white segmented wings and a single large talon climbs over the cloth awning roof at upper left, spreads its wings and hovers clear of the awning. Its large amber-gold chest fuel sac glows in the center of its body. Its eyes turn from blue to red, it folds its wings, dives at the camera, pulls up and flies back behind the awning.
[M]
```

**c1_w_bifang_sky**

```
[P_WAVE] A crane-like flying machine dives out from behind the top of the ruined stone archway against the sky and hovers above the square, wings wide, amber-gold chest sac glowing. Its eyes turn red and two small burning darts shoot from under its wings toward the camera. It climbs and flies back behind the archway.
[M]
```

**c1_w_suanni_tables**

```
[P_WAVE] A lion-like machine leaps up from behind the long table and the stack of steamers, lands on the paving and crouches low. Its mane plates flare open, the two amber-gold canisters on its shoulders brighten, its eyes turn red, and it pounces at the camera, then springs back behind the table.
[M]
```

**c1_w_suanni_shrine**

```
[P_WAVE] A lion-like machine steps sideways out from behind the huge horned skull shrine, crouches low, mane plates flaring, shoulder canisters bright, eyes red. It pounces toward the camera and retreats behind the skull.
[M]
```

**c1_w_suanni_bridge**

```
[P_WAVE] A lion-like machine appears on top of the distant stone arch bridge, head raised, shoulder canisters glowing. Its eyes turn red, its jaws open and it breathes a short stream of orange flame toward the camera, then drops behind the bridge.
[M]
```

**c1_w_peddler**

```
[P_FIXED] A frightened peddler in hand-woven clothes runs from left to right through the middle of the empty market square, a bamboo shoulder pole bouncing with two swinging baskets of vegetables, glancing back over his shoulder. His face, body and baskets are clearly visible together. No machines; finish on the original empty plate.
```

### 7.3 S2 击毁（每条波次在第 28、42、56 帧各一条）

**c1_w_bifang_awning_kill_* / c1_w_bifang_sky_kill_***

```
[P_KILL] The chest fuel sac bursts with an amber flash; white wing plates scatter. The crane-like machine spins down behind the awning roof or behind the archway.
```

**c1_w_suanni_tables_kill_* / c1_w_suanni_shrine_kill_***

```
[P_KILL] One shoulder canister blows off and tumbles away with an amber burst; mane plates break loose. The lion-like machine collapses sideways behind the table or behind the skull, smoking.
```

**c1_w_suanni_bridge_kill_***

```
[P_KILL] A shoulder canister blows off with an amber burst. The lion-like machine topples off the bridge into the river with a splash.
```

### 7.4 S5 波次

**c1_w_fox_shrine**　PL_BAMBOO → PL_BAMBOO · 99

```
[P_FIXED] From the empty bamboo plate, a few leaves and a bent light shaft trace an invisible fox in the shrine doorway. Until the scan completes, keep the armor, eyes and cells invisible. Around frame 30 a thin pale-cyan beam from the lower right completes its sweep and reveals a lean white fox-like machine with nine slender tail fins and an amber forehead cell. Hold a clear silhouette long enough for the shot, then lower the body, turn its eyes red and dash toward the camera. It cloaks again and slips behind the doorway, restoring the empty plate.
[M]
```

**c1_w_fox_grove**　PL_BAMBOO → PL_BAMBOO · 99

```
[P_FIXED] From the empty bamboo plate, leaves trace an invisible fox in the left foreground thicket. At about frame 10 a pale-cyan scan finishes and reveals its white armor, nine tail fins and amber forehead cell for the first time. Hold a clear silhouette, lower the body, turn its eyes red and dash toward the camera. It cloaks again and disappears behind the thicket. Finish on the empty plate.
[M]
```

**c1_w_bifang_canopy**

```
[P_WAVE] A crane-like flying machine bursts out of the bamboo canopy at the top center, leaves flying. It hovers beside a light shaft, its glowing amber chest sac silhouetted against cool green bamboo in shade. Its eyes turn red, it folds its wings and dives at the camera, pulls up and returns into the canopy.
[M]
```

**c1_w_suanni_rock**

```
[P_WAVE] A lion-like machine leaps up onto the top of the large mossy boulder at right, crouches, mane plates flaring, shoulder canisters bright, eyes red, pounces toward the camera and drops back behind the boulder.
[M]
```

**c1_w_suanni_steps**

```
[P_WAVE] A lion-like machine bounds down the distant stone steps, stops by the stream and crouches low, shoulder canisters glowing, eyes red, pounces toward the camera and bounds back up the steps.
[M]
```

**c1_w_raft**　PL_BAMBOO → PL_BAMBOO · 99

```
[P_FIXED] Begin on the empty bamboo plate. Two lion-like machines rise together from cover on the stream bank below the bamboo bundle, eyes red, mane plates flaring. They crouch, pounce toward the camera together, then retreat out of sight. Above them, the bundle of bamboo poles tied by the thick vine rope sways slightly; the knot stays visible against the slope and the poles remain secured. End on the original empty plate.
[M]
```

### 7.5 S5 击毁和借势

**c1_w_fox_shrine_kill_* / c1_w_fox_grove_kill_***（三个锚帧都在现形后）

```
[P_KILL] The forehead cell bursts with an amber flash; the cloaking plates shatter into flickering fragments. The fox-like machine tumbles back into the shrine doorway or the thicket.
```

**c1_w_bifang_canopy_kill_***

```
[P_KILL] The chest fuel sac bursts with an amber flash; white wing plates scatter. The machine spins down into the bamboo.
```

**c1_w_suanni_rock_kill_* / c1_w_suanni_steps_kill_***

```
[P_KILL] One shoulder canister blows off with an amber burst. At the boulder, the machine and loose canister fall behind the rock. At the steps, they tumble out of sight behind the bank beside the stairway. Smoke clears for the empty end plate.
```

**c1_raft_drop_28 / 42**　c1_w_raft 的锚帧 → PL_BAMBOO_X · 47

```
[P_FIXED] The vine rope snaps at the knot. The whole bundle of bamboo poles rolls down the slope with a roar and crashes onto the two lion-like machines by the stream; armor plates and bamboo fly, the machines' eyes go dark under the pile. Finish on the end anchor with the rope hanging loose and the pile of bamboo on the bank.
[M]
```

### 7.6 鲮鲤

**[P_ELITE] 精英前缀**

```
Locked-off high-end game-cinematic shot in stylized realism, matching the bamboo-clearing plate's light and color. The shrine roof ridge is at upper left, against a quiet patch of bamboo. While the pangolin is in view, its large fan of off-white scales is easy to see. Solid scales cover the center with no amber glow throughout every needle flight. In the open-core pose the scales turn back, exposing the round amber cell against the shade. Match the specified start and end anchors. Gentle breeze, no people, music, captions, writing or UI.
[M]
```

**c1_w_pangolin_roof**　PL_BAMBOO → K_PANGOLIN · 119

```
[P_ELITE] It climbs onto the roof ridge from behind, plants its claws and fans its back scales open. A ring of scales flips over to cover the core, and a tight cluster of glowing needle darts with short golden trails launches toward the camera. When the darts have left the frame, the ring flips back to reveal the core. End on the anchor.
```

**c1_pangolin_intercept_early / late**　发射片的两个飞行锚帧 → K_PANGOLIN · 47

```
[P_ELITE] The cluster of needle darts explodes in mid-air in a compact burst of sparks. The smoke clears within 12 frames to reveal the pangolin on the roof with its core open.
```

**c1_pangolin_impact**　发射片的抵达帧 → K_PANGOLIN · 47

```
[P_ELITE] The needle darts burst just short of the lens. The sparks clear within 12 frames to reveal the pangolin on the roof with its core open.
```

**c1_pangolin_threat**　K_PANGOLIN → K_PANGOLIN · 99

```
[P_ELITE] From the open-core pose, the ring of scales flips over the core again and another cluster of needle darts launches toward the camera, matching the first volley's launch pose. After the darts leave the frame, the ring flips back. End on the anchor.
```

剪辑时先锁首发片的盖芯姿态和飞针段。循环片只取 K_PANGOLIN 到同一盖芯姿态的起势，接首发片同一段飞针，再回 K_PANGOLIN。两条成片分别登记飞行段的起止帧、拦截锚与抵达帧；核对相对帧的针簇位置和掩码一致。拼不上时返修起势，保留已验过的飞行段。

**c1_pangolin_flinch**　K_PANGOLIN → K_PANGOLIN · 47

```
[P_ELITE] The core sprays sparks; the pangolin staggers on the ridge, scales rattling, then settles back into the same open-core pose.
```

**c1_pangolin_kill**　K_PANGOLIN → PL_BAMBOO · 73

```
[P_ELITE] The core bursts with an amber flash; the fan of scales breaks apart. The pangolin topples backward off the roof ridge and disappears behind the shrine. End on the empty plate.
```

## 8. H3 视频：饕餮

**[P_BOSS] Boss 前缀**

```
Locked-off high-end game-cinematic shot in stylized realism, matching the shoal plate's sunset light and color. A colossal Taotie machine about eight meters tall, built like a rhinoceros, bull and bear, its face shaped after an ancient bronze taotie mask with wide brow ridges, curling horns and round red eyes, stands on the shoal. Only the selected weak point glows. Keep components that are not yet exposed hidden until the stated stage. Match start and end anchors. River and hydraulic ambience, no people, music, captions, writing or UI.
[M]
```

**c1_boss_enter**　PL_SHOAL → K_TAOTIE_1 · 119（从立稳后的余帧裁短）

```
[P_BOSS] Start as a tall splash of river water fills the lower frame, matching the bamboo crash. The spray clears to reveal the creature rising out of the river and planting its feet on the shoal in the pose of the end anchor. All canister hoops stay unlit. Complete the emergence within the opening second and hold the end pose.
```

**c1_boss_p1_a / c1_boss_p1_b / c1_boss_p1_c**　各 K_TAOTIE_1 → K_TAOTIE_1 · 119

```
[P_BOSS] From the neutral pose it turns its body to the screen-left so the screen-left back canister swings toward the camera, and the <n> hoop on that canister lights up bright amber; it holds steady for the aim window, then charges a few steps toward the camera, stamps and returns to the neutral pose, hoop dark. Repeat the same turn, hoop, hold, charge and reset for the screen-right canister. Finish on the exact neutral anchor.
```

每条单独投递，把 `<n>` 依次换成 `first`、`second`、`third`。左右均以画面为准。三条冲撞片分别复用同一个左侧瞄准姿态和同一个右侧瞄准姿态，仅改变当窗发亮的罐箍。前五击由引擎在实际落点画火花，失效的箍熄灯并保持结构完整。每片标注两个起窗、抵达和中立复位点；命中切同侧受击片，复位后从下一未完成窗口对应的中立帧起播。

**c1_boss_p1_flinch_l / _r**　同侧瞄准姿态 → K_TAOTIE_1 · 47（分别代入 screen-left、screen-right）

```
[P_BOSS] The <side> canister jerks at impact, its hoop lights cut out, and all metal bands remain physically intact. The creature flinches, all four feet planted, then straightens into the neutral anchor within the opening second and holds it.
```

**c1_boss_break**　第六窗的右侧瞄准姿态 → K_TAOTIE_2 · 73

```
[P_BOSS] The final glowing hoop goes dark. Both canisters tear free with their bands in two amber explosions and tumble across the shoal. The creature roars, lowers itself, and a fiery glow rises between its jaws by the end of the opening second. Hold the end pose for the first volley.
```

**c1_boss_p2_launch**　K_TAOTIE_2 → K_TAOTIE_2 · 99

```
[P_BOSS] Within the first eight frames it opens its jaws and spits one large glowing fireball that flies straight toward the camera, growing larger as one compact target. Keep the fireball visible on approach, then let it pass the camera; the shot ends on the neutral pose without an explosion.
```

**c1_boss_p2_intercept_early / _mid / _late**　发射片的三个飞行锚帧 → K_TAOTIE_2 · 47

```
[P_BOSS] The fireball explodes in mid-air in a compact orange burst with scattered sparks. The smoke clears within 12 frames to reveal the same neutral pose, ready for the next volley or the mouth-opening shot.
```

**c1_boss_p2_impact**　发射片的抵达帧 → K_TAOTIE_2 · 47

```
[P_BOSS] The fireball bursts just short of the lens. The fire and smoke clear within 12 frames to reveal the neutral pose; hold it for the cut.
```

**c1_boss_expose**　K_TAOTIE_2 → K_TAOTIE_3 · 73

```
[P_BOSS] It lowers its huge head toward the camera and opens its jaws wide, revealing the round amber-gold core deep in its maw. Complete the change in the opening second and hold the exposed pose.
```

**c1_boss_p3**　K_TAOTIE_3 → K_TAOTIE_3 · 99

```
[P_BOSS] Jaws wide, the core pulses brighter for about two seconds as it gathers itself. It lunges forward with a snapping bite, throwing pebbles and water aside, stops short and returns to the same exposed pose.
```

**c1_boss_p3_flinch**　K_TAOTIE_3 → K_TAOTIE_3 · 47

```
[P_BOSS] The core sprays sparks inside its maw; the head jerks back and the legs brace under the load. It settles into the same pose, jaws wide and core still glowing.
```

**c1_boss_kill**　K_TAOTIE_3 → K_TAOTIE_END · 73

```
[P_BOSS] The core cracks and goes dark. One horn snaps off and falls. The creature drops to its knees on the shoal with a heavy impact, armor cracking, thick smoke pouring out. Reach the end pose within the first 30 frames and hold it.
```

## 9. 配音的音色描述

用于 Qwen3-TTS VoiceDesign 设计音色，再用声音克隆固定。M0-C 与 VoxCPM2 对比后按角色选定。

| 角色 | 音色描述 |
|---|---|
| 陆沉 | 二十多岁的中国男性，低沉、略带沙哑，话少、语速偏慢，平静克制，偶尔冷幽默，普通话 |
| 青萍 | 十七八岁的少女，清亮、灵动、语速快，带一点俏皮和不服气，着急时声音拔高，普通话 |
| 云姨 | 五十岁左右的中国女性，嗓门大、爽快，带一点江南口音的普通话，嘴硬心软 |
| 老九 | 四十岁左右的男性，沙哑、碎嘴、语速很快，传音里略带失真，普通话 |

老九的台词在混音时加传音效果（带通 300–3400Hz，轻微失真和底噪，加一点螺壳的空腔共鸣）。青萍的台词加一层很轻的空灵质感（短延迟、极轻的合唱），只在剧情里使用，战斗喊话保持干声以保证清晰。
